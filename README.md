# Stock Toolkit

A personal investment intelligence system for Indian residents investing in US stocks. Built in Python, it combines stock screening, technical analysis, backtesting, Telegram alerts, portfolio tracking with INR conversion, India tax calculations, and Interactive Brokers API integration.

## Why This Exists

Indian mutual funds have delivered inconsistent returns, and the rupee depreciates ~4-5% annually against the USD. Investing in US stocks provides:
- Access to global companies (FAANG, semiconductors, etc.)
- A natural currency hedge (USD appreciation)
- Historically ~10-12% USD returns on S&P 500 + ~4-5% INR depreciation = **14-17% effective INR returns**

This toolkit gives you an **information edge** — instead of guessing, you screen 500 stocks across fundamental + technical signals, backtest strategies before risking money, and get automated alerts when opportunities arise.

## Features

### Phase 1: Screener + Analyzer
- Scans S&P 500 stocks using fundamental filters (P/E, revenue growth, margins, debt) and technical indicators (RSI, SMA crossovers, MACD, Bollinger bands, volume spikes)
- Ranks stocks by a composite score
- Deep-dive analyzer for individual stocks with bull/bear case and verdict (Strong Buy → Strong Sell)

### Phase 2: Backtester
- Test 8 preset strategies against 1-10 years of historical data
- Metrics: total return, win rate, Sharpe ratio, max drawdown, profit factor
- Side-by-side comparison of all strategies vs buy-and-hold benchmark
- Strategies included: RSI mean reversion, golden cross, SMA trend, MACD crossover, Bollinger bounce, combined momentum, dip buyer

### Phase 3: Alert System
- JSON-based watchlist with per-stock strategy assignment
- Alert scanner with 24-hour cooldown (no duplicate spam)
- Telegram bot integration for push notifications
- Cron-ready script for automated daily scans (7:30 PM IST = 10:00 AM EST market open)
- Preset watchlists: top30, tech, dividend

### Phase 4: Portfolio Tracker
- Record buy/sell transactions with cost basis tracking
- Live portfolio view with real-time USD prices and INR conversion
- P&L in both USD and INR
- Transaction history

### Phase 5: IBKR API Integration
- Interactive Brokers Client Portal REST API integration
- View accounts and positions
- Place market and limit orders (with dry-run mode by default)
- Signal-to-order pipeline: scanner signals → IBKR orders automatically
- Setup guide for Indian residents

### Phase 6: Advanced Signals (News, Insider, Earnings)
- **News sentiment** — keyword-scored analysis of Yahoo Finance headlines per stock
- **Insider trading** — tracks insider buy/sell ratio (insider buys are one of the strongest bullish signals)
- **Earnings momentum** — tracks earnings beats/misses (PEAD — stocks that beat estimates tend to keep outperforming)
- All three signals are combined into a bonus score that augments the screener
- Use `--enhanced` flag on screener to include these signals, or `signals NVDA` for standalone view

### Phase 7: GitHub Actions (Cloud Automation)
- Daily scan runs on GitHub Actions at 7:30 PM IST (Mon-Fri) — works even when your laptop is off
- Scans ALL S&P 500 stocks with ALL strategies
- Sends Telegram alerts ranked by conviction (how many strategies agree)
- Scan results saved as GitHub artifacts for 30 days

### India Tax Calculator
- Capital gains tax: LTCG (>24 months, 12.5%) vs STCG (slab rate)
- TCS on LRS remittance (20% above Rs.7 lakh/FY)
- Dividend tax with DTAA credit calculation
- Comprehensive tax guide for US investments

## Setup

```bash
cd stock-toolkit

# Create virtual environment and install dependencies
python3 -m venv venv
./venv/bin/pip install -r requirements.txt

# Verify it works
./venv/bin/python3 main.py quick
```

### Telegram Alerts (Optional)
1. Create a bot via `@BotFather` on Telegram
2. Get your chat ID from `@userinfobot`
3. Configure:
```bash
./venv/bin/python3 main.py alerts setup YOUR_BOT_TOKEN YOUR_CHAT_ID
```

### Automated Daily Alerts — GitHub Actions (Recommended)
No laptop needed. Runs in the cloud automatically.

1. Go to your repo → Settings → Secrets and variables → Actions
2. Add two secrets:
   - `TELEGRAM_BOT_TOKEN` — your bot token from @BotFather
   - `TELEGRAM_CHAT_ID` — your chat ID (number)
3. That's it. The scan runs daily at 7:30 PM IST (Mon-Fri).
4. You can also trigger manually: Actions tab → "Daily Stock Scan" → "Run workflow"

### Automated Daily Alerts — Local Cron (Alternative)
```bash
crontab -e
# Add: runs 7:30 PM IST Mon-Fri (10:00 AM EST market open)
30 19 * * 1-5 /path/to/stock-toolkit/run_scan.sh
```
Note: Only works when your laptop is on and awake.

### IBKR Integration (Optional)
```bash
./venv/bin/python3 main.py ibkr guide   # Full setup instructions
```

## Usage

```bash
PY=./venv/bin/python3

# ── Screening ──
$PY main.py quick                          # Scan 30 popular stocks (~30s)
$PY main.py screen -o results.csv          # Full S&P 500 scan (~10-15 min)
$PY main.py screen --enhanced -o results.csv  # With news/insider/earnings signals
$PY main.py screen --tickers AAPL,MSFT,NVDA

# ── Deep Analysis ──
$PY main.py analyze NVDA META ORCL
$PY main.py signals NVDA META              # News sentiment, insider trades, earnings

# ── Backtesting ──
$PY main.py strategies                     # List available strategies
$PY main.py backtest NVDA -s all           # Compare all strategies (5 years)
$PY main.py backtest AAPL -s rsi -p 3y     # Single strategy, custom period
$PY main.py backtest META -s bollinger -c 5000  # Custom starting capital

# ── Alerts ──
$PY main.py alerts add NVDA META AAPL      # Add to watchlist
$PY main.py alerts add MSFT -s rsi,macd    # Custom strategies per stock
$PY main.py alerts preset top30            # Add 30 popular stocks at once
$PY main.py alerts list                    # View watchlist
$PY main.py alerts scan                    # Run scan + send Telegram alerts
$PY main.py alerts scan --no-notify        # Dry run (terminal only)
$PY main.py alerts scan --force            # Ignore 24h cooldown
$PY main.py alerts scan-full               # Scan ALL S&P 500 (used by GitHub Actions)

# ── Portfolio ──
$PY main.py portfolio buy NVDA 18 194.83 --date 2026-07-04
$PY main.py portfolio buy VOO 7 550.00
$PY main.py portfolio sell NVDA 5 250.00
$PY main.py portfolio show                 # Live P&L in USD + INR
$PY main.py portfolio history              # Transaction log

# ── Tax Calculator ──
$PY main.py tax calc 194 250 18 2026-07-04 --sell-date 2028-08-01
$PY main.py tax tcs 300000 --already-sent 500000
$PY main.py tax guide                      # Full India tax reference

# ── IBKR Trading ──
$PY main.py ibkr setup --account YOUR_ID
$PY main.py ibkr status
$PY main.py ibkr positions
$PY main.py ibkr order buy NVDA 10                     # Dry run
$PY main.py ibkr order buy NVDA 10 --execute            # Live order
$PY main.py ibkr order buy AAPL 5 --type LMT --limit 300
$PY main.py ibkr auto-trade                             # Scan → orders (dry run)
$PY main.py ibkr auto-trade --execute --capital 500     # Live, $500 per trade
```

## How It Works (Flow)

```
  Screener (S&P 500)          Backtest strategies
  Score by fundamentals +     against 5y history
  technicals                  before risking money
         │                           │
         v                           v
  Pick top stocks ──────> Validate strategy works
         │
         v
  Add to watchlist ──> Daily cron scan ──> Telegram alert
                                                │
                                       "NVDA hit buy signal!"
                                                │
                                                v
  Record in portfolio <─── Buy via IBKR <─── You decide
         │
         v
  Track P&L (USD + INR) + estimate India taxes
```

## Strategies

| Strategy | Description | Best For |
|----------|-------------|----------|
| `rsi` | Buy RSI < 30, sell RSI > 70 | Range-bound markets |
| `rsi-conservative` | Buy RSI < 25, sell RSI > 65 | Fewer, higher-conviction trades |
| `golden-cross` | SMA 50/200 crossover | Long-term trend following |
| `sma-trend` | Price vs SMA50 crossover | Catching trends early |
| `macd` | MACD/signal line crossover | Momentum shifts |
| `bollinger` | Buy at lower band, sell at upper | Sideways markets |
| `momentum` | RSI + MACD + SMA200 combined | High-conviction entries |
| `dip-buyer` | Buy 5%+ dips in uptrends | Buying corrections |

## Project Structure

```
stock-toolkit/
├── main.py            # CLI entry point (10 commands)
├── config.py          # Screener thresholds and constants
├── screener.py        # S&P 500 stock screener
├── analyzer.py        # Deep-dive stock analyzer
├── indicators.py      # Technical indicators (RSI, SMA, MACD, Bollinger)
├── signals.py         # Advanced signals (news sentiment, insider, earnings)
├── sp500.py           # S&P 500 ticker list fetcher
├── strategies.py      # 8 preset trading strategies
├── backtester.py      # Backtesting engine
├── watchlist.py       # Watchlist manager (JSON)
├── scanner.py         # Alert scanner (watchlist + full S&P 500 mode)
├── notifier.py        # Telegram notification sender (supports env vars for CI)
├── portfolio.py       # Portfolio tracker with INR conversion
├── tax.py             # India tax calculator (LTCG/STCG/TCS/DTAA)
├── ibkr.py            # Interactive Brokers API integration
├── run_scan.sh        # Cron-ready daily scan script
├── requirements.txt   # Python dependencies
├── .github/workflows/ # GitHub Actions for automated daily scans
└── venv/              # Python virtual environment (local only)
```

## What's Done

- [x] Stock screener with fundamental + technical scoring
- [x] Deep-dive analyzer with bull/bear case verdict
- [x] 8 backtesting strategies with full metrics
- [x] Strategy comparison with buy-and-hold benchmark
- [x] Telegram alert bot with watchlist management
- [x] Alert scanner with deduplication and cooldown
- [x] Cron-ready automated scanning
- [x] Portfolio tracker with live USD + INR P&L
- [x] India tax calculator (LTCG, STCG, TCS, dividends, DTAA)
- [x] IBKR API integration with dry-run safety
- [x] Signal-to-order pipeline (scanner → IBKR orders)
- [x] News sentiment analysis (Yahoo Finance headlines)
- [x] Insider trading signal (buy/sell ratio tracking)
- [x] Earnings momentum signal (beat/miss tracking, PEAD)
- [x] Enhanced screener mode (`--enhanced`) combining all signals
- [x] Full S&P 500 scan mode (`scan-full`) for GitHub Actions
- [x] GitHub Actions workflow for daily cloud-based automated scans
- [x] Conviction ranking (alerts ranked by # of strategies agreeing)

## Future Improvements

- [ ] **News sentiment analysis** — Scrape financial news APIs, score sentiment per stock, add as a signal to the screener
- [ ] **Earnings calendar integration** — Avoid buying before earnings (high volatility), or buy dips after overreactions
- [ ] **Multi-timeframe backtesting** — Test strategies across 1y, 3y, 5y, 10y simultaneously to find robust ones
- [ ] **Portfolio rebalancing alerts** — Notify when your allocation drifts from target (e.g., 70/30 VOO/picks)
- [ ] **Options screening** — Screen for covered calls on holdings for income generation
- [ ] **India MF comparison** — Auto-compare US portfolio returns against Nifty 50, SENSEX, and existing MF returns
- [ ] **Web dashboard (Streamlit)** — Interactive charts, filters, one-click analysis instead of CLI
- [ ] **Sector rotation strategy** — Track sector momentum and rotate between sectors based on macro trends
- [ ] **Stop-loss / take-profit automation** — Auto-sell via IBKR when positions hit predefined thresholds
- [ ] **Historical P&L tracking** — Store daily portfolio snapshots for performance charting over time
- [ ] **Dividend tracker** — Track dividend income, ex-dates, and auto-calculate India tax on dividends
- [ ] **Paper trading mode** — Simulated trading using live prices without real money to validate strategies

## Tech Stack

- **Python 3.14** with venv
- **yfinance** — Yahoo Finance data (prices, fundamentals, history)
- **pandas** — Data manipulation and analysis
- **ta** — Technical analysis indicators
- **tabulate** — Terminal table formatting
- **python-telegram-bot** — Telegram notifications
- **IBKR Client Portal API** — Order execution (REST)

## Disclaimer

This is a personal toolkit for educational and experimental purposes. It is not financial advice. Past performance does not guarantee future results. Always do your own research before investing. The author is not a licensed financial advisor.
