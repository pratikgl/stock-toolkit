"""Strategy performance tests — validates signals against historical data.

Tests 3 time windows:
  - Month 1: signals from last 22 trading days, measured to today
  - Month 2: signals from days 44-22, measured to day 22
  - Month 3: signals from days 66-44, measured to day 44

For each window: what signals fired, and did the price go up after?
"""

import sys
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

import yfinance as yf
import pandas as pd
from ta.momentum import RSIIndicator
from ta.trend import MACD
from ta.volatility import BollingerBands

from strategies import STRATEGIES
from sp500 import get_sp500_tickers

SAMPLE_SIZE = 150  # test on 150 stocks (extrapolate to 500)
TRADE_AMOUNT = 300  # $300 per trade


def _precompute(hist: pd.DataFrame) -> pd.DataFrame:
    df = hist.copy()
    close = df["Close"]
    volume = df["Volume"]
    df["rsi"] = RSIIndicator(close, window=14).rsi()
    df["sma_20"] = close.rolling(20).mean()
    df["sma_50"] = close.rolling(50).mean()
    df["sma_200"] = close.rolling(200).mean()
    macd = MACD(close)
    df["macd"] = macd.macd()
    df["macd_signal"] = macd.macd_signal()
    df["macd_hist"] = macd.macd_diff()
    bb = BollingerBands(close, window=20)
    df["bb_upper"] = bb.bollinger_hband()
    df["bb_lower"] = bb.bollinger_lband()
    df["vol_ma20"] = volume.rolling(20).mean()
    return df


def _simulate_ticker(ticker: str, df: pd.DataFrame, signal_start: int, signal_end: int, exit_idx: int):
    """Find signals in [signal_start, signal_end), measure at exit_idx."""
    results = []
    all_strats = list(STRATEGIES.keys())

    for i in range(signal_start, signal_end):
        if i < 200 or i >= len(df):
            continue
        row = df.iloc[i]
        lookback = df.iloc[:i + 1]
        date = str(row.name.date())
        price = row["Close"]

        buy_strats = set()
        for name, (fn, desc) in STRATEGIES.items():
            signal = fn(row, lookback)
            if signal == "buy":
                buy_strats.add(name)

        if len(buy_strats) >= 2:
            exit_price = df["Close"].iloc[min(exit_idx, len(df) - 1)]
            pnl_pct = (exit_price / price - 1) * 100
            tier = "BUY" if len(buy_strats) >= 3 else "WATCH"

            results.append({
                "ticker": ticker,
                "date": date,
                "buy_price": price,
                "exit_price": exit_price,
                "pnl_pct": pnl_pct,
                "strategies": len(buy_strats),
                "tier": tier,
                "rsi": row.get("rsi"),
            })

    return results


def _run_window(tickers: list[str], window_name: str, signal_start: int, signal_end: int, exit_idx: int):
    """Run simulation for one time window."""
    all_results = []
    done = 0

    def process(ticker):
        try:
            stock = yf.Ticker(ticker)
            hist = stock.history(period="1y")
            if hist.empty or len(hist) < 220:
                return []
            df = _precompute(hist)
            start = len(df) - signal_start
            end = len(df) - signal_end
            exit_at = len(df) - exit_idx
            return _simulate_ticker(ticker, df, start, end, exit_at)
        except Exception:
            return []

    with ThreadPoolExecutor(max_workers=10) as ex:
        futures = {ex.submit(process, t): t for t in tickers}
        for f in as_completed(futures):
            done += 1
            if done % 50 == 0:
                print(f"    {done}/{len(tickers)}")
            all_results.extend(f.result())

    return all_results


def run_tests(sample_size: int = SAMPLE_SIZE) -> dict:
    tickers = get_sp500_tickers()[:sample_size]
    scale = 503 / sample_size

    windows = [
        ("Month 1 (recent → today)", 22, 0, 0),
        ("Month 2 (2 months ago → 1 month ago)", 44, 22, 22),
        ("Month 3 (3 months ago → 2 months ago)", 66, 44, 44),
    ]

    all_window_results = {}
    overall_pass = True

    print(f"\n{'='*70}")
    print(f"  STRATEGY PERFORMANCE TEST")
    print(f"  Testing on {sample_size} stocks (extrapolated to 503)")
    print(f"{'='*70}")

    for name, sig_start, sig_end, exit_at in windows:
        print(f"\n  {name}")
        print(f"  {'-'*60}")
        results = _run_window(tickers, name, sig_start, sig_end, exit_at)

        buy_signals = [r for r in results if r["tier"] == "BUY"]
        watch_signals = [r for r in results if r["tier"] == "WATCH"]

        # Deduplicate: take first signal per ticker per window
        seen_buy = set()
        unique_buys = []
        for r in buy_signals:
            if r["ticker"] not in seen_buy:
                seen_buy.add(r["ticker"])
                unique_buys.append(r)

        seen_watch = set()
        unique_watch = []
        for r in watch_signals:
            if r["ticker"] not in seen_watch:
                seen_watch.add(r["ticker"])
                unique_watch.append(r)

        window_data = {"buy": unique_buys, "watch": unique_watch}
        all_window_results[name] = window_data

        for tier_name, signals in [("🔥 BUY", unique_buys), ("⚡ WATCH", unique_watch)]:
            if not signals:
                print(f"\n    {tier_name}: 0 signals")
                continue

            wins = [s for s in signals if s["pnl_pct"] > 0]
            losses = [s for s in signals if s["pnl_pct"] <= 0]
            avg_return = sum(s["pnl_pct"] for s in signals) / len(signals)
            win_rate = len(wins) / len(signals) * 100
            avg_win = sum(s["pnl_pct"] for s in wins) / len(wins) if wins else 0
            avg_loss = sum(s["pnl_pct"] for s in losses) / len(losses) if losses else 0
            total_profit = sum(TRADE_AMOUNT * s["pnl_pct"] / 100 for s in signals)

            status = "PASS" if win_rate >= 50 and avg_return > 0 else "FAIL"
            if tier_name == "🔥 BUY" and status == "FAIL":
                overall_pass = False

            print(f"\n    {tier_name}: {len(signals)} signals (~{len(signals)*scale:.0f} extrapolated)  [{status}]")
            print(f"      Win rate:    {win_rate:.0f}% ({len(wins)}W / {len(losses)}L)")
            print(f"      Avg return:  {avg_return:+.2f}%")
            print(f"      Avg win:     {avg_win:+.2f}%")
            print(f"      Avg loss:    {avg_loss:+.2f}%")
            print(f"      Profit ($300/trade): ${total_profit:+.1f}")

            # Show top and bottom trades
            sorted_signals = sorted(signals, key=lambda x: -x["pnl_pct"])
            if sorted_signals:
                best = sorted_signals[0]
                worst = sorted_signals[-1]
                print(f"      Best:  {best['ticker']} {best['pnl_pct']:+.1f}% (bought ${best['buy_price']:.2f})")
                print(f"      Worst: {worst['ticker']} {worst['pnl_pct']:+.1f}% (bought ${worst['buy_price']:.2f})")

    print(f"\n{'='*70}")
    print(f"  OVERALL: {'PASS ✅' if overall_pass else 'FAIL ❌'}")
    if not overall_pass:
        print(f"  ⚠️  BUY tier underperforming in at least one window.")
        print(f"  Review strategy parameters before deploying.")
    print(f"{'='*70}\n")

    return {"pass": overall_pass, "results": all_window_results}


if __name__ == "__main__":
    result = run_tests()
    sys.exit(0 if result["pass"] else 1)
