"""Portfolio tracker — track holdings, P&L in USD and INR."""

import json
from datetime import datetime
from pathlib import Path

import yfinance as yf
import pandas as pd
from tabulate import tabulate

PORTFOLIO_PATH = Path(__file__).parent / "portfolio.json"


def _load() -> dict:
    if not PORTFOLIO_PATH.exists():
        return {"holdings": [], "transactions": []}
    with open(PORTFOLIO_PATH) as f:
        return json.load(f)


def _save(data: dict):
    with open(PORTFOLIO_PATH, "w") as f:
        json.dump(data, f, indent=2)


def _get_usd_inr() -> float:
    try:
        ticker = yf.Ticker("USDINR=X")
        return ticker.info.get("regularMarketPrice") or ticker.info.get("previousClose", 85.0)
    except Exception:
        return 85.0


def buy(ticker: str, shares: float, price: float, date: str | None = None):
    data = _load()
    txn = {
        "type": "buy",
        "ticker": ticker.upper(),
        "shares": shares,
        "price": price,
        "date": date or datetime.now().strftime("%Y-%m-%d"),
        "timestamp": datetime.now().isoformat(),
    }
    data["transactions"].append(txn)

    existing = next((h for h in data["holdings"] if h["ticker"] == ticker.upper()), None)
    if existing:
        total_cost = existing["avg_cost"] * existing["shares"] + price * shares
        existing["shares"] += shares
        existing["avg_cost"] = total_cost / existing["shares"]
    else:
        data["holdings"].append({
            "ticker": ticker.upper(),
            "shares": shares,
            "avg_cost": price,
            "first_buy": date or datetime.now().strftime("%Y-%m-%d"),
        })

    _save(data)
    print(f"Bought {shares} shares of {ticker.upper()} at ${price:.2f}")


def sell(ticker: str, shares: float, price: float, date: str | None = None):
    data = _load()
    ticker = ticker.upper()

    existing = next((h for h in data["holdings"] if h["ticker"] == ticker), None)
    if not existing:
        print(f"No holding found for {ticker}")
        return
    if existing["shares"] < shares:
        print(f"Only {existing['shares']:.4f} shares available, can't sell {shares}")
        return

    txn = {
        "type": "sell",
        "ticker": ticker,
        "shares": shares,
        "price": price,
        "cost_basis": existing["avg_cost"],
        "pnl": (price - existing["avg_cost"]) * shares,
        "date": date or datetime.now().strftime("%Y-%m-%d"),
        "timestamp": datetime.now().isoformat(),
    }
    data["transactions"].append(txn)

    existing["shares"] -= shares
    if existing["shares"] < 0.0001:
        data["holdings"] = [h for h in data["holdings"] if h["ticker"] != ticker]

    _save(data)
    pnl = txn["pnl"]
    print(f"Sold {shares} shares of {ticker} at ${price:.2f} (P&L: ${pnl:+.2f})")


def show_portfolio():
    data = _load()
    holdings = data.get("holdings", [])
    if not holdings:
        print("Portfolio is empty. Add holdings with: main.py portfolio buy AAPL 10 150.00")
        return

    usd_inr = _get_usd_inr()
    tickers = [h["ticker"] for h in holdings]

    print("Fetching live prices...")
    prices = {}
    for t in tickers:
        try:
            stock = yf.Ticker(t)
            hist = stock.history(period="2d")
            if not hist.empty:
                prices[t] = {
                    "price": hist["Close"].iloc[-1],
                    "prev": hist["Close"].iloc[-2] if len(hist) > 1 else hist["Close"].iloc[-1],
                }
        except Exception:
            pass

    rows = []
    total_invested = 0
    total_value_usd = 0
    total_pnl = 0

    for h in holdings:
        t = h["ticker"]
        shares = h["shares"]
        avg_cost = h["avg_cost"]
        invested = avg_cost * shares

        p = prices.get(t)
        if not p:
            continue

        current = p["price"]
        prev = p["prev"]
        value = current * shares
        pnl = value - invested
        pnl_pct = (current / avg_cost - 1) * 100
        day_change = (current / prev - 1) * 100

        total_invested += invested
        total_value_usd += value
        total_pnl += pnl

        rows.append([
            t,
            f"{shares:.4f}" if shares < 1 else f"{shares:.2f}",
            f"${avg_cost:.2f}",
            f"${current:.2f}",
            f"${value:.2f}",
            f"${pnl:+.2f}",
            f"{pnl_pct:+.1f}%",
            f"{day_change:+.1f}%",
        ])

    total_value_inr = total_value_usd * usd_inr
    total_invested_inr = total_invested * usd_inr
    total_pnl_inr = total_pnl * usd_inr
    total_pnl_pct = (total_value_usd / total_invested - 1) * 100 if total_invested > 0 else 0

    print(f"\n{'='*90}")
    print(f"  PORTFOLIO")
    print(f"  USD/INR: {usd_inr:.2f}")
    print(f"{'='*90}")

    print(tabulate(
        rows,
        headers=["Ticker", "Shares", "Avg Cost", "Price", "Value", "P&L ($)", "P&L (%)", "1D (%)"],
        tablefmt="simple",
    ))

    print(f"\n{'─'*90}")
    print(f"  {'TOTAL':52s}  ${total_value_usd:>9.2f}  ${total_pnl:>+9.2f}  {total_pnl_pct:+.1f}%")
    print(f"\n  USD Values")
    print(f"    Invested:    ${total_invested:>12,.2f}")
    print(f"    Current:     ${total_value_usd:>12,.2f}")
    print(f"    P&L:         ${total_pnl:>+12,.2f} ({total_pnl_pct:+.1f}%)")
    print(f"\n  INR Values (@ {usd_inr:.2f})")
    print(f"    Invested:    Rs.{total_invested_inr:>12,.0f}")
    print(f"    Current:     Rs.{total_value_inr:>12,.0f}")
    print(f"    P&L:         Rs.{total_pnl_inr:>+12,.0f}")
    print()


def show_transactions(last_n: int = 20):
    data = _load()
    txns = data.get("transactions", [])
    if not txns:
        print("No transactions yet.")
        return

    rows = []
    for t in txns[-last_n:]:
        row = [
            t["date"],
            t["type"].upper(),
            t["ticker"],
            f"{t['shares']:.4f}" if t["shares"] < 1 else f"{t['shares']:.2f}",
            f"${t['price']:.2f}",
            f"${t['shares'] * t['price']:.2f}",
        ]
        if t["type"] == "sell" and "pnl" in t:
            row.append(f"${t['pnl']:+.2f}")
        else:
            row.append("")
        rows.append(row)

    print(f"\nTransaction History (last {last_n}):\n")
    print(tabulate(
        rows,
        headers=["Date", "Type", "Ticker", "Shares", "Price", "Total", "P&L"],
        tablefmt="simple",
    ))
    print()
