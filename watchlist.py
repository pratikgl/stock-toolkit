"""Watchlist manager — tracks which stocks to monitor and with which strategies."""

import json
from pathlib import Path
from tabulate import tabulate

WATCHLIST_PATH = Path(__file__).parent / "watchlist.json"


def _load() -> dict:
    if not WATCHLIST_PATH.exists():
        return {"stocks": {}}
    with open(WATCHLIST_PATH) as f:
        return json.load(f)


def _save(data: dict):
    with open(WATCHLIST_PATH, "w") as f:
        json.dump(data, f, indent=2)


def add_stock(ticker: str, strategies: list[str] | None = None, notes: str = ""):
    data = _load()
    ticker = ticker.upper()
    data["stocks"][ticker] = {
        "strategies": strategies or ["rsi", "momentum", "dip-buyer"],
        "notes": notes,
        "active": True,
    }
    _save(data)
    print(f"Added {ticker} to watchlist (strategies: {', '.join(data['stocks'][ticker]['strategies'])})")


def remove_stock(ticker: str):
    data = _load()
    ticker = ticker.upper()
    if ticker in data["stocks"]:
        del data["stocks"][ticker]
        _save(data)
        print(f"Removed {ticker} from watchlist")
    else:
        print(f"{ticker} not in watchlist")


def get_watchlist() -> dict:
    return _load()["stocks"]


def display_watchlist():
    stocks = get_watchlist()
    if not stocks:
        print("Watchlist is empty. Add stocks with: main.py alerts add AAPL")
        return

    rows = []
    for ticker, info in stocks.items():
        rows.append([
            ticker,
            ", ".join(info["strategies"]),
            "Yes" if info.get("active", True) else "No",
            info.get("notes", ""),
        ])

    print(f"\nWatchlist ({len(rows)} stocks):\n")
    print(tabulate(rows, headers=["Ticker", "Strategies", "Active", "Notes"], tablefmt="simple"))
    print()


def add_preset_watchlist(preset: str = "top30"):
    presets = {
        "top30": [
            "AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META", "TSLA",
            "BRK-B", "JPM", "V", "UNH", "JNJ", "WMT", "PG", "MA",
            "HD", "XOM", "COST", "ABBV", "CRM", "AMD", "NFLX", "ADBE",
            "LLY", "MRK", "PEP", "KO", "AVGO", "TMO", "ORCL",
        ],
        "tech": [
            "AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META", "TSLA",
            "CRM", "AMD", "NFLX", "ADBE", "AVGO", "ORCL", "INTC", "UBER",
        ],
        "dividend": [
            "JNJ", "PG", "KO", "PEP", "WMT", "XOM", "ABBV",
            "MRK", "VZ", "T", "IBM", "MMM", "CVX", "MO",
        ],
    }

    if preset not in presets:
        print(f"Unknown preset. Available: {', '.join(presets.keys())}")
        return

    tickers = presets[preset]
    for t in tickers:
        add_stock(t)
    print(f"\nAdded {len(tickers)} stocks from '{preset}' preset")
