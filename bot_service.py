#!/usr/bin/env python3
"""Real-time Telegram bot — runs 24/7 as a systemd service.

Responds instantly to:
  BUY NVDA 10 194.83 — record trade
  SELL NVDA 5 250.00  — record sale
  HOLDINGS            — show portfolio
  HELP                — show commands
  SCAN                — trigger immediate scan
  SCAN INDIA          — trigger India scan
"""

import json
import time
import urllib.request
import urllib.error
import urllib.parse
from pathlib import Path

from trade_tracker import _process_command

CONFIG_PATH = Path(__file__).parent / "alert_config.json"


def _load_config() -> dict:
    with open(CONFIG_PATH) as f:
        return json.load(f)


def _get_updates(bot_token: str, offset: int, timeout: int = 30) -> list:
    url = f"https://api.telegram.org/bot{bot_token}/getUpdates?offset={offset}&timeout={timeout}"
    try:
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=timeout + 10) as resp:
            data = json.loads(resp.read().decode())
            return data.get("result", [])
    except Exception:
        return []


def _send_message(bot_token: str, chat_id: str, text: str):
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    data = urllib.parse.urlencode({
        "chat_id": chat_id,
        "text": text,
    }).encode()
    try:
        req = urllib.request.Request(url, data=data)
        urllib.request.urlopen(req, timeout=10)
    except Exception:
        pass


def _handle_scan_command(text: str, bot_token: str, chat_id: str) -> bool:
    upper = text.strip().upper()
    if upper in ("SCAN", "SCAN US", "SCAN FULL"):
        _send_message(bot_token, chat_id, "🔄 Running US scan...")
        import subprocess
        toolkit_dir = Path(__file__).parent
        python = toolkit_dir / "venv" / "bin" / "python3"
        result = subprocess.run(
            [str(python), "main.py", "alerts", "scan-full"],
            cwd=str(toolkit_dir), capture_output=True, text=True, timeout=600,
        )
        if result.returncode != 0:
            _send_message(bot_token, chat_id, f"❌ Scan failed:\n{result.stderr[:500]}")
        return True

    if upper in ("SCAN INDIA", "SCAN IN"):
        _send_message(bot_token, chat_id, "🔄 Running India scan...")
        import subprocess
        toolkit_dir = Path(__file__).parent
        python = toolkit_dir / "venv" / "bin" / "python3"
        result = subprocess.run(
            [str(python), "main.py", "alerts", "scan-india"],
            cwd=str(toolkit_dir), capture_output=True, text=True, timeout=600,
        )
        if result.returncode != 0:
            _send_message(bot_token, chat_id, f"❌ Scan failed:\n{result.stderr[:500]}")
        return True

    if upper in ("SCAN BOTH", "SCAN ALL"):
        _send_message(bot_token, chat_id, "🔄 Running India + US scan...")
        import subprocess
        toolkit_dir = Path(__file__).parent
        python = toolkit_dir / "venv" / "bin" / "python3"
        for cmd in ["scan-india", "scan-full"]:
            subprocess.run(
                [str(python), "main.py", "alerts", cmd],
                cwd=str(toolkit_dir), capture_output=True, text=True, timeout=600,
            )
        return True

    return False


def run():
    config = _load_config()
    tg = config.get("telegram", {})
    bot_token = tg.get("bot_token")
    chat_id = str(tg.get("chat_id"))

    if not bot_token or not chat_id:
        print("Telegram not configured. Run: main.py alerts setup <TOKEN> <CHAT_ID>")
        return

    print(f"Bot started. Listening for messages...")
    offset = 0

    while True:
        updates = _get_updates(bot_token, offset)

        for update in updates:
            offset = update["update_id"] + 1
            msg = update.get("message", {})
            text = msg.get("text", "").strip()
            msg_chat_id = str(msg.get("chat", {}).get("id", ""))

            if msg_chat_id != chat_id or not text:
                continue

            print(f"  Message: {text}")

            # Handle scan commands (run actual scans)
            if _handle_scan_command(text, bot_token, chat_id):
                continue

            # Handle trade commands (BUY/SELL/HOLDINGS/HELP)
            response = _process_command(text)
            if response:
                _send_message(bot_token, chat_id, response)

        if not updates:
            time.sleep(1)


if __name__ == "__main__":
    run()
