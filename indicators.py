import numpy as np
import pandas as pd
import ta

try:
    import talib
    HAS_TALIB = True
except ImportError:
    HAS_TALIB = False


def compute_rsi(close: pd.Series, window: int = 14) -> float | None:
    if len(close) < window + 1:
        return None
    rsi = ta.momentum.RSIIndicator(close, window=window).rsi()
    return round(rsi.iloc[-1], 2) if not rsi.empty else None


def compute_sma(close: pd.Series, window: int = 50) -> float | None:
    if len(close) < window:
        return None
    return round(close.rolling(window).mean().iloc[-1], 2)


def compute_macd(close: pd.Series) -> dict | None:
    if len(close) < 35:
        return None
    macd_ind = ta.trend.MACD(close)
    return {
        "macd": round(macd_ind.macd().iloc[-1], 4),
        "signal": round(macd_ind.macd_signal().iloc[-1], 4),
        "histogram": round(macd_ind.macd_diff().iloc[-1], 4),
    }


def compute_bollinger(close: pd.Series, window: int = 20) -> dict | None:
    if len(close) < window:
        return None
    bb = ta.volatility.BollingerBands(close, window=window)
    price = close.iloc[-1]
    upper = bb.bollinger_hband().iloc[-1]
    lower = bb.bollinger_lband().iloc[-1]
    width = upper - lower
    position = (price - lower) / width if width > 0 else 0.5
    return {
        "upper": round(upper, 2),
        "lower": round(lower, 2),
        "position": round(position, 2),
    }


def compute_volume_spike(volume: pd.Series, window: int = 20) -> float | None:
    if len(volume) < window + 1:
        return None
    avg_vol = volume.iloc[-(window + 1):-1].mean()
    if avg_vol == 0:
        return None
    return round(volume.iloc[-1] / avg_vol, 2)


# ─── TA-Lib Enhanced Indicators ─────────────────────────────────────────

def compute_stochastic(high: pd.Series, low: pd.Series, close: pd.Series) -> dict | None:
    """Stochastic oscillator — better overbought/oversold than RSI alone."""
    if len(close) < 14:
        return None
    if HAS_TALIB:
        k, d = talib.STOCH(high.values.astype(float), low.values.astype(float), close.values.astype(float))
        return {"k": round(float(k[-1]), 2), "d": round(float(d[-1]), 2)}
    stoch = ta.momentum.StochasticOscillator(high, low, close)
    return {
        "k": round(stoch.stoch().iloc[-1], 2),
        "d": round(stoch.stoch_signal().iloc[-1], 2),
    }


def compute_atr(high: pd.Series, low: pd.Series, close: pd.Series, window: int = 14) -> float | None:
    """Average True Range — measures volatility. Low ATR = ranging, high ATR = trending."""
    if len(close) < window + 1:
        return None
    if HAS_TALIB:
        atr = talib.ATR(high.values.astype(float), low.values.astype(float), close.values.astype(float), timeperiod=window)
        return round(float(atr[-1]), 4)
    atr = ta.volatility.AverageTrueRange(high, low, close, window=window)
    return round(atr.average_true_range().iloc[-1], 4)


def compute_atr_percent(high: pd.Series, low: pd.Series, close: pd.Series, window: int = 14) -> float | None:
    """ATR as percentage of price — comparable across stocks."""
    atr = compute_atr(high, low, close, window)
    if atr is None:
        return None
    price = close.iloc[-1]
    return round(atr / price * 100, 2) if price > 0 else None


def compute_obv_trend(close: pd.Series, volume: pd.Series, window: int = 20) -> str | None:
    """On-Balance Volume trend — rising OBV = accumulation, falling = distribution."""
    if len(close) < window + 1:
        return None
    if HAS_TALIB:
        obv = pd.Series(talib.OBV(close.values.astype(float), volume.values.astype(float)))
    else:
        obv = ta.volume.OnBalanceVolumeIndicator(close, volume).on_balance_volume()
    obv_sma = obv.rolling(window).mean()
    if obv.iloc[-1] > obv_sma.iloc[-1]:
        return "accumulation"
    return "distribution"


def compute_williams_r(high: pd.Series, low: pd.Series, close: pd.Series, window: int = 14) -> float | None:
    """Williams %R — momentum. Below -80 = oversold, above -20 = overbought."""
    if len(close) < window:
        return None
    if HAS_TALIB:
        wr = talib.WILLR(high.values.astype(float), low.values.astype(float), close.values.astype(float), timeperiod=window)
        return round(float(wr[-1]), 2)
    wr = ta.momentum.WilliamsRIndicator(high, low, close, lbp=window)
    return round(wr.williams_r().iloc[-1], 2)


def detect_candlestick_patterns(open_: pd.Series, high: pd.Series, low: pd.Series, close: pd.Series) -> list[str]:
    """Detect reversal/continuation candlestick patterns using TA-Lib."""
    if not HAS_TALIB or len(close) < 5:
        return []

    o, h, l, c = open_.values.astype(float), high.values.astype(float), low.values.astype(float), close.values.astype(float)
    patterns = []

    # Bullish reversal patterns
    if talib.CDLHAMMER(o, h, l, c)[-1] > 0:
        patterns.append("Hammer (bullish reversal)")
    if talib.CDLENGULFING(o, h, l, c)[-1] > 0:
        patterns.append("Bullish Engulfing")
    if talib.CDLMORNINGSTAR(o, h, l, c)[-1] > 0:
        patterns.append("Morning Star (strong bullish)")
    if talib.CDLPIERCING(o, h, l, c)[-1] > 0:
        patterns.append("Piercing Line (bullish)")
    if talib.CDLHARAMI(o, h, l, c)[-1] > 0:
        patterns.append("Bullish Harami")

    # Bearish reversal patterns
    if talib.CDLHANGINGMAN(o, h, l, c)[-1] < 0:
        patterns.append("Hanging Man (bearish reversal)")
    if talib.CDLENGULFING(o, h, l, c)[-1] < 0:
        patterns.append("Bearish Engulfing")
    if talib.CDLEVENINGSTAR(o, h, l, c)[-1] < 0:
        patterns.append("Evening Star (strong bearish)")
    if talib.CDLSHOOTINGSTAR(o, h, l, c)[-1] < 0:
        patterns.append("Shooting Star (bearish)")

    # Indecision
    if talib.CDLDOJI(o, h, l, c)[-1] != 0:
        patterns.append("Doji (indecision)")

    return patterns


def compute_enhanced_indicators(hist: pd.DataFrame) -> dict:
    """Compute all TA-Lib enhanced indicators for a stock. Returns a dict of signals."""
    close = hist["Close"]
    high = hist["High"]
    low = hist["Low"]
    volume = hist["Volume"]
    open_ = hist["Open"]

    result = {
        "stochastic": compute_stochastic(high, low, close),
        "atr_pct": compute_atr_percent(high, low, close),
        "obv_trend": compute_obv_trend(close, volume),
        "williams_r": compute_williams_r(high, low, close),
        "candlestick_patterns": detect_candlestick_patterns(open_, high, low, close),
    }

    # Compute a bonus score from enhanced indicators
    bonus = 0
    reasons = []

    stoch = result["stochastic"]
    if stoch:
        if stoch["k"] < 20 and stoch["d"] < 20:
            bonus += 8
            reasons.append(f"Stochastic oversold ({stoch['k']:.0f})")
        elif stoch["k"] > 80 and stoch["d"] > 80:
            bonus -= 5
            reasons.append(f"Stochastic overbought ({stoch['k']:.0f})")

    wr = result["williams_r"]
    if wr is not None:
        if wr < -80:
            bonus += 5
            reasons.append(f"Williams %R oversold ({wr:.0f})")
        elif wr > -20:
            bonus -= 5

    obv = result["obv_trend"]
    if obv == "accumulation":
        bonus += 5
        reasons.append("OBV: accumulation (smart money buying)")
    elif obv == "distribution":
        bonus -= 5
        reasons.append("OBV: distribution (smart money selling)")

    patterns = result["candlestick_patterns"]
    bullish = [p for p in patterns if "bullish" in p.lower() or "Morning" in p or "Hammer" in p or "Piercing" in p]
    bearish = [p for p in patterns if "bearish" in p.lower() or "Evening" in p or "Shooting" in p or "Hanging" in p]
    if bullish:
        bonus += 8
        reasons.append(f"Pattern: {bullish[0]}")
    if bearish:
        bonus -= 8
        reasons.append(f"Pattern: {bearish[0]}")

    atr_pct = result["atr_pct"]
    if atr_pct is not None and atr_pct < 1.0:
        bonus -= 3
        reasons.append(f"Low volatility (ATR {atr_pct:.1f}%) — weak signals")

    result["bonus"] = bonus
    result["reasons"] = reasons
    return result
