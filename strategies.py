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


def earnings_dip(row: pd.Series, lookback: pd.DataFrame) -> str | None:
    """Buy stocks that dropped 10%+ in a short window (earnings overreaction).
    These tend to recover within 2-4 weeks as the market digests the news."""
    if len(lookback) < 10:
        return None

    price = row["Close"]
    rsi = row.get("rsi")
    sma_200 = row.get("sma_200")

    # Check for a sharp drop in the last 5 days
    price_5d_ago = lookback["Close"].iloc[-6] if len(lookback) > 5 else price
    drop_5d = (price / price_5d_ago - 1) * 100

    # Buy if: dropped 10%+ in 5 days, RSI oversold, and was above SMA200 before the drop
    if drop_5d < -10 and rsi and rsi < 35:
        if sma_200 and price_5d_ago > sma_200:
            return "buy"

    # Sell after bounce or if it keeps falling
    if rsi and rsi > 60:
        return "sell"
    price_10d_ago = lookback["Close"].iloc[-11] if len(lookback) > 10 else price
    if (price / price_10d_ago - 1) * 100 < -20:
        return "sell"
    return None


def relative_strength(row: pd.Series, lookback: pd.DataFrame) -> str | None:
    """Buy stocks outperforming their recent trend with improving momentum.
    Filters out stocks that are cheap for a reason (declining fundamentals)."""
    if len(lookback) < 60:
        return None

    price = row["Close"]
    sma_50 = row.get("sma_50")
    sma_200 = row.get("sma_200")
    rsi = row.get("rsi")
    macd_hist = row.get("macd_hist")

    if sma_50 is None or sma_200 is None or rsi is None:
        return None

    # 1-month and 3-month performance
    price_1m = lookback["Close"].iloc[-22] if len(lookback) > 22 else price
    price_3m = lookback["Close"].iloc[-63] if len(lookback) > 63 else price
    ret_1m = (price / price_1m - 1) * 100
    ret_3m = (price / price_3m - 1) * 100

    # Buy: stock is in uptrend AND outperforming (positive 1m + 3m returns)
    # AND has a mild pullback (RSI 35-50 = not oversold, just a dip)
    if (sma_50 > sma_200 and ret_1m > 0 and ret_3m > 5
            and 30 < rsi < 50 and macd_hist and macd_hist > 0):
        return "buy"

    # Sell: momentum gone
    if ret_1m < -10 or (sma_50 < sma_200 and rsi > 50):
        return "sell"
    return None


def multi_timeframe(row: pd.Series, lookback: pd.DataFrame) -> str | None:
    """Buy only when BOTH weekly and daily timeframes agree.
    Daily: RSI < 40 (short-term dip). Weekly: price above 10-week SMA (long-term uptrend).
    This filters out short-term noise and only buys when the big picture supports it."""
    if len(lookback) < 50:
        return None

    price = row["Close"]
    rsi = row.get("rsi")
    sma_50 = row.get("sma_50")  # ~10 weeks
    sma_200 = row.get("sma_200")
    macd_hist = row.get("macd_hist")

    if rsi is None or sma_50 is None or sma_200 is None:
        return None

    # Weekly view: SMA50 > SMA200 (uptrend) AND price above SMA50
    weekly_bullish = sma_50 > sma_200

    # Daily view: RSI dip (oversold) + MACD turning positive
    daily_dip = rsi < 40
    macd_positive = macd_hist and macd_hist > 0

    # Weekly uptrend confirmation using slope (SMA50 rising over last 10 days)
    sma50_series = lookback["sma_50"].dropna()
    if len(sma50_series) >= 10:
        sma50_slope = sma50_series.iloc[-1] - sma50_series.iloc[-10]
        weekly_rising = sma50_slope > 0
    else:
        weekly_rising = False

    if weekly_bullish and weekly_rising and daily_dip and macd_positive:
        return "buy"

    if rsi > 70 or (not weekly_bullish and rsi > 55):
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
    "earnings-dip": (earnings_dip, "Earnings Dip (10%+ drop overreaction)"),
    "rel-strength": (relative_strength, "Relative Strength (outperformers pulling back)"),
    "multi-tf": (multi_timeframe, "Multi-Timeframe (weekly uptrend + daily dip)"),
}
