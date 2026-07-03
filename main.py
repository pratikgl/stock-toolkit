#!/usr/bin/env python3
"""Stock Toolkit — Screener + Analyzer for US stocks."""

import argparse
import sys

from screener import run_screener, display_results
from analyzer import analyze_stock, display_analysis
from backtester import Backtester, display_backtest, compare_strategies
from strategies import STRATEGIES
from watchlist import add_stock, remove_stock, display_watchlist, add_preset_watchlist
from scanner import run_scan, run_full_scan
from notifier import configure_telegram
from portfolio import buy as portfolio_buy, sell as portfolio_sell, show_portfolio, show_transactions
from tax import display_tax_summary, display_tcs_estimate, display_full_tax_guide
import ibkr
from signals import display_enhanced_signals


def cmd_screen(args):
    if args.tickers:
        tickers = [t.strip().upper() for t in args.tickers.split(",")]
        df = run_screener(tickers=tickers, max_workers=args.workers, enhanced=args.enhanced)
    else:
        df = run_screener(max_workers=args.workers, enhanced=args.enhanced)
    display_results(df, top_n=args.top)
    if args.output:
        df.to_csv(args.output, index=False)
        print(f"Saved to {args.output}")


def cmd_analyze(args):
    for ticker in args.tickers:
        analysis = analyze_stock(ticker.upper())
        display_analysis(analysis)


def cmd_quick(args):
    """Screen a small set of popular stocks for quick results."""
    popular = [
        "AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META", "TSLA",
        "BRK-B", "JPM", "V", "UNH", "JNJ", "WMT", "PG", "MA",
        "HD", "XOM", "COST", "ABBV", "CRM", "AMD", "NFLX", "ADBE",
        "LLY", "MRK", "PEP", "KO", "AVGO", "TMO", "ORCL",
    ]
    df = run_screener(tickers=popular, max_workers=args.workers)
    display_results(df, top_n=args.top)


def cmd_backtest(args):
    ticker = args.ticker.upper()
    bt = Backtester(ticker, period=args.period, initial_capital=args.capital)

    if args.strategy == "all":
        results = []
        for name, (fn, desc) in STRATEGIES.items():
            print(f"Running {name}...")
            result = bt.run(fn, strategy_name=name)
            results.append(result)
        compare_strategies(results)
        print("Detailed results for top strategy:\n")
        best = max(results, key=lambda r: r.total_return_pct)
        display_backtest(best)
    else:
        if args.strategy not in STRATEGIES:
            print(f"Unknown strategy: {args.strategy}")
            print(f"Available: {', '.join(STRATEGIES.keys())}")
            sys.exit(1)
        fn, desc = STRATEGIES[args.strategy]
        result = bt.run(fn, strategy_name=args.strategy)
        display_backtest(result)


def cmd_strategies(args):
    print("\nAvailable strategies:\n")
    for name, (fn, desc) in STRATEGIES.items():
        print(f"  {name:20s}  {desc}")
    print(f"\nUsage: main.py backtest AAPL -s rsi")
    print(f"       main.py backtest NVDA -s all  (compare all strategies)\n")


def cmd_alert_setup(args):
    configure_telegram(args.bot_token, args.chat_id)


def cmd_alert_add(args):
    strats = args.strategies.split(",") if args.strategies else None
    for ticker in args.tickers:
        add_stock(ticker, strategies=strats)


def cmd_alert_remove(args):
    for ticker in args.tickers:
        remove_stock(ticker)


def cmd_alert_list(args):
    display_watchlist()


def cmd_alert_preset(args):
    add_preset_watchlist(args.name)


def cmd_alert_scan(args):
    run_scan(notify=not args.no_notify, force=args.force)


def cmd_alert_scan_full(args):
    run_full_scan(notify=not args.no_notify)


def cmd_signals(args):
    for ticker in args.tickers:
        display_enhanced_signals(ticker.upper())


# --- Portfolio commands ---
def cmd_portfolio_show(args):
    show_portfolio()


def cmd_portfolio_buy(args):
    portfolio_buy(args.ticker, args.shares, args.price, args.date)


def cmd_portfolio_sell(args):
    portfolio_sell(args.ticker, args.shares, args.price, args.date)


def cmd_portfolio_history(args):
    show_transactions(args.last)


# --- Tax commands ---
def cmd_tax_calc(args):
    display_tax_summary(args.buy_price, args.sell_price, args.shares,
                        args.buy_date, args.sell_date, args.buy_rate, args.sell_rate)


def cmd_tax_tcs(args):
    display_tcs_estimate(args.amount, args.already_sent)


def cmd_tax_guide(args):
    display_full_tax_guide()


# --- IBKR commands ---
def cmd_ibkr_setup(args):
    ibkr.configure(args.gateway_url, args.account)


def cmd_ibkr_status(args):
    ibkr.check_auth()


def cmd_ibkr_accounts(args):
    ibkr.get_accounts()


def cmd_ibkr_positions(args):
    ibkr.get_positions()


def cmd_ibkr_order(args):
    ibkr.place_order(args.ticker, args.quantity, args.side,
                     order_type=args.type, limit_price=args.limit,
                     dry_run=not args.execute)


def cmd_ibkr_auto_trade(args):
    signals = run_scan(notify=False, force=True)
    ibkr.execute_signals(signals, capital_per_trade=args.capital,
                         dry_run=not args.execute)


def cmd_ibkr_guide(args):
    ibkr.display_setup_guide()


def main():
    parser = argparse.ArgumentParser(description="Stock Toolkit")
    sub = parser.add_subparsers(dest="command", required=True)

    p_screen = sub.add_parser("screen", help="Screen S&P 500 stocks")
    p_screen.add_argument("--tickers", help="Comma-separated tickers (default: all S&P 500)")
    p_screen.add_argument("--top", type=int, default=15, help="Show top N results")
    p_screen.add_argument("--workers", type=int, default=10, help="Parallel workers")
    p_screen.add_argument("--output", "-o", help="Save full results to CSV")
    p_screen.add_argument("--enhanced", "-e", action="store_true",
                          help="Add news/insider/earnings signals to scoring (slower but smarter)")
    p_screen.set_defaults(func=cmd_screen)

    p_analyze = sub.add_parser("analyze", help="Deep-analyze specific stocks")
    p_analyze.add_argument("tickers", nargs="+", help="Ticker symbols to analyze")
    p_analyze.set_defaults(func=cmd_analyze)

    p_quick = sub.add_parser("quick", help="Quick screen of 30 popular stocks")
    p_quick.add_argument("--top", type=int, default=15, help="Show top N results")
    p_quick.add_argument("--workers", type=int, default=10, help="Parallel workers")
    p_quick.set_defaults(func=cmd_quick)

    p_backtest = sub.add_parser("backtest", help="Backtest a strategy on a stock")
    p_backtest.add_argument("ticker", help="Ticker symbol")
    p_backtest.add_argument(
        "--strategy", "-s",
        default="all",
        help=f"Strategy name or 'all' (choices: {', '.join(STRATEGIES.keys())}, all)",
    )
    p_backtest.add_argument("--period", "-p", default="5y", help="History period (1y, 2y, 5y, 10y, max)")
    p_backtest.add_argument("--capital", "-c", type=float, default=3500, help="Starting capital in USD")
    p_backtest.set_defaults(func=cmd_backtest)

    p_strats = sub.add_parser("strategies", help="List available strategies")
    p_strats.set_defaults(func=cmd_strategies)

    p_signals = sub.add_parser("signals", help="Advanced signals: news sentiment, insider trading, earnings")
    p_signals.add_argument("tickers", nargs="+", help="Ticker symbols")
    p_signals.set_defaults(func=cmd_signals)

    # --- Alert commands ---
    p_alerts = sub.add_parser("alerts", help="Manage alerts and watchlist")
    alert_sub = p_alerts.add_subparsers(dest="alert_cmd", required=True)

    p_setup = alert_sub.add_parser("setup", help="Configure Telegram bot")
    p_setup.add_argument("bot_token", help="Telegram bot token from @BotFather")
    p_setup.add_argument("chat_id", help="Your Telegram chat ID (use @userinfobot)")
    p_setup.set_defaults(func=cmd_alert_setup)

    p_add = alert_sub.add_parser("add", help="Add stock to watchlist")
    p_add.add_argument("tickers", nargs="+", help="Ticker symbols")
    p_add.add_argument("--strategies", "-s", help="Comma-separated strategies (default: rsi,momentum,dip-buyer)")
    p_add.set_defaults(func=cmd_alert_add)

    p_remove = alert_sub.add_parser("remove", help="Remove stock from watchlist")
    p_remove.add_argument("tickers", nargs="+", help="Ticker symbols")
    p_remove.set_defaults(func=cmd_alert_remove)

    p_list = alert_sub.add_parser("list", help="Show watchlist")
    p_list.set_defaults(func=cmd_alert_list)

    p_preset = alert_sub.add_parser("preset", help="Add a preset watchlist (top30, tech, dividend)")
    p_preset.add_argument("name", choices=["top30", "tech", "dividend"])
    p_preset.set_defaults(func=cmd_alert_preset)

    p_scan = alert_sub.add_parser("scan", help="Run alert scan now (watchlist only)")
    p_scan.add_argument("--no-notify", action="store_true", help="Don't send Telegram messages")
    p_scan.add_argument("--force", action="store_true", help="Ignore cooldown, send all signals")
    p_scan.set_defaults(func=cmd_alert_scan)

    p_scan_full = alert_sub.add_parser("scan-full", help="Scan ALL S&P 500 stocks with all strategies")
    p_scan_full.add_argument("--no-notify", action="store_true", help="Don't send Telegram messages")
    p_scan_full.set_defaults(func=cmd_alert_scan_full)

    # --- Portfolio commands ---
    p_portfolio = sub.add_parser("portfolio", help="Track your holdings and P&L")
    port_sub = p_portfolio.add_subparsers(dest="port_cmd", required=True)

    p_port_show = port_sub.add_parser("show", help="Show current portfolio with live prices")
    p_port_show.set_defaults(func=cmd_portfolio_show)

    p_port_buy = port_sub.add_parser("buy", help="Record a stock purchase")
    p_port_buy.add_argument("ticker", help="Ticker symbol")
    p_port_buy.add_argument("shares", type=float, help="Number of shares")
    p_port_buy.add_argument("price", type=float, help="Purchase price per share (USD)")
    p_port_buy.add_argument("--date", "-d", help="Buy date YYYY-MM-DD (default: today)")
    p_port_buy.set_defaults(func=cmd_portfolio_buy)

    p_port_sell = port_sub.add_parser("sell", help="Record a stock sale")
    p_port_sell.add_argument("ticker", help="Ticker symbol")
    p_port_sell.add_argument("shares", type=float, help="Number of shares")
    p_port_sell.add_argument("price", type=float, help="Sale price per share (USD)")
    p_port_sell.add_argument("--date", "-d", help="Sell date YYYY-MM-DD (default: today)")
    p_port_sell.set_defaults(func=cmd_portfolio_sell)

    p_port_hist = port_sub.add_parser("history", help="Show transaction history")
    p_port_hist.add_argument("--last", "-n", type=int, default=20, help="Show last N transactions")
    p_port_hist.set_defaults(func=cmd_portfolio_history)

    # --- Tax commands ---
    p_tax = sub.add_parser("tax", help="India tax calculator for US investments")
    tax_sub = p_tax.add_subparsers(dest="tax_cmd", required=True)

    p_tax_calc = tax_sub.add_parser("calc", help="Calculate capital gains tax")
    p_tax_calc.add_argument("buy_price", type=float, help="Buy price per share (USD)")
    p_tax_calc.add_argument("sell_price", type=float, help="Sell price per share (USD)")
    p_tax_calc.add_argument("shares", type=float, help="Number of shares")
    p_tax_calc.add_argument("buy_date", help="Buy date YYYY-MM-DD")
    p_tax_calc.add_argument("--sell-date", help="Sell date YYYY-MM-DD (default: today)")
    p_tax_calc.add_argument("--buy-rate", type=float, default=83.0, help="USD/INR rate on buy date")
    p_tax_calc.add_argument("--sell-rate", type=float, default=85.0, help="USD/INR rate on sell date")
    p_tax_calc.set_defaults(func=cmd_tax_calc)

    p_tax_tcs = tax_sub.add_parser("tcs", help="Calculate TCS on remittance")
    p_tax_tcs.add_argument("amount", type=float, help="Remittance amount in INR")
    p_tax_tcs.add_argument("--already-sent", type=float, default=0, help="Already remitted this FY (INR)")
    p_tax_tcs.set_defaults(func=cmd_tax_tcs)

    p_tax_guide = tax_sub.add_parser("guide", help="Show India tax guide for US investments")
    p_tax_guide.set_defaults(func=cmd_tax_guide)

    # --- IBKR commands ---
    p_ibkr = sub.add_parser("ibkr", help="Interactive Brokers API integration")
    ibkr_sub = p_ibkr.add_subparsers(dest="ibkr_cmd", required=True)

    p_ibkr_setup = ibkr_sub.add_parser("setup", help="Configure IBKR gateway connection")
    p_ibkr_setup.add_argument("--gateway-url", default="https://localhost:5000", help="Gateway URL")
    p_ibkr_setup.add_argument("--account", default="", help="IBKR account ID")
    p_ibkr_setup.set_defaults(func=cmd_ibkr_setup)

    p_ibkr_status = ibkr_sub.add_parser("status", help="Check IBKR auth status")
    p_ibkr_status.set_defaults(func=cmd_ibkr_status)

    p_ibkr_accounts = ibkr_sub.add_parser("accounts", help="List IBKR accounts")
    p_ibkr_accounts.set_defaults(func=cmd_ibkr_accounts)

    p_ibkr_pos = ibkr_sub.add_parser("positions", help="Show IBKR positions")
    p_ibkr_pos.set_defaults(func=cmd_ibkr_positions)

    p_ibkr_order = ibkr_sub.add_parser("order", help="Place an order")
    p_ibkr_order.add_argument("side", choices=["buy", "sell"])
    p_ibkr_order.add_argument("ticker", help="Ticker symbol")
    p_ibkr_order.add_argument("quantity", type=float, help="Number of shares")
    p_ibkr_order.add_argument("--type", default="MKT", choices=["MKT", "LMT"], help="Order type")
    p_ibkr_order.add_argument("--limit", type=float, help="Limit price (for LMT orders)")
    p_ibkr_order.add_argument("--execute", action="store_true", help="Actually place the order (default: dry run)")
    p_ibkr_order.set_defaults(func=cmd_ibkr_order)

    p_ibkr_auto = ibkr_sub.add_parser("auto-trade", help="Execute scanner signals as orders")
    p_ibkr_auto.add_argument("--capital", type=float, default=500, help="USD per trade (default: 500)")
    p_ibkr_auto.add_argument("--execute", action="store_true", help="Actually place orders (default: dry run)")
    p_ibkr_auto.set_defaults(func=cmd_ibkr_auto_trade)

    p_ibkr_guide = ibkr_sub.add_parser("guide", help="Show IBKR setup guide")
    p_ibkr_guide.set_defaults(func=cmd_ibkr_guide)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
