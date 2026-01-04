"""
Polymarket API Client
Connects to Polymarket's Gamma API to fetch prediction market data.
"""

import json
import requests

BASE_URL = "https://gamma-api.polymarket.com"


def get_markets(limit: int = 10, active: bool = True, closed: bool = False) -> list:
    """
    Fetch markets from Polymarket.

    Args:
        limit: Number of markets to fetch
        active: Include active markets
        closed: Include closed markets

    Returns:
        List of market dictionaries
    """
    params = {
        "limit": limit,
        "active": str(active).lower(),
        "closed": str(closed).lower(),
    }

    response = requests.get(f"{BASE_URL}/markets", params=params)
    response.raise_for_status()
    return response.json()


def get_market_by_id(market_id: str) -> dict:
    """Fetch a specific market by its ID."""
    response = requests.get(f"{BASE_URL}/markets/{market_id}")
    response.raise_for_status()
    return response.json()


def get_events(limit: int = 10) -> list:
    """Fetch events from Polymarket."""
    params = {"limit": limit}
    response = requests.get(f"{BASE_URL}/events", params=params)
    response.raise_for_status()
    return response.json()


def search_markets(query: str, limit: int = 10) -> list:
    """Search for markets by keyword."""
    params = {"q": query, "limit": limit}
    response = requests.get(f"{BASE_URL}/markets", params=params)
    response.raise_for_status()
    return response.json()


def parse_json_field(field: str) -> list:
    """Parse a JSON string field."""
    try:
        return json.loads(field) if isinstance(field, str) else field
    except (json.JSONDecodeError, TypeError):
        return []


def get_active_events(limit: int = 10) -> list:
    """Fetch active events with their markets."""
    params = {
        "limit": limit,
        "active": "true",
        "closed": "false",
    }
    response = requests.get(f"{BASE_URL}/events", params=params)
    response.raise_for_status()
    return response.json()


def display_market(market: dict, indent: str = "   ") -> None:
    """Display a single market's info."""
    question = market.get("question", "N/A")
    outcome_prices = parse_json_field(market.get("outcomePrices", "[]"))
    volume = market.get("volumeNum", 0) or float(market.get("volume", 0) or 0)

    print(f"{indent}{question}")
    if outcome_prices and len(outcome_prices) >= 2:
        try:
            yes_price = float(outcome_prices[0])
            print(f"{indent}  → Yes: {yes_price:.1%} | Volume: ${volume:,.0f}")
        except (ValueError, IndexError):
            pass


if __name__ == "__main__":
    print("=" * 60)
    print("POLYMARKET - Active Prediction Markets")
    print("=" * 60)

    try:
        events = get_active_events(limit=5)

        for i, event in enumerate(events, 1):
            title = event.get("title", "N/A")
            volume = event.get("volume", 0)
            markets = event.get("markets", [])

            print(f"\n{i}. {title}")
            print(f"   Total Volume: ${float(volume):,.0f}")

            # Show top markets in this event (by price/probability)
            if markets:
                sorted_markets = sorted(
                    markets,
                    key=lambda m: float(parse_json_field(m.get("outcomePrices", "[0]"))[0] or 0),
                    reverse=True,
                )
                for market in sorted_markets[:3]:
                    display_market(market)

        print("\n" + "=" * 60)

    except requests.exceptions.RequestException as e:
        print(f"Error connecting to Polymarket API: {e}")
