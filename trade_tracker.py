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
    original = text.strip()
    text = original.upper()
    parts = text.split()

    if not parts:
        return None

    cmd = parts[0]

    if cmd in ("BUY", "BOUGHT"):
        return _handle_buy(parts)

    elif cmd in ("SELL", "SOLD"):
        return _handle_sell(parts)

    elif cmd in ("HOLDINGS", "PORTFOLIO", "STATUS"):
        return _format_holdings()

    elif cmd in ("HELP", "HI", "HELLO", "START", "/START", "/HELP"):
        return _help_message()

    # Unknown command — show help
    return (
        f"❓ Didn't understand: \"{original}\"\n\n"
        + _help_message()
    )


def _handle_buy(parts: list[str]) -> str:
    if len(parts) < 2:
        return "❌ Missing ticker.\n\nFormat: BUY TICKER SHARES PRICE\nExample: BUY NVDA 10 194.83"

    if len(parts) < 3:
        return f"❌ Missing number of shares.\n\nFormat: BUY {parts[1]} SHARES PRICE\nExample: BUY {parts[1]} 10 194.83"

    if len(parts) < 4:
        return f"❌ Missing price.\n\nFormat: BUY {parts[1]} {parts[2]} PRICE\nExample: BUY {parts[1]} {parts[2]} 194.83"

    ticker = parts[1]

    # Validate ticker (basic: 1-5 uppercase letters)
    if not ticker.isalpha() or len(ticker) > 5:
        return f"❌ Invalid ticker \"{ticker}\". Should be 1-5 letters.\nExample: BUY NVDA 10 194.83"

    # Validate shares
    try:
        shares = float(parts[2])
    except ValueError:
        return f"❌ \"{parts[2]}\" is not a valid number for shares.\nExample: BUY {ticker} 10 194.83"
    if shares <= 0:
        return f"❌ Shares must be greater than 0. You entered: {shares}"

    # Validate price
    price_str = parts[3].replace("$", "")
    try:
        price = float(price_str)
    except ValueError:
        return f"❌ \"{parts[3]}\" is not a valid price.\nExample: BUY {ticker} {shares} 194.83"
    if price <= 0:
        return f"❌ Price must be greater than 0. You entered: {price}"

    result = record_buy(ticker, shares, price)
    total = shares * price
    return (
        f"✅ {result}\n"
        f"Total invested: ${total:,.2f}\n\n"
        f"I'll monitor {ticker} and alert you when to sell.\n"
        f"Type HOLDINGS to see your portfolio."
    )


def _handle_sell(parts: list[str]) -> str:
    if len(parts) < 2:
        return "❌ Missing ticker.\n\nFormat: SELL TICKER SHARES PRICE\nExample: SELL NVDA 5 250.00"

    if len(parts) < 3:
        return f"❌ Missing number of shares.\n\nFormat: SELL {parts[1]} SHARES PRICE\nExample: SELL {parts[1]} 5 250.00"

    if len(parts) < 4:
        return f"❌ Missing price.\n\nFormat: SELL {parts[1]} {parts[2]} PRICE\nExample: SELL {parts[1]} {parts[2]} 250.00"

    ticker = parts[1]

    if not ticker.isalpha() or len(ticker) > 5:
        return f"❌ Invalid ticker \"{ticker}\". Should be 1-5 letters."

    try:
        shares = float(parts[2])
    except ValueError:
        return f"❌ \"{parts[2]}\" is not a valid number for shares."
    if shares <= 0:
        return f"❌ Shares must be greater than 0."

    price_str = parts[3].replace("$", "")
    try:
        price = float(price_str)
    except ValueError:
        return f"❌ \"{parts[3]}\" is not a valid price."
    if price <= 0:
        return f"❌ Price must be greater than 0."

    result = record_sell(ticker, shares, price)
    return f"✅ {result}\n\nType HOLDINGS to see updated portfolio."


def _help_message() -> str:
    return (
        "📈 Stock Toolkit Bot\n\n"
        "Record your trades and I'll monitor them for sell signals.\n\n"
        "Commands:\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        "BUY NVDA 10 194.83\n"
        "  → Records buying 10 shares of NVDA at $194.83\n\n"
        "SELL NVDA 5 250.00\n"
        "  → Records selling 5 shares at $250\n\n"
        "HOLDINGS\n"
        "  → Shows your current portfolio\n\n"
        "HELP\n"
        "  → Shows this message\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        "After recording, I'll automatically check your stocks\n"
        "twice daily and alert you when to SELL HALF, SELL ALL,\n"
        "or HOLD (for tax reasons)."
    )


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
