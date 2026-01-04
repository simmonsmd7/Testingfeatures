"""
Polymarket Whale & Insider Tracker
Monitors blockchain for suspicious trading patterns.

Detects:
- New wallets making large first trades
- Concentrated positions (one market, big size)
- Unusual volume spikes before news
- Wallet clustering patterns

Usage:
    python whale_tracker.py                    # Scan with defaults
    python whale_tracker.py --hours 48         # Scan last 48 hours
    python whale_tracker.py --min-trade 10000  # Only trades > $10k
    python whale_tracker.py --wallet 0x123...  # Analyze specific wallet
"""

import json
import requests
from datetime import datetime, timedelta
from typing import Optional
from dataclasses import dataclass
import sys

# Polygon RPC endpoints (public, free)
POLYGON_RPCS = [
    "https://polygon-rpc.com",
    "https://rpc.ankr.com/polygon",
    "https://polygon.llamarpc.com",
]

# Polymarket contracts on Polygon
CONTRACTS = {
    "ctf_exchange": "0x4bfb41d5b3570defd03c39a9a4d8de6bd8b8982e",  # Main CTF Exchange
    "ctf_exchange_old": "0xC5d563A36AE78145C45a50134d48A1215220f80a",  # Legacy CTF Exchange
    "neg_risk_exchange": "0x4D97DCd97eC945f40cF65F87097ACe5EA0476045",  # NegRisk CTF Exchange
    "usdc": "0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174",
    "conditional_tokens": "0x4D97DCd97eC945f40cF65F87097ACe5EA0476045",
}

# USDC Transfer event signature
USDC_TRANSFER_TOPIC = "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"

# OrderFilled event signature from CTF Exchange (verified from on-chain data)
ORDER_FILLED_TOPIC = "0xd0a08e8c493f9c94f29311604c9de1b4e8c8d4c06bd0c789af57f2d65bfec0f6"

# OrdersMatched event (alternative event used in some contracts)
# keccak256("OrdersMatched(bytes32,address,address,uint256,uint256,uint256,uint256)")
ORDERS_MATCHED_TOPIC = "0x829fa99d94dc4636925b38632e625736a614c154d55c8d5c513ed85f9a778d02"

# Minimum trade size to track (in USDC, 6 decimals)
MIN_TRADE_SIZE = 1000  # $1,000

# Cache for token ID to market mapping
TOKEN_TO_MARKET_CACHE = {}

# Sports-related keywords to filter out for political/news insider detection
SPORTS_KEYWORDS = [
    # American Football
    "nfl", "football", "touchdown", "quarterback", "super bowl", "superbowl",
    "patriots", "chiefs", "eagles", "cowboys", "49ers", "ravens", "bills",
    "dolphins", "jets", "steelers", "browns", "bengals", "raiders", "broncos",
    "chargers", "colts", "texans", "titans", "jaguars", "commanders", "giants",
    "bears", "packers", "lions", "vikings", "saints", "falcons", "buccaneers",
    "panthers", "cardinals", "rams", "seahawks",
    # Basketball
    "nba", "basketball", "lakers", "celtics", "warriors", "nets", "knicks",
    "heat", "bucks", "76ers", "suns", "mavericks", "clippers", "nuggets",
    "grizzlies", "pelicans", "timberwolves", "thunder", "blazers", "kings",
    "spurs", "rockets", "jazz", "cavaliers", "pistons", "pacers", "bulls",
    "hawks", "hornets", "magic", "wizards", "raptors",
    # Baseball
    "mlb", "baseball", "yankees", "red sox", "dodgers", "mets", "cubs",
    "astros", "braves", "phillies", "padres", "mariners", "orioles", "twins",
    "guardians", "rangers", "rays", "blue jays", "white sox", "royals",
    "tigers", "athletics", "angels", "giants", "diamondbacks", "rockies",
    "brewers", "cardinals", "reds", "pirates", "marlins", "nationals",
    # Hockey
    "nhl", "hockey", "stanley cup", "bruins", "rangers", "maple leafs",
    "canadiens", "blackhawks", "penguins", "capitals", "lightning", "avalanche",
    "knights", "oilers", "flames", "canucks", "kraken", "wild", "blues",
    "predators", "stars", "hurricanes", "panthers", "devils", "islanders",
    "flyers", "senators", "sabres", "red wings", "blue jackets", "jets",
    "coyotes", "sharks", "ducks", "kings",
    # Soccer
    "soccer", "premier league", "la liga", "bundesliga", "serie a", "ligue 1",
    "champions league", "world cup", "manchester united", "manchester city",
    "liverpool", "chelsea", "arsenal", "tottenham", "real madrid", "barcelona",
    "bayern", "juventus", "psg", "inter milan", "ac milan", "mls",
    "atlético", "atletico", "paris saint-germain", "borussia", "benfica",
    "porto", "sporting", "ajax", "feyenoord", "celtic", "rangers fc",
    # Golf/Tennis/Boxing/MMA
    "golf", "pga", "masters", "tennis", "wimbledon", "us open", "australian open",
    "french open", "boxing", "ufc", "mma", "fight", "knockout",
    # Racing
    "nascar", "f1", "formula 1", "racing", "grand prix", "indy 500",
    # General sports terms
    "spread", "over/under", "moneyline", "point spread", "playoff", "playoffs",
    "championship", "finals", "semifinals", "quarterfinals", "division",
    "conference", "regular season", "postseason", "game 1", "game 2", "game 3",
    "game 4", "game 5", "game 6", "game 7", "vs.", "beat the",
]


def is_sports_market(market_question: str) -> bool:
    """Check if a market question is sports-related."""
    if not market_question:
        return False
    question_lower = market_question.lower()
    return any(keyword in question_lower for keyword in SPORTS_KEYWORDS)


@dataclass
class Trade:
    """Represents a Polymarket trade."""
    tx_hash: str
    wallet: str
    timestamp: datetime
    market_id: str
    side: str  # 'buy' or 'sell'
    amount_usdc: float
    outcome: str  # 'yes' or 'no'
    block_number: int


@dataclass
class WalletProfile:
    """Profile of a wallet's trading behavior."""
    address: str
    first_seen: Optional[datetime]
    total_trades: int
    total_volume: float
    unique_markets: int
    largest_trade: float
    is_new: bool  # Less than 7 days old
    is_concentrated: bool  # >80% in one market
    flags: list


def get_market_for_token(token_id: str) -> Optional[dict]:
    """Map a token ID to its market question using Polymarket API."""
    if token_id in TOKEN_TO_MARKET_CACHE:
        return TOKEN_TO_MARKET_CACHE[token_id]

    try:
        # Query Polymarket Gamma API for market by token ID
        url = f"https://gamma-api.polymarket.com/markets"
        params = {"clob_token_ids": token_id, "limit": 1}
        response = requests.get(url, params=params, timeout=10)

        if response.ok:
            markets = response.json()
            if markets and len(markets) > 0:
                market = markets[0]
                result = {
                    "question": market.get("question", "Unknown"),
                    "slug": market.get("slug", ""),
                    "outcomes": json.loads(market.get("outcomes", "[]")),
                    "outcome_prices": json.loads(market.get("outcomePrices", "[]")),
                }
                TOKEN_TO_MARKET_CACHE[token_id] = result
                return result
    except Exception as e:
        pass

    return None


def get_all_markets_batch() -> dict:
    """Fetch a batch of markets to pre-populate the cache."""
    try:
        url = "https://gamma-api.polymarket.com/markets"
        params = {"limit": 100, "active": "true"}
        response = requests.get(url, params=params, timeout=15)

        if response.ok:
            markets = response.json()
            for market in markets:
                token_ids = market.get("clobTokenIds", "[]")
                try:
                    tokens = json.loads(token_ids) if isinstance(token_ids, str) else token_ids
                    for token_id in tokens:
                        TOKEN_TO_MARKET_CACHE[token_id] = {
                            "question": market.get("question", "Unknown"),
                            "slug": market.get("slug", ""),
                            "outcomes": json.loads(market.get("outcomes", "[]")),
                            "outcome_prices": json.loads(market.get("outcomePrices", "[]")),
                        }
                except:
                    pass
            return TOKEN_TO_MARKET_CACHE
    except Exception as e:
        print(f"Error fetching markets batch: {e}")

    return {}


def get_wallet_first_tx(wallet: str) -> Optional[datetime]:
    """Get the timestamp of a wallet's first transaction on Polygon."""
    try:
        # Use Polygonscan API (free tier)
        url = f"https://api.polygonscan.com/api"
        params = {
            "module": "account",
            "action": "txlist",
            "address": wallet,
            "startblock": 0,
            "endblock": 99999999,
            "page": 1,
            "offset": 1,
            "sort": "asc",
        }
        response = requests.get(url, params=params, timeout=10)
        data = response.json()

        if data.get("status") == "1" and data.get("result"):
            first_tx = data["result"][0]
            timestamp = int(first_tx.get("timeStamp", 0))
            return datetime.fromtimestamp(timestamp)
    except Exception as e:
        print(f"Error fetching wallet age: {e}")

    return None


def get_wallet_age_days(wallet: str) -> Optional[int]:
    """Get the age of a wallet in days."""
    first_tx = get_wallet_first_tx(wallet)
    if first_tx:
        age = datetime.now() - first_tx
        return age.days
    return None


def check_wallet_flags(wallet: str, trades: list[dict]) -> list[str]:
    """Check for suspicious patterns in a wallet's trading."""
    flags = []

    # Check wallet age
    age_days = get_wallet_age_days(wallet)
    if age_days is not None and age_days < 7:
        flags.append(f"NEW_WALLET ({age_days} days old)")

    if not trades:
        return flags

    # Check for concentrated positions
    markets = {}
    total_volume = 0
    for trade in trades:
        market = trade.get("market", "unknown")
        amount = trade.get("amount", 0)
        markets[market] = markets.get(market, 0) + amount
        total_volume += amount

    if total_volume > 0:
        for market, volume in markets.items():
            concentration = volume / total_volume
            if concentration > 0.8:
                flags.append(f"CONCENTRATED ({concentration:.0%} in one market)")
                break

    # Check for large first trade
    if trades:
        first_trade_amount = trades[0].get("amount", 0)
        if first_trade_amount > 5000:
            flags.append(f"LARGE_FIRST_TRADE (${first_trade_amount:,.0f})")

    # Check for rapid accumulation
    if len(trades) >= 3:
        first_three_time = trades[2].get("timestamp", 0) - trades[0].get("timestamp", 0)
        first_three_volume = sum(t.get("amount", 0) for t in trades[:3])
        if first_three_time < 3600 and first_three_volume > 10000:  # 1 hour, $10k
            flags.append(f"RAPID_ACCUMULATION (${first_three_volume:,.0f} in <1hr)")

    return flags


def rpc_call(method: str, params: list, rpc_url: str = None) -> dict:
    """Make a JSON-RPC call to Polygon."""
    # Only use polygon-rpc.com as it's most reliable
    rpc = rpc_url or "https://polygon-rpc.com"

    payload = {
        "jsonrpc": "2.0",
        "method": method,
        "params": params,
        "id": 1,
    }

    try:
        response = requests.post(rpc, json=payload, timeout=30)
        result = response.json()
        return result
    except Exception as e:
        return {"error": str(e)}


def get_current_block() -> int:
    """Get the current block number on Polygon."""
    result = rpc_call("eth_blockNumber", [])
    return int(result.get("result", "0x0"), 16)


def get_block_timestamp(block_num: int) -> datetime:
    """Get the timestamp of a specific block."""
    hex_block = hex(block_num)
    result = rpc_call("eth_getBlockByNumber", [hex_block, False])
    block = result.get("result", {})
    timestamp = int(block.get("timestamp", "0x0"), 16)
    return datetime.fromtimestamp(timestamp)


def get_order_filled_trades(hours: int = 6, min_value_usd: int = 5000, filter_sports: bool = False) -> list[dict]:
    """
    Get actual OrderFilled trades from CTF Exchange contracts.
    This gives us the specific market and price information.

    Args:
        hours: How far back to scan
        min_value_usd: Minimum trade size in USD
        filter_sports: If True, exclude sports betting markets (for political/news focus)
    """
    trades = []

    try:
        # Pre-populate market cache
        print("  Loading market data...")
        get_all_markets_batch()
        print(f"  Cached {len(TOKEN_TO_MARKET_CACHE)} token mappings")

        current_block = get_current_block()
        blocks_per_hour = 1800
        from_block = current_block - (hours * blocks_per_hour)

        print(f"  Scanning blocks {from_block:,} to {current_block:,}...")

        # Query all exchange contracts
        exchange_addresses = [
            CONTRACTS["ctf_exchange"],
            CONTRACTS["ctf_exchange_old"],
        ]

        # Use smaller chunks to avoid RPC limits
        chunk_size = 50
        all_logs = []

        for chunk_start in range(from_block, current_block, chunk_size):
            chunk_end = min(chunk_start + chunk_size - 1, current_block)

            for exchange in exchange_addresses:
                # Query OrderFilled events
                params = [{
                    "fromBlock": hex(chunk_start),
                    "toBlock": hex(chunk_end),
                    "address": exchange,
                    "topics": [ORDER_FILLED_TOPIC],
                }]

                result = rpc_call("eth_getLogs", params)
                if "error" not in result:
                    all_logs.extend(result.get("result", []))

            progress = (chunk_end - from_block) / (current_block - from_block) * 100
            print(f"  Progress: {progress:.0f}% ({len(all_logs)} OrderFilled events)", end="\r")

        print(f"  Found {len(all_logs)} OrderFilled events                    ")

        # Parse OrderFilled events
        # Event structure: OrderFilled(bytes32 orderHash, address maker, address taker,
        #                              uint256 makerAssetId, uint256 takerAssetId,
        #                              uint256 makerAmountFilled, uint256 takerAmountFilled, uint256 fee)
        for log in all_logs:
            try:
                topics = log.get("topics", [])
                data = log.get("data", "0x")

                if len(topics) < 4:
                    continue

                # Indexed: orderHash, maker, taker
                order_hash = topics[1]
                maker = "0x" + topics[2][26:].lower()
                taker = "0x" + topics[3][26:].lower()

                # Non-indexed data: makerAssetId, takerAssetId, makerAmountFilled, takerAmountFilled, fee
                # Each uint256 is 32 bytes (64 hex chars)
                if len(data) < 322:  # 0x + 5*64
                    continue

                data = data[2:]  # Remove 0x
                maker_asset_id = str(int(data[0:64], 16))
                taker_asset_id = str(int(data[64:128], 16))
                maker_amount = int(data[128:192], 16)
                taker_amount = int(data[192:256], 16)
                fee = int(data[256:320], 16)

                # Determine trade direction and value
                # If makerAssetId is 0, maker is selling USDC (buying outcome tokens)
                # Token amounts are in their native decimals (USDC = 6, CTF tokens = 6)
                if maker_asset_id == "0":
                    # Maker is spending USDC to buy taker_asset_id tokens
                    usdc_amount = maker_amount / 1_000_000
                    token_id = taker_asset_id
                    buyer = maker
                    side = "buy"
                    tokens_received = taker_amount / 1_000_000
                else:
                    # Maker is selling tokens for USDC
                    usdc_amount = taker_amount / 1_000_000
                    token_id = maker_asset_id
                    buyer = taker
                    side = "sell"
                    tokens_received = maker_amount / 1_000_000

                # Calculate price (probability)
                if tokens_received > 0:
                    price = usdc_amount / tokens_received
                else:
                    price = 0

                if usdc_amount < min_value_usd:
                    continue

                block_num = int(log.get("blockNumber", "0x0"), 16)

                # Get market info
                market_info = get_market_for_token(token_id)
                market_question = market_info.get("question", f"Token {token_id[:20]}...") if market_info else f"Token {token_id[:20]}..."

                # Filter out sports markets if requested
                if filter_sports and is_sports_market(market_question):
                    continue

                trades.append({
                    "tx_hash": log.get("transactionHash", ""),
                    "wallet": buyer,
                    "block": block_num,
                    "value_usd": usdc_amount,
                    "token_id": token_id,
                    "side": side,
                    "price": price,
                    "tokens": tokens_received,
                    "market": market_question,
                    "market_slug": market_info.get("slug", "") if market_info else "",
                })

            except Exception as e:
                continue

        # Get timestamps
        if trades:
            print(f"  Found {len(trades)} large trades (>= ${min_value_usd:,})")
            first_block_time = get_block_timestamp(trades[-1]["block"])
            last_block_time = get_block_timestamp(trades[0]["block"])

            for trade in trades:
                block_range = trades[0]["block"] - trades[-1]["block"]
                if block_range > 0:
                    time_range = (last_block_time - first_block_time).total_seconds()
                    block_offset = trade["block"] - trades[-1]["block"]
                    seconds_offset = (block_offset / block_range) * time_range
                    trade["timestamp"] = first_block_time + timedelta(seconds=seconds_offset)
                else:
                    trade["timestamp"] = last_block_time

        return trades

    except Exception as e:
        print(f"Error fetching OrderFilled trades: {e}")
        import traceback
        traceback.print_exc()
        return []


def get_recent_large_trades_rpc(hours: int = 24, min_value_usd: int = 5000) -> list[dict]:
    """
    Get recent large trades using direct RPC calls.
    Queries USDC Transfer events to Polymarket contracts.
    """
    trades = []

    try:
        # Get current block and estimate block from X hours ago
        # Polygon has ~2 second blocks, so ~1800 blocks/hour
        current_block = get_current_block()
        blocks_per_hour = 1800
        from_block = current_block - (hours * blocks_per_hour)

        print(f"  Scanning blocks {from_block:,} to {current_block:,}...")

        # Query in chunks (free RPCs have strict limits - use 100 blocks)
        chunk_size = 100
        all_logs = []

        for chunk_start in range(from_block, current_block, chunk_size):
            chunk_end = min(chunk_start + chunk_size - 1, current_block)

            # Query ALL USDC transfers in this chunk, filter locally
            params = [{
                "fromBlock": hex(chunk_start),
                "toBlock": hex(chunk_end),
                "address": CONTRACTS["usdc"],
                "topics": [USDC_TRANSFER_TOPIC],
            }]

            result = rpc_call("eth_getLogs", params)

            if "error" in result:
                print(f"  Warning: RPC error on blocks {chunk_start}-{chunk_end}: {result['error']}")
                continue

            chunk_logs = result.get("result", [])
            all_logs.extend(chunk_logs)

            # Progress indicator
            progress = (chunk_end - from_block) / (current_block - from_block) * 100
            print(f"  Progress: {progress:.0f}% ({len(all_logs)} transfers found)", end="\r")

        print(f"  Found {len(all_logs)} total USDC transfers                    ")

        # Filter for transfers TO Polymarket contracts
        polymarket_addrs = [addr.lower() for addr in CONTRACTS.values()]
        logs = []
        for log in all_logs:
            if len(log.get("topics", [])) >= 3:
                to_addr = "0x" + log["topics"][2][26:].lower()
                if to_addr in polymarket_addrs:
                    logs.append(log)

        print(f"  {len(logs)} transfers to Polymarket contracts")

        for log in logs:
            # Parse the transfer amount from data
            data = log.get("data", "0x0")
            value = int(data, 16) / 1_000_000  # USDC has 6 decimals

            if value >= min_value_usd:
                # Parse the "from" address from topics
                from_topic = log.get("topics", [None, None])[1]
                if from_topic:
                    wallet = "0x" + from_topic[26:]  # Remove padding

                block_num = int(log.get("blockNumber", "0x0"), 16)

                trades.append({
                    "tx_hash": log.get("transactionHash", ""),
                    "wallet": wallet,
                    "block": block_num,
                    "value_usd": value,
                })

        # Get timestamps for trades (batch for efficiency)
        if trades:
            print(f"  Found {len(trades)} large trades (>= ${min_value_usd:,})")
            # Get timestamp for first and last block to estimate
            first_block_time = get_block_timestamp(trades[-1]["block"])
            last_block_time = get_block_timestamp(trades[0]["block"])

            for trade in trades:
                # Estimate timestamp based on block position
                block_range = trades[0]["block"] - trades[-1]["block"]
                if block_range > 0:
                    time_range = (last_block_time - first_block_time).total_seconds()
                    block_offset = trade["block"] - trades[-1]["block"]
                    seconds_offset = (block_offset / block_range) * time_range
                    trade["timestamp"] = first_block_time + timedelta(seconds=seconds_offset)
                else:
                    trade["timestamp"] = last_block_time

        return trades

    except Exception as e:
        print(f"Error fetching trades via RPC: {e}")
        import traceback
        traceback.print_exc()
        return []


def get_recent_large_trades_polygonscan(hours: int = 24, min_value_usd: int = 5000) -> list[dict]:
    """Fallback: Use Polygonscan API (may be rate limited)."""
    # This is deprecated, use RPC method instead
    return get_recent_large_trades_rpc(hours, min_value_usd)


def analyze_wallet(wallet: str) -> WalletProfile:
    """Analyze a wallet's trading behavior and flag suspicious patterns."""

    # Get wallet's first transaction
    first_seen = get_wallet_first_tx(wallet)
    is_new = False
    if first_seen:
        age = datetime.now() - first_seen
        is_new = age.days < 7

    # Get wallet's token transfers (trades)
    try:
        url = "https://api.polygonscan.com/api"
        params = {
            "module": "account",
            "action": "tokentx",
            "address": wallet,
            "startblock": 0,
            "endblock": 99999999,
            "page": 1,
            "offset": 100,
            "sort": "asc",
        }
        response = requests.get(url, params=params, timeout=10)
        data = response.json()

        trades = []
        total_volume = 0
        markets = set()
        largest_trade = 0

        if data.get("status") == "1" and data.get("result"):
            for tx in data["result"]:
                # Only count USDC transfers to Polymarket
                to_addr = tx.get("to", "").lower()
                if to_addr in [c.lower() for c in CONTRACTS.values()]:
                    value = int(tx.get("value", 0)) / 1_000_000
                    total_volume += value
                    largest_trade = max(largest_trade, value)
                    trades.append({
                        "amount": value,
                        "timestamp": int(tx.get("timeStamp", 0)),
                        "market": tx.get("to", ""),
                    })

        # Check flags
        flags = check_wallet_flags(wallet, trades)

        # Check concentration
        is_concentrated = len(markets) == 1 and total_volume > 5000

        return WalletProfile(
            address=wallet,
            first_seen=first_seen,
            total_trades=len(trades),
            total_volume=total_volume,
            unique_markets=len(markets) if markets else 1,
            largest_trade=largest_trade,
            is_new=is_new,
            is_concentrated=is_concentrated,
            flags=flags,
        )

    except Exception as e:
        print(f"Error analyzing wallet: {e}")
        return WalletProfile(
            address=wallet,
            first_seen=None,
            total_trades=0,
            total_volume=0,
            unique_markets=0,
            largest_trade=0,
            is_new=False,
            is_concentrated=False,
            flags=[f"ERROR: {e}"],
        )


def detect_price_clustering(trades: list[dict]) -> bool:
    """Detect if trades are clustered at similar prices (accumulation pattern)."""
    if len(trades) < 3:
        return False

    prices = [t.get("price", 0) for t in trades if t.get("price", 0) > 0]
    if len(prices) < 3:
        return False

    # Check if prices are within 5% of each other
    avg_price = sum(prices) / len(prices)
    if avg_price == 0:
        return False

    for price in prices:
        if abs(price - avg_price) / avg_price > 0.05:
            return False

    return True


def scan_for_insiders(hours: int = 6, min_trade: int = 5000, political_only: bool = False) -> dict:
    """
    Full insider detection scan - tracks actual market positions.

    Detects:
    - New wallets (< 7 days) making large bets
    - Concentrated positions (80%+ in one market)
    - Price clustering (accumulation at similar prices)
    - Large single trades

    Args:
        hours: How far back to scan
        min_trade: Minimum trade size in USD
        political_only: If True, filter out sports markets to focus on political/news
    """
    print(f"INSIDER DETECTION SCAN")
    if political_only:
        print(f"MODE: Political/News markets only (sports filtered out)")
    print(f"Scanning last {hours} hours for trades >= ${min_trade:,}")
    print()

    # Get actual OrderFilled trades with market info
    trades = get_order_filled_trades(hours=hours, min_value_usd=min_trade, filter_sports=political_only)

    if not trades:
        print("No trades found in the specified time range.")
        return {"flagged": [], "all_whales": [], "by_market": {}}

    print()

    # Group by wallet
    wallets = {}
    for trade in trades:
        wallet = trade.get("wallet", "unknown")
        if wallet not in wallets:
            wallets[wallet] = {
                "trades": [],
                "total_volume": 0,
                "markets": {},
            }
        wallets[wallet]["trades"].append(trade)
        wallets[wallet]["total_volume"] += trade.get("value_usd", 0)

        # Track per-market volume
        market = trade.get("market", "unknown")
        if market not in wallets[wallet]["markets"]:
            wallets[wallet]["markets"][market] = {
                "volume": 0,
                "trades": [],
                "prices": [],
            }
        wallets[wallet]["markets"][market]["volume"] += trade.get("value_usd", 0)
        wallets[wallet]["markets"][market]["trades"].append(trade)
        wallets[wallet]["markets"][market]["prices"].append(trade.get("price", 0))

    print(f"Analyzing {len(wallets)} unique wallets...")

    # Analyze each wallet for suspicious patterns
    flagged = []
    all_whales = []

    for wallet, data in wallets.items():
        if data["total_volume"] < min_trade:
            continue

        flags = []
        markets_traded = list(data["markets"].keys())

        # 1. Check for concentration (80%+ in one market)
        for market, mdata in data["markets"].items():
            concentration = mdata["volume"] / data["total_volume"]
            if concentration >= 0.8:
                flags.append(f"CONCENTRATED ({concentration:.0%} in '{market[:40]}...')")
                break

        # 2. Check for large single trades
        max_trade = max(t.get("value_usd", 0) for t in data["trades"])
        if max_trade >= 10000:
            flags.append(f"LARGE_TRADE (${max_trade:,.0f})")

        # 3. Check for price clustering in any market
        for market, mdata in data["markets"].items():
            if detect_price_clustering(mdata["trades"]):
                avg_price = sum(mdata["prices"]) / len(mdata["prices"])
                flags.append(f"PRICE_CLUSTER ({avg_price:.1%} avg in '{market[:30]}...')")
                break

        # 4. Multiple trades (accumulation)
        if len(data["trades"]) >= 3:
            flags.append(f"ACCUMULATION ({len(data['trades'])} trades)")

        # 5. Single market focus (only traded one market)
        if len(markets_traded) == 1:
            flags.append(f"SINGLE_MARKET_FOCUS")

        whale_entry = {
            "wallet": wallet,
            "flags": flags,
            "recent_trades": data["trades"],
            "recent_volume": data["total_volume"],
            "trade_count": len(data["trades"]),
            "markets": markets_traded,
            "market_breakdown": data["markets"],
        }

        all_whales.append(whale_entry)
        if flags:
            flagged.append(whale_entry)

    # Sort by volume
    all_whales.sort(key=lambda x: x["recent_volume"], reverse=True)
    flagged.sort(key=lambda x: x["recent_volume"], reverse=True)

    # Group by market for market-level analysis
    by_market = {}
    for trade in trades:
        market = trade.get("market", "unknown")
        if market not in by_market:
            by_market[market] = {
                "volume": 0,
                "trades": [],
                "wallets": set(),
            }
        by_market[market]["volume"] += trade.get("value_usd", 0)
        by_market[market]["trades"].append(trade)
        by_market[market]["wallets"].add(trade.get("wallet", ""))

    # Convert sets to counts
    for market in by_market:
        by_market[market]["wallet_count"] = len(by_market[market]["wallets"])
        del by_market[market]["wallets"]

    return {"flagged": flagged, "all_whales": all_whales, "by_market": by_market}


def scan_for_whales(hours: int = 24, min_trade: int = 5000) -> list[dict]:
    """
    Scan recent trades and flag suspicious wallets (legacy method using USDC transfers).

    Returns list of flagged wallets with their patterns.
    """
    print(f"Scanning for large trades in last {hours} hours (min ${min_trade:,})...")
    print()

    # Get recent large trades via RPC
    trades = get_recent_large_trades_rpc(hours=hours, min_value_usd=min_trade)

    if not trades:
        print("No large trades found in the specified time range.")
        return []

    print()

    # Analyze unique wallets
    wallets = {}
    for trade in trades:
        wallet = trade.get("wallet", "unknown")
        if wallet not in wallets:
            wallets[wallet] = {
                "trades": [],
                "total_volume": 0,
            }
        wallets[wallet]["trades"].append(trade)
        wallets[wallet]["total_volume"] += trade.get("value_usd", 0)

    print(f"Analyzing {len(wallets)} unique wallets...")

    # Analyze wallets and flag suspicious ones
    flagged = []
    all_whales = []

    for wallet, data in wallets.items():
        # Skip if volume is too low
        if data["total_volume"] < min_trade:
            continue

        # Check for basic whale indicators without API calls
        flags = []

        # Large single trades
        max_trade = max(t.get("value_usd", 0) for t in data["trades"])
        if max_trade >= 10000:
            flags.append(f"LARGE_TRADE (${max_trade:,.0f})")

        # Multiple trades in short time (accumulation)
        if len(data["trades"]) >= 3:
            flags.append(f"MULTIPLE_TRADES ({len(data['trades'])} trades)")

        whale_entry = {
            "wallet": wallet,
            "flags": flags,
            "recent_trades": data["trades"],
            "recent_volume": data["total_volume"],
            "trade_count": len(data["trades"]),
        }

        all_whales.append(whale_entry)

        if flags:
            flagged.append(whale_entry)

    # Sort by volume
    all_whales.sort(key=lambda x: x["recent_volume"], reverse=True)
    flagged.sort(key=lambda x: x["recent_volume"], reverse=True)

    return {"flagged": flagged, "all_whales": all_whales}


def print_insider_report(results: dict) -> None:
    """Print a detailed insider detection report."""

    if not results:
        print("No data to report.")
        return

    flagged = results.get("flagged", [])
    all_whales = results.get("all_whales", [])
    by_market = results.get("by_market", {})

    print()
    print("=" * 75)
    print("INSIDER DETECTION REPORT")
    print("=" * 75)

    # Summary stats
    total_volume = sum(w["recent_volume"] for w in all_whales)
    print(f"\nTotal wallets analyzed: {len(all_whales)}")
    print(f"Total volume: ${total_volume:,.0f}")
    print(f"Flagged as suspicious: {len(flagged)}")

    # Hot markets (most volume)
    if by_market:
        print("\n" + "-" * 75)
        print("HOT MARKETS (by volume)")
        print("-" * 75)

        sorted_markets = sorted(by_market.items(), key=lambda x: x[1]["volume"], reverse=True)
        for i, (market, mdata) in enumerate(sorted_markets[:5], 1):
            vol = mdata["volume"]
            trades = len(mdata["trades"])
            wallets = mdata["wallet_count"]
            print(f"\n[{i}] {market[:65]}")
            print(f"    Volume: ${vol:,.0f} | Trades: {trades} | Unique wallets: {wallets}")

    # Flagged wallets with full details
    if flagged:
        print("\n" + "-" * 75)
        print("FLAGGED WALLETS (Suspicious Patterns Detected)")
        print("-" * 75)

        for i, item in enumerate(flagged[:10], 1):
            wallet = item["wallet"]
            short_wallet = f"{wallet[:8]}...{wallet[-6:]}"

            print(f"\n{'='*40}")
            print(f"[{i}] {short_wallet}")
            print(f"    Volume: ${item['recent_volume']:,.0f} | Trades: {item['trade_count']}")

            if item.get("flags"):
                print(f"\n    RED FLAGS:")
                for flag in item["flags"]:
                    print(f"      ⚠ {flag}")

            # Show market breakdown
            if item.get("market_breakdown"):
                print(f"\n    POSITIONS:")
                for market, mdata in item["market_breakdown"].items():
                    vol = mdata["volume"]
                    trades_count = len(mdata["trades"])
                    if mdata["prices"]:
                        avg_price = sum(mdata["prices"]) / len(mdata["prices"])
                        print(f"      • {market[:50]}")
                        print(f"        ${vol:,.0f} | {trades_count} trades | avg price: {avg_price:.1%}")

            # Show recent trades with market context
            print(f"\n    RECENT TRADES:")
            for trade in item["recent_trades"][:5]:
                if "timestamp" in trade:
                    time_str = trade["timestamp"].strftime("%m/%d %H:%M")
                else:
                    time_str = f"Block {trade.get('block', 'N/A')}"
                market = trade.get("market", "Unknown")[:40]
                price = trade.get("price", 0)
                side = trade.get("side", "?")
                print(f"      {time_str} | ${trade.get('value_usd', 0):>10,.0f} | {side.upper():4} @ {price:.1%} | {market}")

            print(f"\n    Polygonscan: https://polygonscan.com/address/{wallet}")

    # Summary for non-flagged whales
    non_flagged = [w for w in all_whales if w not in flagged]
    if non_flagged:
        print("\n" + "-" * 75)
        print(f"OTHER LARGE TRADERS ({len(non_flagged)} wallets, no flags)")
        print("-" * 75)

        for whale in non_flagged[:5]:
            wallet = whale["wallet"]
            short_wallet = f"{wallet[:8]}...{wallet[-6:]}"
            print(f"  {short_wallet} | ${whale['recent_volume']:,.0f} | {whale['trade_count']} trades")


def print_whale_report(results: dict) -> None:
    """Print a formatted report of whale activity (legacy format)."""

    if not results:
        print("No data to report.")
        return

    flagged = results.get("flagged", [])
    all_whales = results.get("all_whales", [])

    print()
    print("=" * 70)
    print("WHALE TRACKER REPORT")
    print("=" * 70)

    # Summary stats
    total_volume = sum(w["recent_volume"] for w in all_whales)
    print(f"\nTotal large trades found: {len(all_whales)} wallets")
    print(f"Total volume: ${total_volume:,.0f}")
    print(f"Flagged as suspicious: {len(flagged)}")

    # Top whales by volume
    print("\n" + "-" * 70)
    print("TOP WHALES BY VOLUME")
    print("-" * 70)

    for i, whale in enumerate(all_whales[:10], 1):
        wallet = whale["wallet"]
        short_wallet = f"{wallet[:8]}...{wallet[-6:]}"
        volume = whale["recent_volume"]
        trades = whale["trade_count"]
        flags = whale.get("flags", [])

        flag_str = " | ".join(flags) if flags else ""

        print(f"\n[{i}] {short_wallet}")
        print(f"    Volume: ${volume:,.0f} | Trades: {trades}")
        if flag_str:
            print(f"    FLAGS: {flag_str}")
        print(f"    View: https://polygonscan.com/address/{wallet}")

    # Flagged wallets (if different from top)
    if flagged:
        print("\n" + "-" * 70)
        print("FLAGGED WALLETS (Suspicious Patterns)")
        print("-" * 70)

        for i, item in enumerate(flagged[:10], 1):
            wallet = item["wallet"]
            short_wallet = f"{wallet[:8]}...{wallet[-6:]}"

            print(f"\n[{i}] {short_wallet}")
            print(f"    Volume: ${item['recent_volume']:,.0f}")

            if item.get("flags"):
                print(f"    FLAGS:")
                for flag in item["flags"]:
                    print(f"      - {flag}")

            print(f"    Recent trades:")
            for trade in item["recent_trades"][:3]:
                if "timestamp" in trade:
                    time_str = trade["timestamp"].strftime("%Y-%m-%d %H:%M")
                else:
                    time_str = f"Block {trade.get('block', 'N/A')}"
                print(f"      {time_str} | ${trade.get('value_usd', 0):,.0f}")

            print(f"    Polygonscan: https://polygonscan.com/address/{wallet}")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Polymarket Whale & Insider Tracker",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python whale_tracker.py --insider               # Full insider detection scan
  python whale_tracker.py --insider --hours 12    # Scan last 12 hours
  python whale_tracker.py --insider --political   # Political/news markets only (no sports)
  python whale_tracker.py --hours 6               # Basic whale scan (USDC transfers)
  python whale_tracker.py --wallet 0x123...       # Analyze specific wallet
        """
    )
    parser.add_argument("--hours", type=int, default=1, help="Hours to scan (default: 1)")
    parser.add_argument("--min-trade", type=int, default=5000, help="Minimum trade size in USD (default: 5000)")
    parser.add_argument("--wallet", type=str, help="Analyze a specific wallet address")
    parser.add_argument("--insider", action="store_true", help="Run full insider detection (tracks actual market positions)")
    parser.add_argument("--political", action="store_true", help="Filter out sports markets, focus on political/news/crypto (use with --insider)")

    args = parser.parse_args()

    print("=" * 75)
    print("POLYMARKET WHALE & INSIDER TRACKER")
    print("=" * 75)
    print()

    if args.wallet:
        # Analyze specific wallet
        print(f"Analyzing wallet: {args.wallet}")
        profile = analyze_wallet(args.wallet)
        print(f"\nWallet: {profile.address[:10]}...{profile.address[-6:]}")
        print(f"First seen: {profile.first_seen}")
        print(f"Total trades: {profile.total_trades}")
        print(f"Total volume: ${profile.total_volume:,.0f}")
        print(f"Largest trade: ${profile.largest_trade:,.0f}")
        print(f"Is new wallet: {profile.is_new}")
        if profile.flags:
            print(f"Flags: {', '.join(profile.flags)}")

    elif args.insider:
        # Full insider detection scan
        results = scan_for_insiders(hours=args.hours, min_trade=args.min_trade, political_only=args.political)
        print_insider_report(results)

    else:
        # Basic whale scan (USDC transfers)
        results = scan_for_whales(hours=args.hours, min_trade=args.min_trade)
        print_whale_report(results)

    print()
    print("=" * 75)
    print("Scan complete.")
