"""Preset trading strategies for backtesting.

Each strategy is a function: (current_row, lookback_df) -> "buy" | "sell" | None
- current_row: the current day's data (with precomputed indicators)
- lookback_df: all data up to and including today
"""

import pandas as pd


def rsi_mean_reversion(row: pd.Series, lookback: pd.DataFrame) -> str | None:
    """Buy when RSI drops below 30 (oversold), sell when RSI rises above 70 (overbought).
    Classic mean-reversion strategy — works well in range-bound markets."""
    rsi = row.get("rsi")
    if rsi is None:
        return None
    if rsi < 30:
        return "buy"
    if rsi > 70:
        return "sell"
    return None


def rsi_conservative(row: pd.Series, lookback: pd.DataFrame) -> str | None:
    """Tighter RSI bands: buy < 25, sell > 65. Fewer trades, higher conviction."""
    rsi = row.get("rsi")
    if rsi is None:
        return None
    if rsi < 25:
        return "buy"
    if rsi > 65:
        return "sell"
    return None


def golden_cross(row: pd.Series, lookback: pd.DataFrame) -> str | None:
    """Buy when 50-day SMA crosses above 200-day SMA (golden cross).
    Sell when 50-day crosses below (death cross). Classic trend-following."""
    sma_50 = row.get("sma_50")
    sma_200 = row.get("sma_200")
    if sma_50 is None or sma_200 is None:
        return None

    prev = lookback.iloc[-2]
    prev_50 = prev.get("sma_50")
    prev_200 = prev.get("sma_200")
    if prev_50 is None or prev_200 is None:
        return None

    if prev_50 <= prev_200 and sma_50 > sma_200:
        return "buy"
    if prev_50 >= prev_200 and sma_50 < sma_200:
        return "sell"
    return None


def sma_trend(row: pd.Series, lookback: pd.DataFrame) -> str | None:
    """Buy when price crosses above SMA50, sell when it crosses below.
    More responsive than golden cross — catches trends earlier."""
    sma_50 = row.get("sma_50")
    if sma_50 is None:
        return None

    price = row["Close"]
    prev_price = lookback["Close"].iloc[-2]

    if prev_price <= sma_50 and price > sma_50:
        return "buy"
    if prev_price >= sma_50 and price < sma_50:
        return "sell"
    return None


def macd_crossover(row: pd.Series, lookback: pd.DataFrame) -> str | None:
    """Buy when MACD crosses above signal line, sell when it crosses below.
    Good momentum indicator — catches trend changes."""
    macd = row.get("macd")
    signal = row.get("macd_signal")
    if macd is None or signal is None:
        return None

    prev = lookback.iloc[-2]
    prev_macd = prev.get("macd")
    prev_signal = prev.get("macd_signal")
    if prev_macd is None or prev_signal is None:
        return None

    if prev_macd <= prev_signal and macd > signal:
        return "buy"
    if prev_macd >= prev_signal and macd < signal:
        return "sell"
    return None


def bollinger_bounce(row: pd.Series, lookback: pd.DataFrame) -> str | None:
    """Buy when price touches lower Bollinger Band, sell at upper band.
    Works in sideways markets, fails in strong trends."""
    price = row["Close"]
    bb_lower = row.get("bb_lower")
    bb_upper = row.get("bb_upper")
    if bb_lower is None or bb_upper is None:
        return None

    if price <= bb_lower:
        return "buy"
    if price >= bb_upper:
        return "sell"
    return None


def combined_momentum(row: pd.Series, lookback: pd.DataFrame) -> str | None:
    """Multi-signal strategy: buy when RSI < 40 AND MACD histogram is positive
    AND price is above SMA200. Sell when RSI > 65 OR price drops below SMA200.
    Higher conviction entries with trend confirmation."""
    rsi = row.get("rsi")
    macd_hist = row.get("macd_hist")
    sma_200 = row.get("sma_200")
    price = row["Close"]

    if rsi is None or macd_hist is None or sma_200 is None:
        return None

    if rsi < 40 and macd_hist > 0 and price > sma_200:
        return "buy"
    if rsi > 65 or price < sma_200 * 0.97:
        return "sell"
    return None


def dip_buyer(row: pd.Series, lookback: pd.DataFrame) -> str | None:
    """Buy 5%+ dips from recent highs when above SMA200 (uptrend dip).
    Sell after 10% gain or if SMA200 breaks."""
    sma_200 = row.get("sma_200")
    if sma_200 is None or len(lookback) < 20:
        return None

    price = row["Close"]
    recent_high = lookback["Close"].iloc[-20:].max()
    dip_pct = (recent_high - price) / recent_high

    if dip_pct > 0.05 and price > sma_200:
        return "buy"

    recent_low = lookback["Close"].iloc[-20:].min()
    if price > recent_low * 1.10 or price < sma_200 * 0.98:
        return "sell"
    return None


# Registry for CLI access
STRATEGIES = {
    "rsi": (rsi_mean_reversion, "RSI Mean Reversion (buy <30, sell >70)"),
    "rsi-conservative": (rsi_conservative, "RSI Conservative (buy <25, sell >65)"),
    "golden-cross": (golden_cross, "Golden Cross (SMA 50/200 crossover)"),
    "sma-trend": (sma_trend, "SMA Trend (price vs SMA50 crossover)"),
    "macd": (macd_crossover, "MACD Crossover"),
    "bollinger": (bollinger_bounce, "Bollinger Band Bounce"),
    "momentum": (combined_momentum, "Combined Momentum (RSI + MACD + SMA200)"),
    "dip-buyer": (dip_buyer, "Dip Buyer (5% dips in uptrends)"),
}
