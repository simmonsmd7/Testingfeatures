# Polymarket Insider Detection System

A blockchain analysis toolkit for detecting suspicious trading patterns on Polymarket prediction markets. Inspired by community research that identified wallets front-running major news events by loading heavily into specific markets hours before information became public.

## Background

Polymarket is a prediction market platform running on Polygon where users trade YES/NO outcome tokens. The market price (e.g., 65 cents for YES) represents the crowd's probability estimate (65% chance of happening).

This toolkit monitors on-chain trading activity to flag patterns that may indicate informed trading:

- **Fresh wallets** making five-figure first entries
- **Hyper-focused positions** concentrated on a single market
- **Tight clustered buys** at similar prices (accumulation)
- **Large sudden bets** without prior trading history

## Components

### 1. `polymarket_client.py` - Market Data API

Connects to Polymarket's Gamma API to fetch market data.

```bash
python polymarket_client.py
```

**Features:**
- Fetch active markets and events
- Search markets by keyword
- Display current prices and volumes
- Parse outcome probabilities

**Key Functions:**
- `get_markets()` - Fetch market list
- `get_events()` - Fetch events with associated markets
- `search_markets(query)` - Search by keyword
- `get_active_events()` - Get currently active events

### 2. `whale_tracker.py` - Insider Detection Scanner

Monitors Polygon blockchain for suspicious Polymarket trading patterns.

```bash
# Full insider detection scan (recommended)
python whale_tracker.py --insider

# Political/news markets only - filters out sports betting
python whale_tracker.py --insider --political

# Scan last 6 hours for trades > $10k on political markets
python whale_tracker.py --insider --political --hours 6 --min-trade 10000

# Basic scan using USDC transfers only
python whale_tracker.py --hours 24

# Analyze a specific wallet
python whale_tracker.py --wallet 0x1234...
```

The `--political` flag is key for catching real insider trading like the Maduro example. Sports betting generates tons of large trades that aren't insider activity - filtering these out reveals the political/news/crypto markets where informed trading is more likely.

## Detection Patterns

The scanner flags wallets exhibiting these behaviors:

| Flag | Description |
|------|-------------|
| `CONCENTRATED` | 80%+ of volume in a single market |
| `LARGE_TRADE` | Single trade ≥ $10,000 |
| `PRICE_CLUSTER` | Multiple buys within 5% of average price |
| `ACCUMULATION` | 3+ trades (building position) |
| `SINGLE_MARKET_FOCUS` | Only traded one market |
| `NEW_WALLET` | Wallet less than 7 days old |
| `LARGE_FIRST_TRADE` | First trade > $5,000 |
| `RAPID_ACCUMULATION` | $10k+ volume in under 1 hour |

## How It Works

### Data Sources

1. **Polymarket Gamma API** - Market metadata (questions, prices, token IDs)
2. **Polygon RPC** - On-chain OrderFilled events from CTF Exchange contracts
3. **Polygonscan API** - Wallet age lookup (rate limited without API key)

### Contract Addresses (Polygon)

| Contract | Address |
|----------|---------|
| CTF Exchange | `0x4bfb41d5b3570defd03c39a9a4d8de6bd8b8982e` |
| CTF Exchange (Legacy) | `0xC5d563A36AE78145C45a50134d48A1215220f80a` |
| NegRisk Exchange | `0x4D97DCd97eC945f40cF65F87097ACe5EA0476045` |
| USDC | `0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174` |

### Event Parsing

The scanner queries `OrderFilled` events from the CTF Exchange:

```
OrderFilled(
    bytes32 indexed orderHash,
    address indexed maker,
    address indexed taker,
    uint256 makerAssetId,
    uint256 takerAssetId,
    uint256 makerAmountFilled,
    uint256 takerAmountFilled,
    uint256 fee
)
```

Token IDs are mapped to market questions via the Gamma API to show which markets each wallet is trading.

## Sample Output

```
INSIDER DETECTION REPORT
===========================================================================

Total wallets analyzed: 86
Total volume: $3,412,847
Flagged as suspicious: 80

---------------------------------------------------------------------------
HOT MARKETS (by volume)
---------------------------------------------------------------------------

[1] Will the Ravens beat the spread (-3.5) vs Texans?
    Volume: $847,293 | Trades: 42 | Unique wallets: 18

[2] Will the Chargers beat the Broncos?
    Volume: $523,891 | Trades: 31 | Unique wallets: 12

---------------------------------------------------------------------------
FLAGGED WALLETS (Suspicious Patterns Detected)
---------------------------------------------------------------------------

[1] 0x7a3f...8c2e1d
    Volume: $127,450 | Trades: 8

    RED FLAGS:
      ⚠ CONCENTRATED (94% in 'Will the Ravens beat the spread...')
      ⚠ LARGE_TRADE ($45,000)
      ⚠ PRICE_CLUSTER (67.2% avg in 'Will the Ravens...')
      ⚠ ACCUMULATION (8 trades)
      ⚠ SINGLE_MARKET_FOCUS

    POSITIONS:
      • Will the Ravens beat the spread (-3.5) vs Texans?
        $127,450 | 8 trades | avg price: 67.2%

    Polygonscan: https://polygonscan.com/address/0x7a3f...
```

## Limitations

1. **Wallet age detection** requires Polygonscan API key for reliable lookups (free tier is rate limited)
2. **No historical baseline** - cannot compare to "normal" trading patterns for each wallet
3. **Sports betting noise** - high-volume sports markets generate many large trades that aren't necessarily insider activity
4. **RPC rate limits** - free Polygon RPCs limit query size, requiring chunked requests

## Potential Improvements

- Filter for political/news markets vs sports (different insider dynamics)
- Add webhook/cron support for 24/7 monitoring
- Alert system for real-time notifications
- Historical database to track wallet behavior over time
- Correlation with news timestamps to identify pre-news accumulation

## Installation

```bash
pip install -r requirements.txt
```

**Requirements:**
- Python 3.8+
- `requests` library

## Legal Note

This tool analyzes publicly available blockchain data for research and market analysis purposes. All transaction data on Polygon is public and freely accessible.
