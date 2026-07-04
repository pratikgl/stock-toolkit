"""Sell signal monitor — watches your holdings and recommends when to sell."""

from datetime import datetime

import yfinance as yf

from trade_tracker import get_holdings
from notifier import send_telegram
from indicators import compute_rsi, compute_sma


def check_sell_signals(notify: bool = True) -> list[dict]:
    holdings = get_holdings()
    if not holdings:
        print("No holdings to monitor.")
        return []

    signals = []
    print(f"Checking sell signals for {len(holdings)} holdings...")

    for ticker, holding in holdings.items():
        signal = _analyze_holding(ticker, holding)
        if signal:
            signals.append(signal)
            print(f"  {signal['action']:15s} {ticker:6s}  P&L: {signal['pnl_pct']:+.1f}%  "
                  f"Reason: {signal['reason']}")

    if notify and signals:
        for s in signals:
            msg = _format_sell_alert(s)
            send_telegram(msg, parse_mode="HTML")
        print(f"Sent {len(signals)} sell alerts.")

    return signals


def _analyze_holding(ticker: str, holding: dict) -> dict | None:
    try:
        stock = yf.Ticker(ticker)
        hist = stock.history(period="6mo")
        if hist.empty:
            return None

        info = stock.info
        close = hist["Close"]
        price = close.iloc[-1]
        avg_cost = holding["avg_cost"]
        shares = holding["shares"]
        buy_date = holding.get("buy_date", "2026-01-01")

        pnl = (price - avg_cost) * shares
        pnl_pct = (price / avg_cost - 1) * 100

        # Days held
        try:
            days_held = (datetime.now() - datetime.strptime(buy_date, "%Y-%m-%d")).days
        except ValueError:
            days_held = 0
        months_held = days_held / 30.44

        # Tax context
        is_ltcg = months_held >= 24
        tax_rate = 0.125 if is_ltcg else 0.20
        months_to_ltcg = max(0, 24 - months_held)

        # Technical indicators
        rsi = compute_rsi(close)
        sma_50 = compute_sma(close, 50)
        sma_200 = compute_sma(close, 200)

        # Determine action
        action = None
        reason = None
        sell_pct = 0  # 0 = hold, 50 = sell half, 100 = sell all

        # SELL signals
        if rsi and rsi > 75 and pnl_pct > 20:
            action = "SELL HALF"
            sell_pct = 50
            reason = f"Overbought (RSI {rsi:.0f}) with +{pnl_pct:.0f}% gain. Lock in some profit."

        elif rsi and rsi > 80:
            action = "SELL HALF"
            sell_pct = 50
            reason = f"Very overbought (RSI {rsi:.0f}). Take profit, buy back on dip."

        elif pnl_pct > 50 and rsi and rsi > 65:
            action = "SELL 30%"
            sell_pct = 30
            reason = f"Up +{pnl_pct:.0f}%. Trim position, let rest ride."

        elif sma_50 and sma_200 and sma_50 < sma_200 and pnl_pct < -10:
            action = "SELL ALL"
            sell_pct = 100
            reason = f"Death cross + losing {pnl_pct:.0f}%. Cut losses."

        elif pnl_pct < -25:
            action = "SELL ALL"
            sell_pct = 100
            reason = f"Down {pnl_pct:.0f}%. Stop loss — protect remaining capital."

        elif pnl_pct < -15 and sma_50 and price < sma_50:
            action = "SELL HALF"
            sell_pct = 50
            reason = f"Down {pnl_pct:.0f}% and below SMA50. Reduce exposure."

        # HOLD signals (no alert sent unless notable)
        elif 0 < months_to_ltcg <= 3 and pnl_pct > 15:
            action = "HOLD"
            sell_pct = 0
            reason = f"Up +{pnl_pct:.0f}% but {months_to_ltcg:.0f} months from LTCG. Hold for 12.5% tax rate."

        if not action:
            return None

        sell_shares = shares * sell_pct / 100
        tax_on_sell = max(0, (price - avg_cost) * sell_shares * tax_rate)

        return {
            "ticker": ticker,
            "action": action,
            "sell_pct": sell_pct,
            "sell_shares": sell_shares,
            "reason": reason,
            "price": price,
            "avg_cost": avg_cost,
            "shares": shares,
            "pnl": pnl,
            "pnl_pct": pnl_pct,
            "rsi": rsi,
            "days_held": days_held,
            "months_held": months_held,
            "is_ltcg": is_ltcg,
            "months_to_ltcg": months_to_ltcg,
            "tax_rate": tax_rate,
            "estimated_tax": tax_on_sell,
        }
    except Exception as e:
        print(f"  Error checking {ticker}: {e}")
        return None


def _format_sell_alert(s: dict) -> str:
    action_emoji = "🔴" if "SELL" in s["action"] else "🟡"

    lines = [
        f"{action_emoji} <b>{s['action']} — {s['ticker']}</b>",
        f"",
        f"<b>Current:</b> ${s['price']:.2f}",
        f"<b>Your Cost:</b> ${s['avg_cost']:.2f} ({s['shares']:.2f} shares)",
        f"<b>P&L:</b> ${s['pnl']:+.2f} ({s['pnl_pct']:+.1f}%)",
        f"<b>Held:</b> {s['days_held']} days ({s['months_held']:.0f} months)",
        f"",
        f"<b>Why:</b> {s['reason']}",
    ]

    if s["sell_pct"] > 0 and s["sell_pct"] < 100:
        lines.append(f"")
        lines.append(f"📋 <b>Action:</b> Sell {s['sell_shares']:.2f} of {s['shares']:.2f} shares")
        lines.append(f"   Keep {s['shares'] - s['sell_shares']:.2f} shares — wait for next signal")

    if s["sell_pct"] == 100:
        lines.append(f"")
        lines.append(f"📋 <b>Action:</b> Sell all {s['shares']:.2f} shares")

    # Tax context
    lines.append(f"")
    if s["is_ltcg"]:
        lines.append(f"💰 Tax: LTCG 12.5% — ~Rs.{s['estimated_tax'] * 85:,.0f}")
    elif s["months_to_ltcg"] <= 6:
        lines.append(f"💰 Tax: STCG ~20% — ~Rs.{s['estimated_tax'] * 85:,.0f}")
        lines.append(f"   ⏳ {s['months_to_ltcg']:.0f} months to LTCG (12.5%)")
    else:
        lines.append(f"💰 Tax: STCG ~20% — ~Rs.{s['estimated_tax'] * 85:,.0f}")

    if s.get("rsi"):
        lines.append(f"")
        lines.append(f"RSI: {s['rsi']:.0f}")

    return "\n".join(lines)
