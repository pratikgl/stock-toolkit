"""Alert scanner — checks watchlist stocks against strategies and fires alerts."""

import json
import hashlib
from datetime import datetime, timedelta
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

import yfinance as yf
import pandas as pd

from strategies import STRATEGIES
from watchlist import get_watchlist
from notifier import send_telegram, format_alert, format_scan_summary
from indicators import compute_rsi, compute_sma

ALERT_HISTORY_PATH = Path(__file__).parent / "alert_history.json"
COOLDOWN_HOURS = 24


def _load_history() -> dict:
    if not ALERT_HISTORY_PATH.exists():
        return {}
    with open(ALERT_HISTORY_PATH) as f:
        return json.load(f)


def _save_history(history: dict):
    with open(ALERT_HISTORY_PATH, "w") as f:
        json.dump(history, f, indent=2)


def _alert_key(ticker: str, strategy: str, signal: str) -> str:
    return hashlib.md5(f"{ticker}:{strategy}:{signal}".encode()).hexdigest()


def _is_duplicate(ticker: str, strategy: str, signal: str, history: dict) -> bool:
    key = _alert_key(ticker, strategy, signal)
    if key not in history:
        return False
    last_sent = datetime.fromisoformat(history[key])
    return datetime.now() - last_sent < timedelta(hours=COOLDOWN_HOURS)


def _record_alert(ticker: str, strategy: str, signal: str, history: dict):
    key = _alert_key(ticker, strategy, signal)
    history[key] = datetime.now().isoformat()


def _scan_ticker(ticker: str, strategy_names: list[str]) -> list[dict]:
    try:
        stock = yf.Ticker(ticker)
        hist = stock.history(period="1y")
        if hist.empty or len(hist) < 200:
            return []

        info = stock.info
        close = hist["Close"]
        volume = hist["Volume"]
        price = close.iloc[-1]

        # Precompute indicators (same as backtester)
        from ta.momentum import RSIIndicator
        from ta.trend import MACD
        from ta.volatility import BollingerBands

        df = hist.copy()
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

        row = df.iloc[-1]
        lookback = df

        alerts = []
        for strat_name in strategy_names:
            if strat_name not in STRATEGIES:
                continue
            fn, desc = STRATEGIES[strat_name]
            signal = fn(row, lookback)
            if signal in ("buy", "sell"):
                high_52w = info.get("fiftyTwoWeekHigh")
                prev_close = close.iloc[-2] if len(close) > 1 else price

                reasons = []
                rsi_val = row.get("rsi")
                if rsi_val is not None:
                    if rsi_val < 30:
                        reasons.append(f"RSI oversold at {rsi_val:.1f}")
                    elif rsi_val > 70:
                        reasons.append(f"RSI overbought at {rsi_val:.1f}")

                sma_50 = row.get("sma_50")
                sma_200 = row.get("sma_200")
                if sma_50 and sma_200:
                    if sma_50 > sma_200:
                        reasons.append("Golden cross active (SMA50 > SMA200)")
                    else:
                        reasons.append("Death cross active (SMA50 < SMA200)")

                if high_52w and price:
                    off_pct = (high_52w - price) / high_52w * 100
                    if off_pct > 15:
                        reasons.append(f"{off_pct:.0f}% below 52-week high")

                alerts.append({
                    "ticker": ticker,
                    "signal": signal,
                    "strategy": strat_name,
                    "price": price,
                    "rsi": rsi_val,
                    "change_1d": (price / prev_close - 1) * 100 if prev_close else None,
                    "off_high": (high_52w - price) / high_52w * 100 if high_52w else None,
                    "reasons": reasons,
                })

        return alerts
    except Exception as e:
        print(f"  Error scanning {ticker}: {e}")
        return []


def run_scan(notify: bool = True, force: bool = False, max_workers: int = 5) -> list[dict]:
    watchlist = get_watchlist()
    if not watchlist:
        print("Watchlist is empty. Add stocks first: main.py alerts add AAPL")
        return []

    history = _load_history()
    all_alerts = []
    scanned = 0

    print(f"Scanning {len(watchlist)} stocks...")

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {}
        for ticker, info in watchlist.items():
            if not info.get("active", True):
                continue
            futures[executor.submit(_scan_ticker, ticker, info["strategies"])] = ticker

        for future in as_completed(futures):
            scanned += 1
            ticker = futures[future]
            alerts = future.result()
            for alert in alerts:
                if force or not _is_duplicate(alert["ticker"], alert["strategy"], alert["signal"], history):
                    all_alerts.append(alert)
                    _record_alert(alert["ticker"], alert["strategy"], alert["signal"], history)

    _save_history(history)

    # Print to terminal
    if all_alerts:
        print(f"\n{len(all_alerts)} signal(s) found:\n")
        for alert in all_alerts:
            signal = alert["signal"].upper()
            marker = ">>>" if signal == "BUY" else "<<<"
            print(f"  {marker} {signal:4s} {alert['ticker']:6s}  ${alert['price']:.2f}  "
                  f"[{alert['strategy']}]  RSI: {alert['rsi']:.1f}" if alert['rsi'] else
                  f"  {marker} {signal:4s} {alert['ticker']:6s}  ${alert['price']:.2f}  "
                  f"[{alert['strategy']}]")
            for r in alert.get("reasons", []):
                print(f"          {r}")
        print()
    else:
        print("No new signals.")

    # Send Telegram notifications
    if notify and all_alerts:
        summary = format_scan_summary(all_alerts, scanned)
        send_telegram(summary)
        for alert in all_alerts:
            msg = format_alert(alert)
            send_telegram(msg)
        print(f"Sent {len(all_alerts) + 1} Telegram messages.")

    return all_alerts


def cleanup_history(days: int = 7):
    history = _load_history()
    cutoff = datetime.now() - timedelta(days=days)
    cleaned = {k: v for k, v in history.items() if datetime.fromisoformat(v) > cutoff}
    removed = len(history) - len(cleaned)
    _save_history(cleaned)
    print(f"Cleaned {removed} old alert records.")
