#!/bin/bash
# Cron-friendly alert scanner.
# Add to crontab for automated daily alerts:
#   crontab -e
#   30 19 * * 1-5 /Users/pratik.goyal/Documents/inmobi/stock-toolkit/run_scan.sh
#
# This runs at 7:30 PM IST (Mon-Fri) = 10:00 AM EST (market open)

DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$DIR"

./venv/bin/python3 main.py alerts scan 2>&1 >> scan.log

echo "$(date): scan complete" >> scan.log
