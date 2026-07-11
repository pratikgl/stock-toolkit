#!/bin/bash
# Freqtrade setup script for Oracle VM.
# Run this AFTER the main setup.sh has been run.
# Usage: bash deploy/setup_freqtrade.sh

set -e

echo "=== Freqtrade Setup ==="
echo ""

# 1. Install Freqtrade
echo "[1/5] Installing Freqtrade..."
cd ~
if [ -d "freqtrade" ]; then
    echo "  Freqtrade directory exists, updating..."
    cd freqtrade && git pull
else
    git clone https://github.com/freqtrade/freqtrade.git
    cd freqtrade
fi

# Install in a separate venv
echo "[2/5] Setting up Python environment..."
python3 -m venv .venv
.venv/bin/pip install -U pip -q
.venv/bin/pip install -e . -q 2>&1 | tail -3
.venv/bin/freqtrade --version

# 3. Create user data directory
echo "[3/5] Creating user data..."
.venv/bin/freqtrade create-userdir --userdir user_data

# 4. Configure
echo "[4/5] Configuring..."
echo ""

if [ ! -f user_data/config.json ]; then
    read -p "Enter Binance API Key: " BINANCE_KEY
    read -p "Enter Binance API Secret: " BINANCE_SECRET

    # Read Telegram config from stock-toolkit
    TELEGRAM_TOKEN=""
    TELEGRAM_CHAT=""
    if [ -f ~/stock-toolkit/alert_config.json ]; then
        TELEGRAM_TOKEN=$(python3 -c "import json; d=json.load(open('$HOME/stock-toolkit/alert_config.json')); print(d.get('telegram',{}).get('bot_token',''))")
        TELEGRAM_CHAT=$(python3 -c "import json; d=json.load(open('$HOME/stock-toolkit/alert_config.json')); print(d.get('telegram',{}).get('chat_id',''))")
    fi

    cat > user_data/config.json << CONF
{
    "max_open_trades": 3,
    "stake_currency": "USDT",
    "stake_amount": "unlimited",
    "tradable_balance_ratio": 0.95,
    "dry_run": true,
    "dry_run_wallet": 500,
    "cancel_open_orders_on_exit": false,
    "trading_mode": "spot",

    "exchange": {
        "name": "binance",
        "key": "${BINANCE_KEY}",
        "secret": "${BINANCE_SECRET}",
        "ccxt_sync_config": {
            "enableRateLimit": true
        },
        "pair_whitelist": [
            "BTC/USDT", "ETH/USDT", "SOL/USDT", "BNB/USDT",
            "XRP/USDT", "ADA/USDT", "AVAX/USDT", "DOT/USDT",
            "MATIC/USDT", "LINK/USDT"
        ]
    },

    "entry_pricing": {
        "price_side": "same",
        "use_order_book": true,
        "order_book_top": 1
    },
    "exit_pricing": {
        "price_side": "same",
        "use_order_book": true,
        "order_book_top": 1
    },

    "telegram": {
        "enabled": true,
        "token": "${TELEGRAM_TOKEN}",
        "chat_id": "${TELEGRAM_CHAT}",
        "notification_settings": {
            "status": "silent",
            "warning": "on",
            "startup": "on",
            "entry": "on",
            "exit": "on"
        }
    },

    "api_server": {
        "enabled": false
    },

    "bot_name": "freqtrade-crypto",
    "initial_state": "running",
    "internals": {
        "process_throttle_secs": 5
    }
}
CONF
    echo "  Config created."
else
    echo "  Config already exists, skipping."
fi

# 5. Download sample strategy
echo "[5/5] Installing strategy..."
cat > user_data/strategies/BollingerRSI.py << 'STRAT'
"""Simple Bollinger + RSI strategy — buy dips in uptrends."""
from freqtrade.strategy import IStrategy
from pandas import DataFrame
import talib.abstract as ta


class BollingerRSI(IStrategy):
    INTERFACE_VERSION = 3
    timeframe = '1h'
    can_short = False

    minimal_roi = {"0": 0.05, "30": 0.03, "60": 0.02, "120": 0.01}
    stoploss = -0.08
    trailing_stop = True
    trailing_stop_positive = 0.02
    trailing_stop_positive_offset = 0.04

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe['rsi'] = ta.RSI(dataframe, timeperiod=14)
        bollinger = ta.BBANDS(dataframe, timeperiod=20, nbdevup=2, nbdevdn=2)
        dataframe['bb_lower'] = bollinger['lowerband']
        dataframe['bb_upper'] = bollinger['upperband']
        dataframe['bb_mid'] = bollinger['middleband']
        dataframe['sma_200'] = ta.SMA(dataframe, timeperiod=200)
        dataframe['volume_mean'] = dataframe['volume'].rolling(20).mean()
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe.loc[
            (
                (dataframe['rsi'] < 35) &
                (dataframe['close'] < dataframe['bb_lower']) &
                (dataframe['close'] > dataframe['sma_200']) &
                (dataframe['volume'] > dataframe['volume_mean'])
            ),
            'enter_long'] = 1
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe.loc[
            (
                (dataframe['rsi'] > 70) |
                (dataframe['close'] > dataframe['bb_upper'])
            ),
            'exit_long'] = 1
        return dataframe
STRAT
echo "  BollingerRSI strategy installed."

# Create systemd service
sudo tee /etc/systemd/system/freqtrade.service > /dev/null << SVC
[Unit]
Description=Freqtrade Crypto Trading Bot
After=network.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/home/ubuntu/freqtrade
ExecStart=/home/ubuntu/freqtrade/.venv/bin/freqtrade trade --config user_data/config.json --strategy BollingerRSI
Restart=always
RestartSec=30

[Install]
WantedBy=multi-user.target
SVC

echo ""
echo "=== Freqtrade Setup Complete ==="
echo ""
echo "IMPORTANT: It's configured in DRY RUN mode (paper trading)."
echo "No real money will be used until you change dry_run to false."
echo ""
echo "Next steps:"
echo ""
echo "  1. Backtest the strategy:"
echo "     cd ~/freqtrade"
echo "     .venv/bin/freqtrade download-data --pairs BTC/USDT ETH/USDT SOL/USDT --timeframe 1h --days 180"
echo "     .venv/bin/freqtrade backtesting --strategy BollingerRSI --timeframe 1h"
echo ""
echo "  2. Start dry-run (paper trading):"
echo "     sudo systemctl enable freqtrade"
echo "     sudo systemctl start freqtrade"
echo "     sudo journalctl -u freqtrade -f   (watch logs)"
echo ""
echo "  3. After 1-2 weeks of profitable dry-run, go live:"
echo "     Edit ~/freqtrade/user_data/config.json"
echo "     Change dry_run to false"
echo "     Change dry_run_wallet to your actual USDT balance"
echo "     sudo systemctl restart freqtrade"
echo ""
echo "  Telegram: Freqtrade will send buy/sell notifications"
echo "  to the same Telegram bot as your stock toolkit."
