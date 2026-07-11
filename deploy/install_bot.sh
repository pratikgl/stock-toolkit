#!/bin/bash
# Run this on the Oracle VM to install the real-time bot service.
# Usage: bash deploy/install_bot.sh

set -e

echo "=== Installing Real-time Telegram Bot ==="

# Copy service file
sudo cp deploy/stock-bot.service /etc/systemd/system/stock-bot.service
sudo systemctl daemon-reload
sudo systemctl enable stock-bot
sudo systemctl start stock-bot

# Remove the 5-min cron for telegram (bot service handles it now)
crontab -l | grep -v "check_telegram_trades" | crontab -

echo ""
echo "Bot service installed and running."
echo ""
echo "Commands:"
echo "  sudo systemctl status stock-bot    — check if running"
echo "  sudo systemctl restart stock-bot   — restart"
echo "  sudo journalctl -u stock-bot -f    — view live logs"
echo ""
echo "Test: send HELP to your Telegram bot — should reply instantly."
