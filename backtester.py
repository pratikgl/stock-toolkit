"""Backtesting engine — run trading strategies against historical data."""

import yfinance as yf
import pandas as pd
import numpy as np
from dataclasses import dataclass, field
from tabulate import tabulate

from indicators import compute_rsi, compute_sma, compute_macd, compute_bollinger


@dataclass
class Trade:
    entry_date: str
    entry_price: float
    exit_date: str | None = None
    exit_price: float | None = None
    shares: float = 0
    side: str = "long"

    @property
    def pnl(self) -> float | None:
        if self.exit_price is None:
            return None
        if self.side == "long":
            return (self.exit_price - self.entry_price) * self.shares
        return (self.entry_price - self.exit_price) * self.shares

    @property
    def pnl_pct(self) -> float | None:
        if self.exit_price is None:
            return None
        if self.side == "long":
            return (self.exit_price / self.entry_price - 1) * 100
        return (self.entry_price / self.exit_price - 1) * 100


@dataclass
class BacktestResult:
    ticker: str
    strategy_name: str
    period: str
    initial_capital: float
    final_capital: float
    trades: list[Trade] = field(default_factory=list)
    equity_curve: pd.Series | None = None
    benchmark_curve: pd.Series | None = None

    @property
    def total_return_pct(self) -> float:
        return (self.final_capital / self.initial_capital - 1) * 100

    @property
    def num_trades(self) -> int:
        return len(self.trades)

    @property
    def winning_trades(self) -> int:
        return sum(1 for t in self.trades if t.pnl and t.pnl > 0)

    @property
    def losing_trades(self) -> int:
        return sum(1 for t in self.trades if t.pnl and t.pnl <= 0)

    @property
    def win_rate(self) -> float:
        closed = [t for t in self.trades if t.pnl is not None]
        if not closed:
            return 0
        return self.winning_trades / len(closed) * 100

    @property
    def avg_win(self) -> float:
        wins = [t.pnl_pct for t in self.trades if t.pnl and t.pnl > 0]
        return np.mean(wins) if wins else 0

    @property
    def avg_loss(self) -> float:
        losses = [t.pnl_pct for t in self.trades if t.pnl and t.pnl <= 0]
        return np.mean(losses) if losses else 0

    @property
    def max_drawdown(self) -> float:
        if self.equity_curve is None or self.equity_curve.empty:
            return 0
        peak = self.equity_curve.expanding().max()
        drawdown = (self.equity_curve - peak) / peak * 100
        return drawdown.min()

    @property
    def sharpe_ratio(self) -> float:
        if self.equity_curve is None or len(self.equity_curve) < 2:
            return 0
        daily_returns = self.equity_curve.pct_change().dropna()
        if daily_returns.std() == 0:
            return 0
        return (daily_returns.mean() / daily_returns.std()) * np.sqrt(252)

    @property
    def benchmark_return(self) -> float | None:
        if self.benchmark_curve is None or self.benchmark_curve.empty:
            return None
        return (self.benchmark_curve.iloc[-1] / self.benchmark_curve.iloc[0] - 1) * 100

    @property
    def profit_factor(self) -> float:
        gross_profit = sum(t.pnl for t in self.trades if t.pnl and t.pnl > 0)
        gross_loss = abs(sum(t.pnl for t in self.trades if t.pnl and t.pnl <= 0))
        if gross_loss == 0:
            return float("inf") if gross_profit > 0 else 0
        return gross_profit / gross_loss


class Backtester:
    def __init__(
        self,
        ticker: str,
        period: str = "5y",
        initial_capital: float = 3500,  # ~3 lakh INR
        commission_pct: float = 0.0,    # IBKR has $0 commission on US stocks
    ):
        self.ticker = ticker
        self.period = period
        self.initial_capital = initial_capital
        self.commission_pct = commission_pct
        self._hist = None

    def _load_data(self) -> pd.DataFrame:
        if self._hist is not None:
            return self._hist
        stock = yf.Ticker(self.ticker)
        self._hist = stock.history(period=self.period)
        if self._hist.empty:
            raise ValueError(f"No data for {self.ticker}")
        return self._hist

    def _precompute_indicators(self, hist: pd.DataFrame) -> pd.DataFrame:
        df = hist.copy()
        close = df["Close"]

        # RSI
        from ta.momentum import RSIIndicator
        df["rsi"] = RSIIndicator(close, window=14).rsi()

        # SMAs
        df["sma_20"] = close.rolling(20).mean()
        df["sma_50"] = close.rolling(50).mean()
        df["sma_200"] = close.rolling(200).mean()

        # MACD
        from ta.trend import MACD
        macd = MACD(close)
        df["macd"] = macd.macd()
        df["macd_signal"] = macd.macd_signal()
        df["macd_hist"] = macd.macd_diff()

        # Bollinger
        from ta.volatility import BollingerBands
        bb = BollingerBands(close, window=20)
        df["bb_upper"] = bb.bollinger_hband()
        df["bb_lower"] = bb.bollinger_lband()

        # Volume MA
        df["vol_ma20"] = df["Volume"].rolling(20).mean()

        return df

    def run(self, strategy_fn, strategy_name: str = "Custom") -> BacktestResult:
        hist = self._load_data()
        df = self._precompute_indicators(hist)

        capital = self.initial_capital
        position = 0.0
        trades: list[Trade] = []
        current_trade: Trade | None = None
        equity = []

        for i in range(200, len(df)):  # skip first 200 rows for indicator warmup
            row = df.iloc[i]
            lookback = df.iloc[:i + 1]
            date = str(row.name.date())
            price = row["Close"]

            signal = strategy_fn(row, lookback)

            if signal == "buy" and position == 0:
                shares = capital / price
                cost = capital * self.commission_pct / 100
                capital -= cost
                position = shares
                current_trade = Trade(
                    entry_date=date,
                    entry_price=price,
                    shares=shares,
                )

            elif signal == "sell" and position > 0 and current_trade:
                proceeds = position * price
                cost = proceeds * self.commission_pct / 100
                capital = proceeds - cost
                position = 0
                current_trade.exit_date = date
                current_trade.exit_price = price
                trades.append(current_trade)
                current_trade = None

            portfolio_value = capital if position == 0 else position * price
            equity.append(portfolio_value)

        # Close any open position at end
        if position > 0 and current_trade:
            final_price = df["Close"].iloc[-1]
            capital = position * final_price
            current_trade.exit_date = str(df.index[-1].date())
            current_trade.exit_price = final_price
            trades.append(current_trade)

        equity_series = pd.Series(equity, index=df.index[200:])
        benchmark = df["Close"].iloc[200:]
        benchmark_normalized = benchmark / benchmark.iloc[0] * self.initial_capital

        return BacktestResult(
            ticker=self.ticker,
            strategy_name=strategy_name,
            period=self.period,
            initial_capital=self.initial_capital,
            final_capital=capital,
            trades=trades,
            equity_curve=equity_series,
            benchmark_curve=benchmark_normalized,
        )


def display_backtest(result: BacktestResult):
    bm = result.benchmark_return

    print(f"\n{'='*70}")
    print(f"  BACKTEST: {result.strategy_name}")
    print(f"  {result.ticker} — {result.period}")
    print(f"{'='*70}")

    rows = [
        ["Initial Capital", f"${result.initial_capital:,.2f}"],
        ["Final Capital", f"${result.final_capital:,.2f}"],
        ["Total Return", f"{result.total_return_pct:+.2f}%"],
        ["Buy & Hold Return", f"{bm:+.2f}%" if bm else "N/A"],
        ["Alpha vs B&H", f"{result.total_return_pct - bm:+.2f}%" if bm else "N/A"],
        [""],
        ["Total Trades", result.num_trades],
        ["Win Rate", f"{result.win_rate:.1f}%"],
        ["Avg Win", f"{result.avg_win:+.2f}%"],
        ["Avg Loss", f"{result.avg_loss:+.2f}%"],
        ["Profit Factor", f"{result.profit_factor:.2f}"],
        [""],
        ["Max Drawdown", f"{result.max_drawdown:.2f}%"],
        ["Sharpe Ratio", f"{result.sharpe_ratio:.2f}"],
    ]

    for row in rows:
        if len(row) == 1:
            print()
        else:
            print(f"    {row[0]:22s}  {row[1]}")

    if result.trades:
        print(f"\n  RECENT TRADES (last 5)")
        trade_rows = []
        for t in result.trades[-5:]:
            trade_rows.append([
                t.entry_date, f"${t.entry_price:.2f}",
                t.exit_date, f"${t.exit_price:.2f}" if t.exit_price else "OPEN",
                f"{t.pnl_pct:+.2f}%" if t.pnl_pct else "N/A",
            ])
        print(tabulate(
            trade_rows,
            headers=["Entry Date", "Entry $", "Exit Date", "Exit $", "Return"],
            tablefmt="simple",
        ))

    beat = result.total_return_pct > (bm or 0)
    print(f"\n  {'BEATS' if beat else 'UNDERPERFORMS'} buy-and-hold by "
          f"{abs(result.total_return_pct - (bm or 0)):.2f}%")
    print()


def compare_strategies(results: list[BacktestResult]):
    print(f"\n{'='*70}")
    print(f"  STRATEGY COMPARISON — {results[0].ticker} ({results[0].period})")
    print(f"{'='*70}")

    rows = []
    for r in results:
        rows.append([
            r.strategy_name,
            f"{r.total_return_pct:+.2f}%",
            r.num_trades,
            f"{r.win_rate:.0f}%",
            f"{r.sharpe_ratio:.2f}",
            f"{r.max_drawdown:.1f}%",
            f"{r.profit_factor:.2f}",
        ])

    bm = results[0].benchmark_return
    if bm is not None:
        rows.append([
            "Buy & Hold (benchmark)",
            f"{bm:+.2f}%",
            1, "—", "—", "—", "—",
        ])

    print(tabulate(
        rows,
        headers=["Strategy", "Return", "Trades", "Win%", "Sharpe", "Max DD", "PF"],
        tablefmt="simple",
    ))
    print()
