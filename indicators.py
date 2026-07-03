import pandas as pd
import ta


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
        "position": round(position, 2),  # 0 = at lower band, 1 = at upper
    }


def compute_volume_spike(volume: pd.Series, window: int = 20) -> float | None:
    if len(volume) < window + 1:
        return None
    avg_vol = volume.iloc[-(window + 1):-1].mean()
    if avg_vol == 0:
        return None
    return round(volume.iloc[-1] / avg_vol, 2)
