"""Telegram notification sender."""

import json
import urllib.request
import urllib.parse
from pathlib import Path

CONFIG_PATH = Path(__file__).parent / "alert_config.json"


def _load_config() -> dict:
    if not CONFIG_PATH.exists():
        return {}
    with open(CONFIG_PATH) as f:
        return json.load(f)


def _save_config(config: dict):
    with open(CONFIG_PATH, "w") as f:
        json.dump(config, f, indent=2)


def configure_telegram(bot_token: str, chat_id: str):
    config = _load_config()
    config["telegram"] = {"bot_token": bot_token, "chat_id": chat_id}
    _save_config(config)
    print("Telegram configured. Sending test message...")
    ok = send_telegram("Stock Toolkit connected! You'll receive alerts here.")
    if ok:
        print("Test message sent successfully.")
    else:
        print("Failed to send test message. Check your bot token and chat ID.")


def send_telegram(message: str, parse_mode: str = "HTML") -> bool:
    config = _load_config()
    tg = config.get("telegram")
    if not tg:
        print("Telegram not configured. Run: main.py alerts setup <BOT_TOKEN> <CHAT_ID>")
        return False

    url = f"https://api.telegram.org/bot{tg['bot_token']}/sendMessage"
    data = urllib.parse.urlencode({
        "chat_id": tg["chat_id"],
        "text": message,
        "parse_mode": parse_mode,
    }).encode()

    try:
        req = urllib.request.Request(url, data=data)
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.status == 200
    except Exception as e:
        print(f"Telegram send failed: {e}")
        return False


def format_alert(alert: dict) -> str:
    signal = alert["signal"].upper()
    emoji = "🟢" if signal == "BUY" else "🔴"

    lines = [
        f"{emoji} <b>{signal} SIGNAL — {alert['ticker']}</b>",
        f"",
        f"<b>Price:</b> ${alert['price']:.2f}",
    ]

    if alert.get("rsi") is not None:
        lines.append(f"<b>RSI:</b> {alert['rsi']:.1f}")
    if alert.get("strategy"):
        lines.append(f"<b>Strategy:</b> {alert['strategy']}")
    if alert.get("reasons"):
        lines.append(f"")
        for r in alert["reasons"]:
            lines.append(f"  • {r}")

    if alert.get("change_1d") is not None:
        lines.append(f"")
        lines.append(f"<b>1D Change:</b> {alert['change_1d']:+.2f}%")
    if alert.get("off_high") is not None:
        lines.append(f"<b>Off 52W High:</b> {alert['off_high']:.1f}%")

    return "\n".join(lines)


def format_scan_summary(alerts: list[dict], scanned: int) -> str:
    if not alerts:
        return f"📊 <b>Scan complete</b> — {scanned} stocks checked, no signals."

    buy_count = sum(1 for a in alerts if a["signal"] == "buy")
    sell_count = sum(1 for a in alerts if a["signal"] == "sell")

    lines = [
        f"📊 <b>Scan Summary</b>",
        f"Checked {scanned} stocks",
        f"",
    ]
    if buy_count:
        lines.append(f"🟢 {buy_count} buy signal{'s' if buy_count > 1 else ''}")
    if sell_count:
        lines.append(f"🔴 {sell_count} sell signal{'s' if sell_count > 1 else ''}")

    return "\n".join(lines)
