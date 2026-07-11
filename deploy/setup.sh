#!/bin/bash
# Oracle VM setup script — run this once after SSH'ing into your free VM.
# Usage: bash setup.sh

set -e

echo "=== Stock Toolkit — Oracle VM Setup ==="
echo ""

# 1. System dependencies
echo "[1/6] Installing system packages..."
sudo apt-get update -qq
sudo apt-get install -y -qq python3 python3-pip python3-venv git cron

# 2. Clone repo
echo "[2/6] Cloning repo..."
cd ~
if [ -d "stock-toolkit" ]; then
    cd stock-toolkit && git pull
else
    git clone https://github.com/pratikgl/stock-toolkit.git
    cd stock-toolkit
fi

# 3. Python environment
echo "[3/6] Setting up Python environment..."
python3 -m venv venv
./venv/bin/pip install -r requirements.txt -q

# 4. Configure Telegram
echo "[4/6] Configuring Telegram..."
echo ""
if [ ! -f alert_config.json ]; then
    read -p "Enter Telegram Bot Token: " BOT_TOKEN
    read -p "Enter Telegram Chat ID: " CHAT_ID
    ./venv/bin/python3 main.py alerts setup "$BOT_TOKEN" "$CHAT_ID"
else
    echo "  alert_config.json already exists, skipping."
fi

# 5. Set up cron jobs
echo "[5/6] Setting up cron jobs..."
TOOLKIT_DIR=$(pwd)
PYTHON="$TOOLKIT_DIR/venv/bin/python3"

# Write cron entries
CRON_FILE="/tmp/stock-toolkit-cron"
cat > "$CRON_FILE" << CRON
# Stock Toolkit — scan schedules (IST = UTC + 5:30)

# India market close: 3:00 PM IST = 09:30 UTC
30 9 * * 1-5 cd $TOOLKIT_DIR && $PYTHON main.py alerts scan-india >> scan.log 2>&1

# US market open + 1.5hr: 8:30 PM IST = 15:00 UTC
0 15 * * 1-5 cd $TOOLKIT_DIR && $PYTHON main.py alerts scan-full >> scan.log 2>&1 && $PYTHON main.py portfolio sell-check >> scan.log 2>&1

# US market close: 1:00 AM IST = 19:30 UTC
30 19 * * 1-5 cd $TOOLKIT_DIR && $PYTHON main.py alerts scan-full >> scan.log 2>&1 && $PYTHON main.py portfolio sell-check >> scan.log 2>&1

# Process Telegram messages every 5 minutes (real-time bot)
*/5 * * * * cd $TOOLKIT_DIR && $PYTHON -c "from trade_tracker import check_telegram_trades; check_telegram_trades()" >> bot.log 2>&1

# Auto-update from GitHub daily at 6 AM IST = 00:30 UTC
30 0 * * * cd $TOOLKIT_DIR && git pull -q && ./venv/bin/pip install -r requirements.txt -q >> update.log 2>&1
CRON

crontab "$CRON_FILE"
rm "$CRON_FILE"
echo "  Cron jobs installed:"
crontab -l | grep -v "^#" | grep -v "^$" | while read line; do echo "    $line"; done

# 6. Start the cron service
echo "[6/6] Starting cron service..."
sudo systemctl enable cron
sudo systemctl start cron

echo ""
echo "=== Setup Complete ==="
echo ""
echo "Your scans will run at:"
echo "  3:00 PM IST  — India market close"
echo "  8:30 PM IST  — US market open (1.5hr in)"
echo "  1:00 AM IST  — US market close"
echo ""
echo "Telegram bot checks for messages every 5 minutes."
echo "Auto-updates from GitHub daily at 6:00 AM IST."
echo ""
echo "Logs:"
echo "  Scan log:   tail -f ~/stock-toolkit/scan.log"
echo "  Bot log:    tail -f ~/stock-toolkit/bot.log"
echo "  Update log: tail -f ~/stock-toolkit/update.log"
echo ""
echo "To test now:"
echo "  cd ~/stock-toolkit"
echo "  ./venv/bin/python3 main.py alerts scan-india"
echo "  ./venv/bin/python3 main.py alerts scan-full"
