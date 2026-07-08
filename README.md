# Stock Toolkit

Automated US stock trading assistant for Indian investors. Scans all S&P 500 stocks twice daily, sends buy/sell signals to Telegram, tracks your trades, and tells you when to exit — all running on GitHub Actions while you sleep.

## How It Works

```
GitHub Actions runs twice daily (7:30 PM + 1:00 AM IST)
              │
              ├── Reads your trade commands from Telegram
              ├── Scans 503 S&P 500 stocks × 8 strategies
              ├── Backtest-validates top signals against 3 years of data
              ├── Checks your holdings for sell signals
              │
              └── Sends you Telegram messages:
                    • Buy signals (🔥 BUY / ⚡ WATCH)
                    • Sell signals for your holdings (🔴 SELL HALF / SELL ALL)
                    • Timing advice (BUY TODAY / WAIT)
```

## What You Get on Telegram

### Buy Signal — Summary (every scan)

On quiet days:
```
📊 Daily S&P 500 Scan
Scanned 503 stocks

No signals today. Market is quiet.
```

When opportunities exist:
```
📊 Daily S&P 500 Scan
Scanned 503 stocks

🔥 BUY (1):

🔥 NVDA (NVIDIA Corporation) $178.50
   Score: 95 | RSI 26 | Vol 2.3x | BUY TODAY
   3 strategies: bollinger, dip-buyer, rsi
   ✅ Backtest: +54% / 3y, 74% win rate

⚡ WATCH (3):
⚡ DLR $173.30 | RSI 33 — bollinger, dip-buyer
⚡ KEYS $313.86 | RSI 40 — bollinger, dip-buyer
⚡ EME $774.66 | RSI 39 — bollinger, dip-buyer

📈 Sectors: Technology (48), Industrials (29)
```

### Buy Signal — Detail (only for 🔥 BUY tier)

```
🔥 BUY — NVDA (NVIDIA Corporation)

Price: $178.50
RSI: 26.1
Sector: Technology
Strategy: 3 strategies: bollinger, dip-buyer, rsi
Volume: 2.3x average ✓

  • RSI oversold at 26.1
  • Golden cross (SMA50 > SMA200)
  • 18% below 52W high

⏱ BUY TODAY
   RSI turning up from 24→26. Momentum shifting bullish.

💰 $300 = 1.68 shares
```

### Sell Signal (for stocks you own)

```
🔴 SELL HALF — ORCL

Current: $140.27
Your Cost: $170.00 (8 shares)
P&L: -$237.84 (-17.5%)
Held: 125 days (4 months)

Why: Down -17% and below SMA50. Reduce exposure.

📋 Action: Sell 4 of 8 shares
   Keep 4 shares — wait for next signal

💰 Tax: STCG ~20% — Rs.0 (it's a loss)
   ⏳ 20 months to LTCG (12.5%)
```

### Signal Types

| Signal | What It Means | Your Action |
|--------|--------------|-------------|
| 🔥 **BUY** | 3+ strategies agree, backtest-validated | Buy $300 worth on IndMoney/IBKR |
| ⚡ **WATCH** | 2 strategies agree, decent score | Note it. Don't buy yet. |
| 🔴 **SELL HALF** | Overbought or losing momentum | Sell half, keep rest |
| 🔴 **SELL ALL** | Death cross + losses, or down 25%+ | Cut losses, protect capital |
| 🟡 **HOLD** | In profit but close to LTCG threshold | Wait for lower tax rate |
| ⏱ **BUY TODAY** | RSI turning up, reversal starting | Buy now |
| ⏱ **WAIT** | Still falling, don't catch the knife | Wait 1-2 days for bottom |

### Signal Frequency

| Type | How Often | You'll See |
|------|-----------|-----------|
| 🔥 BUY | ~3-4 per month | The ones you act on |
| ⚡ WATCH | ~15-20 per day | Just in summary, ignore |
| No signal | ~30% of days | Most days. That's good. |
| During crashes | Daily 🔥 signals | Best buying opportunities |

## Recording Trades via Telegram

After you buy/sell on IndMoney or IBKR, tell the bot:

```
BUY NVDA 10 194.83        → Records your purchase
SELL NVDA 5 250.00         → Records your sale
HOLDINGS                   → Shows what you own
HELP                       → Shows all commands
```

The bot reads messages during each scan (twice daily). After recording, it monitors your holdings and sends sell signals when needed.

Wrong input gets a clear error:
```
You: BUY NVDA
Bot: ❌ Missing number of shares.
     Format: BUY NVDA SHARES PRICE
     Example: BUY NVDA 10 194.83
```

## What Each Data Point Means

| Data | What | Why It Matters |
|------|------|---------------|
| **Score** (0-150) | Combined quality metric | Higher = stronger signal |
| **RSI** | Overbought (>70) or oversold (<30) | <30 = stock is cheap, might bounce |
| **Volume 2.3x** | Trading volume vs 20-day average | High volume = real buying interest |
| **3 strategies** | How many independent methods agree | Like 3 doctors agreeing on diagnosis |
| **Backtest: +54%, 74% win** | Historical performance of this strategy on this stock | Proof it worked before |
| **Golden cross** | SMA50 crossed above SMA200 | Uptrend confirmed |
| **Death cross** | SMA50 below SMA200 | Downtrend — stock gets penalized |
| **Off 52W high** | How far below peak price | Potential discount or falling knife |
| **💰 $300 = 1.68 shares** | Trade size calculator | So you don't have to math |

## Sell Rules

The bot monitors your holdings and alerts you based on:

| Condition | Action | Why |
|-----------|--------|-----|
| RSI > 75 + up 20%+ | SELL HALF | Lock in profit, stock is overbought |
| RSI > 80 | SELL HALF | Very overbought, take profit |
| Up 50%+ and RSI > 65 | SELL 30% | Trim position, let rest ride |
| Death cross + down 10% | SELL ALL | Trend broken, cut losses |
| Down 25%+ | SELL ALL | Stop loss — protect remaining capital |
| Down 15% + below SMA50 | SELL HALF | Reduce exposure |
| Up 15% but near LTCG | HOLD | Wait for 12.5% tax rate |

## Strategy Testing

Every push to main auto-runs a **full bot simulation**: starts with $1000, follows every buy/sell signal for 3 months, shows the result.

```
FULL BOT SIMULATION (last 3 months)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Starting capital:     $1,000.00
Final value:          $1,103.50
Total return:         +10.35%
Annualized return:    +52.2%
Buy & hold SPY:       +14.41%
Max drawdown:         -4.8%
Trades:               8 buys, 2 sells
Win rate:             75%
```

If the strategy loses money in simulation, the build fails and alerts don't go out. Safe to experiment with strategy changes — push and see.

## Setup

### 1. Clone and install
```bash
git clone https://github.com/pratikgl/stock-toolkit.git
cd stock-toolkit
python3 -m venv venv
./venv/bin/pip install -r requirements.txt
```

### 2. Create Telegram bot
1. Open Telegram → search `@BotFather` → send `/newbot`
2. Copy the bot token
3. Search `@userinfobot` → get your chat ID (a number)
4. Message your new bot (press Start) so it can send you messages

### 3. Configure GitHub Secrets
Go to repo → Settings → Secrets and variables → Actions. Add:
- `TELEGRAM_BOT_TOKEN` — bot token from step 2
- `TELEGRAM_CHAT_ID` — your chat ID from step 2
- `ANTHROPIC_API_KEY` — (optional) for AI analysis on signals

### 4. Done
Scans run automatically twice daily. Push any change to trigger a test + scan.

## India Tax Reference

| Scenario | Tax Rate |
|----------|---------|
| Sell within 24 months (STCG) | Your income slab rate (~20-30%) |
| Sell after 24 months (LTCG) | 12.5% flat |
| LRS remittance first Rs.7L/FY | No TCS |
| LRS above Rs.7L/FY | 20% TCS (adjustable against income tax) |
| US dividends | 25% withheld by US, DTAA credit in India |

Quick tax check: `./venv/bin/python3 main.py tax calc BUY_PRICE SELL_PRICE SHARES BUY_DATE`

## Project Structure

```
stock-toolkit/
├── main.py              # CLI entry point
├── scanner.py           # Full S&P 500 scanner (buy signals + sell monitor)
├── sell_monitor.py      # Sell signal generator for your holdings
├── trade_tracker.py     # Telegram trade input handler
├── screener.py          # Stock screener (fundamental + technical scoring)
├── analyzer.py          # Deep-dive stock analyzer
├── strategies.py        # 8 trading strategies
├── backtester.py        # Backtesting engine
├── indicators.py        # Technical indicators (RSI, SMA, MACD, Bollinger)
├── signals.py           # Advanced signals (news, insider, earnings)
├── ai_analyzer.py       # Claude API integration for signal analysis
├── notifier.py          # Telegram message sender
├── portfolio.py         # Portfolio tracker (USD + INR)
├── tax.py               # India tax calculator
├── ibkr.py              # Interactive Brokers API
├── sp500.py             # S&P 500 ticker list
├── config.py            # Screener thresholds
├── test_strategy.py     # Full bot simulation test (runs on every push)
├── requirements.txt     # Python dependencies
├── .github/workflows/   # GitHub Actions (auto scan + test)
├── holdings.json        # Your trades (tracked in git)
└── watchlist.json       # Watchlist config
```

## What's Done

- [x] S&P 500 screener (fundamental + technical + advanced signals)
- [x] 8 backtesting strategies with historical validation
- [x] Automated twice-daily scans via GitHub Actions
- [x] Telegram buy signals (🔥 BUY / ⚡ WATCH tiers)
- [x] Telegram sell signals for your holdings (SELL HALF / ALL / HOLD)
- [x] Trade recording via Telegram bot commands
- [x] Timing advice (BUY TODAY / WAIT) based on RSI momentum
- [x] Backtest validation in the alert pipeline
- [x] Score-based ranking (strategies + fundamentals + volume)
- [x] Sector context in alerts
- [x] Full bot simulation test on every push
- [x] India tax calculator (LTCG/STCG/TCS/DTAA)
- [x] IBKR API integration
- [x] Auto-trigger: push to main → test → scan

## Future Improvements

- [ ] **Earnings calendar** — avoid buying right before earnings, buy dips after overreactions
- [ ] **Portfolio rebalancing** — alert when 70/30 allocation drifts and needs rebalancing
- [ ] **Sector rotation** — track sector momentum, rotate between sectors based on macro trends
- [ ] **Stop-loss automation** — auto-sell via IBKR API when positions hit thresholds
- [ ] **Dividend tracking** — track dividend income, ex-dates, auto-calculate India tax
- [ ] **Daily P&L snapshots** — store portfolio value daily for performance charts
- [ ] **India MF comparison** — auto-compare US returns against Nifty 50 and your existing MFs
- [ ] **Web dashboard** — Streamlit UI for charts and one-click analysis
- [ ] **Options screening** — screen for covered calls on holdings (income strategy)
- [ ] **Claude API deep analysis** — LLM-based news analysis for high-conviction signals
