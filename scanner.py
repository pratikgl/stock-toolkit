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
from sp500 import get_sp500_tickers
from notifier import send_telegram, format_alert, format_scan_summary
from indicators import compute_rsi, compute_sma
from backtester import Backtester

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

        # Volume confirmation
        vol_today = volume.iloc[-1] if not volume.empty else 0
        vol_avg = volume.iloc[-21:-1].mean() if len(volume) > 21 else vol_today
        vol_ratio = vol_today / vol_avg if vol_avg > 0 else 1.0

        # Quality score — fundamentals-based
        quality_score = 0
        pe = info.get("trailingPE")
        if pe and 5 < pe < 30:
            quality_score += 10
        growth = info.get("revenueGrowth")
        if growth and growth > 0.10:
            quality_score += 15
        elif growth and growth > 0.05:
            quality_score += 5
        margin = info.get("profitMargins")
        if margin and margin > 0.15:
            quality_score += 10
        cap = info.get("marketCap", 0)
        if cap and cap > 50_000_000_000:
            quality_score += 5  # large cap bonus

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
                        reasons.append("Golden cross (SMA50 > SMA200)")
                    else:
                        reasons.append("Death cross (SMA50 < SMA200)")

                if high_52w and price:
                    off_pct = (high_52w - price) / high_52w * 100
                    if off_pct > 15:
                        reasons.append(f"{off_pct:.0f}% below 52W high")

                if vol_ratio > 1.5:
                    reasons.append(f"Volume {vol_ratio:.1f}x average")

                alerts.append({
                    "ticker": ticker,
                    "signal": signal,
                    "strategy": strat_name,
                    "price": price,
                    "rsi": rsi_val,
                    "change_1d": (price / prev_close - 1) * 100 if prev_close else None,
                    "off_high": (high_52w - price) / high_52w * 100 if high_52w else None,
                    "reasons": reasons,
                    "sector": info.get("sector", "Unknown"),
                    "quality_score": quality_score,
                    "vol_ratio": round(vol_ratio, 2),
                    "market_cap": cap,
                    "name": info.get("shortName", ticker),
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


def _backtest_validate(ticker: str, strategy_name: str) -> dict | None:
    """Run a quick 3-year backtest to validate a strategy works on this stock."""
    if strategy_name not in STRATEGIES:
        return None
    try:
        fn, desc = STRATEGIES[strategy_name]
        bt = Backtester(ticker, period="3y")
        result = bt.run(fn, strategy_name=strategy_name)
        return {
            "return_pct": result.total_return_pct,
            "benchmark_pct": result.benchmark_return or 0,
            "win_rate": result.win_rate,
            "num_trades": result.num_trades,
            "sharpe": result.sharpe_ratio,
            "max_drawdown": result.max_drawdown,
            "passed": result.win_rate >= 40 and result.num_trades >= 2,
        }
    except Exception:
        return None


def _compute_signal_score(info: dict) -> float:
    """Combined score: strategy conviction + quality + volume + backtest validation."""
    strat_count = len(info["strategies"])
    quality = info["alerts"][0].get("quality_score", 0)
    vol_ratio = info["alerts"][0].get("vol_ratio", 1.0)

    score = strat_count * 25  # 25 pts per agreeing strategy
    score += quality           # up to 40 pts for fundamentals
    if vol_ratio > 1.5:
        score += 15            # volume confirmation bonus
    elif vol_ratio > 1.2:
        score += 5

    # Backtest bonus/penalty
    bt = info.get("backtest")
    if bt:
        if bt["passed"]:
            score += 20        # strategy historically works on this stock
            if bt["win_rate"] >= 60:
                score += 10    # high win rate bonus
        else:
            score -= 15        # strategy hasn't worked here

    # Penalty: death cross (downtrend) reduces score
    for alert in info["alerts"]:
        for r in alert.get("reasons", []):
            if "Death cross" in r:
                score -= 20
                break
        break

    return score


def run_full_scan(notify: bool = True, max_workers: int = 10) -> list[dict]:
    """Scan ALL S&P 500 stocks with all strategies. Designed for GitHub Actions."""
    tickers = get_sp500_tickers()
    all_strategies = list(STRATEGIES.keys())

    history = _load_history()
    all_alerts = []
    scanned = 0

    print(f"Full scan: {len(tickers)} stocks x {len(all_strategies)} strategies...")

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(_scan_ticker, t, all_strategies): t for t in tickers}
        for future in as_completed(futures):
            scanned += 1
            if scanned % 50 == 0:
                print(f"  Progress: {scanned}/{len(tickers)}")
            alerts = future.result()
            for alert in alerts:
                if not _is_duplicate(alert["ticker"], alert["strategy"], alert["signal"], history):
                    all_alerts.append(alert)
                    _record_alert(alert["ticker"], alert["strategy"], alert["signal"], history)

    _save_history(history)

    buy_alerts = [a for a in all_alerts if a["signal"] == "buy"]

    # Group by ticker
    ticker_signals = {}
    for a in buy_alerts:
        t = a["ticker"]
        if t not in ticker_signals:
            ticker_signals[t] = {"alerts": [], "strategies": set()}
        ticker_signals[t]["alerts"].append(a)
        ticker_signals[t]["strategies"].add(a["strategy"])

    # Pre-score to find top candidates for backtesting
    for ticker, info in ticker_signals.items():
        info["score"] = _compute_signal_score(info)

    # Backtest top 15 candidates — validate strategy historically works on this stock
    pre_ranked = sorted(ticker_signals.items(), key=lambda x: x[1]["score"], reverse=True)
    if pre_ranked:
        print(f"\nBacktest-validating top {min(15, len(pre_ranked))} candidates...")
        for ticker, info in pre_ranked[:15]:
            # Pick the strategy with strongest signal to backtest
            best_strat = sorted(info["strategies"])[0]
            bt_result = _backtest_validate(ticker, best_strat)
            if bt_result:
                info["backtest"] = bt_result
                status = "PASS" if bt_result["passed"] else "FAIL"
                print(f"  {ticker:6s} [{best_strat}] {status} — "
                      f"{bt_result['return_pct']:+.0f}% return, "
                      f"{bt_result['win_rate']:.0f}% win rate, "
                      f"{bt_result['num_trades']} trades")

        # Re-score with backtest data
        for ticker, info in ticker_signals.items():
            info["score"] = _compute_signal_score(info)

    ranked = sorted(ticker_signals.items(), key=lambda x: x[1]["score"], reverse=True)

    # Sector context — count how many stocks per sector have buy signals
    sector_counts = {}
    for ticker, info in ranked:
        sector = info["alerts"][0].get("sector", "Unknown")
        sector_counts[sector] = sector_counts.get(sector, 0) + 1

    print(f"\nScanned {scanned} stocks. {len(buy_alerts)} buy signals found.")
    if ranked:
        print(f"\nTop signals (score = strategies + quality + volume):\n")
        for ticker, info in ranked[:15]:
            strats = ", ".join(sorted(info["strategies"]))
            a = info["alerts"][0]
            rsi_str = f"RSI {a['rsi']:.0f}" if a.get("rsi") else ""
            vol_str = f"Vol {a['vol_ratio']:.1f}x" if a.get("vol_ratio", 1) > 1.2 else ""
            sector = a.get("sector", "?")
            print(f"  Score {info['score']:3.0f}  {ticker:6s}  ${a['price']:.2f}  {rsi_str:8s}  "
                  f"{vol_str:10s}  {sector:20s}  [{strats}]")
        print()

        if sector_counts:
            print("Sector breakdown of buy signals:")
            for sector, count in sorted(sector_counts.items(), key=lambda x: -x[1])[:5]:
                print(f"  {sector:25s}  {count} stocks")
            print()

    if notify and ranked:
        # Only include stocks with score >= 50 (minimum 2 strategies + decent quality)
        strong = [(t, i) for t, i in ranked if i["score"] >= 50]

        if not strong:
            send_telegram(f"📊 <b>Daily S&P 500 Scan</b>\n"
                         f"Scanned {scanned} stocks\n\n"
                         f"No high-conviction signals today. Market is quiet.")
        else:
            # Summary message with top 10
            msg_lines = [
                f"📊 <b>Daily S&P 500 Scan</b>",
                f"Scanned {scanned} stocks | {len(strong)} quality signals",
                f"",
            ]

            # High conviction (3+ strategies or score >= 75)
            top_tier = [(t, i) for t, i in strong if len(i["strategies"]) >= 3 or i["score"] >= 75]
            if top_tier:
                msg_lines.append(f"🔥 <b>HIGH CONVICTION:</b>")
                msg_lines.append("")
                for ticker, info in top_tier[:5]:
                    a = info["alerts"][0]
                    strats = ", ".join(sorted(info["strategies"]))
                    rsi_str = f" | RSI {a['rsi']:.0f}" if a.get("rsi") else ""
                    vol_str = f" | Vol {a['vol_ratio']:.1f}x" if a.get("vol_ratio", 1) > 1.5 else ""
                    name = a.get("name", ticker)
                    msg_lines.append(f"🔥 <b>{ticker}</b> ({name}) ${a['price']:.2f}")
                    msg_lines.append(f"   Score: {info['score']:.0f}{rsi_str}{vol_str}")
                    msg_lines.append(f"   {len(info['strategies'])} strategies: {strats}")
                    bt = info.get("backtest")
                    if bt and bt["passed"]:
                        msg_lines.append(f"   ✅ Backtest: {bt['return_pct']:+.0f}% over 3y, {bt['win_rate']:.0f}% win rate")
                    elif bt:
                        msg_lines.append(f"   ⚠️ Backtest: {bt['return_pct']:+.0f}% over 3y (weak)")
                    if a.get("reasons"):
                        msg_lines.append(f"   {a['reasons'][0]}")
                    msg_lines.append("")

            # Watchlist-worthy (2 strategies, decent score)
            watch_tier = [(t, i) for t, i in strong if (t, i) not in top_tier]
            if watch_tier:
                msg_lines.append(f"🟢 <b>WATCHLIST:</b>")
                msg_lines.append("")
                for ticker, info in watch_tier[:5]:
                    a = info["alerts"][0]
                    strats = ", ".join(sorted(info["strategies"]))
                    rsi_str = f" | RSI {a['rsi']:.0f}" if a.get("rsi") else ""
                    msg_lines.append(f"🟢 <b>{ticker}</b> ${a['price']:.2f}{rsi_str}")
                    msg_lines.append(f"   {len(info['strategies'])} strats: {strats}")
                    msg_lines.append("")

            # Sector context
            top_sectors = sorted(sector_counts.items(), key=lambda x: -x[1])[:3]
            if top_sectors:
                msg_lines.append(f"📈 <b>Hot sectors:</b> {', '.join(f'{s} ({c})' for s, c in top_sectors)}")

            send_telegram("\n".join(msg_lines))

            # Individual detailed alerts ONLY for high conviction
            for ticker, info in top_tier[:3]:
                a = info["alerts"][0]
                a["strategy"] = f"{len(info['strategies'])} strategies: {', '.join(sorted(info['strategies']))}"
                send_telegram(format_alert(a))

        print(f"Telegram alerts sent.")

    # Save full results to CSV
    if buy_alerts:
        import csv
        fields = ["ticker", "signal", "strategy", "price", "rsi", "change_1d",
                  "off_high", "sector", "quality_score", "vol_ratio"]
        with open("screener_output.csv", "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
            writer.writeheader()
            for a in buy_alerts:
                writer.writerow(a)

    return all_alerts


def cleanup_history(days: int = 7):
    history = _load_history()
    cutoff = datetime.now() - timedelta(days=days)
    cleaned = {k: v for k, v in history.items() if datetime.fromisoformat(v) > cutoff}
    removed = len(history) - len(cleaned)
    _save_history(cleaned)
    print(f"Cleaned {removed} old alert records.")
