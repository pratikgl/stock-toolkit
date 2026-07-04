"""Trade tracker — reads trade commands from Telegram, manages holdings, generates sell signals."""

import json
import os
import urllib.request
import urllib.parse
from datetime import datetime
from pathlib import Path

HOLDINGS_PATH = Path(__file__).parent / "holdings.json"
LAST_UPDATE_PATH = Path(__file__).parent / "last_telegram_update.json"


def _load_holdings() -> dict:
    if not HOLDINGS_PATH.exists():
        return {"holdings": {}, "closed_trades": []}
    with open(HOLDINGS_PATH) as f:
        return json.load(f)


def _save_holdings(data: dict):
    with open(HOLDINGS_PATH, "w") as f:
        json.dump(data, f, indent=2)


def _get_last_update_id() -> int:
    if not LAST_UPDATE_PATH.exists():
        return 0
    with open(LAST_UPDATE_PATH) as f:
        return json.load(f).get("last_update_id", 0)


def _save_last_update_id(update_id: int):
    with open(LAST_UPDATE_PATH, "w") as f:
        json.dump({"last_update_id": update_id}, f)


def record_buy(ticker: str, shares: float, price: float, date: str | None = None):
    data = _load_holdings()
    ticker = ticker.upper()
    date = date or datetime.now().strftime("%Y-%m-%d")

    if ticker in data["holdings"]:
        h = data["holdings"][ticker]
        total_cost = h["avg_cost"] * h["shares"] + price * shares
        h["shares"] += shares
        h["avg_cost"] = total_cost / h["shares"]
        h["trades"].append({"type": "buy", "shares": shares, "price": price, "date": date})
    else:
        data["holdings"][ticker] = {
            "shares": shares,
            "avg_cost": price,
            "buy_date": date,
            "trades": [{"type": "buy", "shares": shares, "price": price, "date": date}],
        }

    _save_holdings(data)
    return f"Recorded: BUY {shares} {ticker} @ ${price:.2f}"


def record_sell(ticker: str, shares: float, price: float, date: str | None = None):
    data = _load_holdings()
    ticker = ticker.upper()
    date = date or datetime.now().strftime("%Y-%m-%d")

    if ticker not in data["holdings"]:
        return f"You don't own {ticker}"

    h = data["holdings"][ticker]
    if h["shares"] < shares:
        return f"You only own {h['shares']:.2f} shares of {ticker}"

    pnl = (price - h["avg_cost"]) * shares
    h["shares"] -= shares
    h["trades"].append({"type": "sell", "shares": shares, "price": price, "date": date, "pnl": pnl})

    data["closed_trades"].append({
        "ticker": ticker, "shares": shares, "buy_price": h["avg_cost"],
        "sell_price": price, "pnl": pnl, "date": date,
    })

    if h["shares"] < 0.001:
        del data["holdings"][ticker]

    _save_holdings(data)
    return f"Recorded: SELL {shares} {ticker} @ ${price:.2f} (P&L: ${pnl:+.2f})"


def get_holdings() -> dict:
    return _load_holdings().get("holdings", {})


def check_telegram_trades():
    """Poll Telegram for new trade commands and process them.

    Supported formats:
      BUY NVDA 10 194.83
      SELL NVDA 5 250.00
      BOUGHT NVDA 10 194.83
      SOLD NVDA 5 250.00
      HOLDINGS (shows current holdings)
    """
    bot_token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    if not bot_token or not chat_id:
        # Try local config
        config_path = Path(__file__).parent / "alert_config.json"
        if config_path.exists():
            with open(config_path) as f:
                config = json.load(f)
            tg = config.get("telegram", {})
            bot_token = tg.get("bot_token")
            chat_id = tg.get("chat_id")
        if not bot_token:
            return []

    last_id = _get_last_update_id()
    url = f"https://api.telegram.org/bot{bot_token}/getUpdates?offset={last_id + 1}&timeout=5"

    try:
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode())
    except Exception as e:
        print(f"  Failed to check Telegram messages: {e}")
        return []

    if not data.get("ok"):
        return []

    results = []
    for update in data.get("result", []):
        update_id = update["update_id"]
        msg = update.get("message", {})
        text = msg.get("text", "").strip()
        msg_chat_id = str(msg.get("chat", {}).get("id", ""))

        if msg_chat_id != str(chat_id):
            _save_last_update_id(update_id)
            continue

        response = _process_command(text)
        if response:
            results.append(response)
            _send_reply(bot_token, chat_id, response)

        _save_last_update_id(update_id)

    return results


def _process_command(text: str) -> str | None:
    text = text.strip().upper()
    parts = text.split()

    if not parts:
        return None

    cmd = parts[0]

    if cmd in ("BUY", "BOUGHT") and len(parts) >= 4:
        try:
            ticker = parts[1]
            shares = float(parts[2])
            price = float(parts[3])
            return record_buy(ticker, shares, price)
        except (ValueError, IndexError):
            return "Format: BUY TICKER SHARES PRICE\nExample: BUY NVDA 10 194.83"

    elif cmd in ("SELL", "SOLD") and len(parts) >= 4:
        try:
            ticker = parts[1]
            shares = float(parts[2])
            price = float(parts[3])
            return record_sell(ticker, shares, price)
        except (ValueError, IndexError):
            return "Format: SELL TICKER SHARES PRICE\nExample: SELL NVDA 5 250.00"

    elif cmd in ("HOLDINGS", "PORTFOLIO", "STATUS"):
        return _format_holdings()

    elif cmd == "HELP":
        return (
            "Commands:\n"
            "BUY NVDA 10 194.83\n"
            "SELL NVDA 5 250.00\n"
            "HOLDINGS — show portfolio\n"
            "HELP — this message"
        )

    return None


def _format_holdings() -> str:
    holdings = get_holdings()
    if not holdings:
        return "No holdings. Send BUY TICKER SHARES PRICE to add."

    lines = ["📊 Your Holdings:\n"]
    for ticker, h in holdings.items():
        lines.append(f"  {ticker}: {h['shares']:.2f} shares @ ${h['avg_cost']:.2f}")
        lines.append(f"    Bought: {h['buy_date']}")
    return "\n".join(lines)


def _send_reply(bot_token: str, chat_id: str, message: str):
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    data = urllib.parse.urlencode({
        "chat_id": chat_id,
        "text": message,
    }).encode()
    try:
        req = urllib.request.Request(url, data=data)
        urllib.request.urlopen(req, timeout=10)
    except Exception:
        pass
