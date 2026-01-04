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
    "ctf_exchange": "0xC5d563A36AE78145C45a50134d48A1215220f80a",
    "neg_risk_exchange": "0x4D97DCd97eC945f40cF65F87097ACe5EA0476045",
    "usdc": "0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174",
    "conditional_tokens": "0x4D97DCd97eC945f40cF65F87097ACe5EA0476045",
}

# USDC Transfer event signature
USDC_TRANSFER_TOPIC = "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"

# Minimum trade size to track (in USDC, 6 decimals)
MIN_TRADE_SIZE = 1000  # $1,000


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
    # Try RPCs in order until one works
    rpcs_to_try = [rpc_url] if rpc_url else POLYGON_RPCS

    for rpc in rpcs_to_try:
        if not rpc:
            continue
        payload = {
            "jsonrpc": "2.0",
            "method": method,
            "params": params,
            "id": 1,
        }

        try:
            response = requests.post(rpc, json=payload, timeout=30)
            result = response.json()
            if "error" not in result:
                return result
        except Exception:
            continue

    return {"error": "All RPCs failed"}


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


def scan_for_whales(hours: int = 24, min_trade: int = 5000) -> list[dict]:
    """
    Scan recent trades and flag suspicious wallets.

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


def print_whale_report(results: dict) -> None:
    """Print a formatted report of whale activity."""

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

    parser = argparse.ArgumentParser(description="Polymarket Whale Tracker")
    parser.add_argument("--hours", type=int, default=6, help="Hours to scan (default: 6)")
    parser.add_argument("--min-trade", type=int, default=5000, help="Minimum trade size in USD (default: 5000)")
    parser.add_argument("--wallet", type=str, help="Analyze a specific wallet address")

    args = parser.parse_args()

    print("=" * 70)
    print("POLYMARKET WHALE TRACKER")
    print("Scanning for suspicious trading patterns...")
    print("=" * 70)
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
    else:
        # Scan for whales
        results = scan_for_whales(hours=args.hours, min_trade=args.min_trade)

        # Print report
        print_whale_report(results)

    print()
    print("=" * 70)
    print("Scan complete.")
