import yfinance as yf
import pandas as pd

from indicators import (
    compute_rsi, compute_sma, compute_macd,
    compute_bollinger, compute_volume_spike,
)


def analyze_stock(ticker: str) -> dict:
    stock = yf.Ticker(ticker)
    info = stock.info
    hist = stock.history(period="2y")

    if hist.empty:
        return {"error": f"No data found for {ticker}"}

    close = hist["Close"]
    volume = hist["Volume"]
    price = close.iloc[-1]

    analysis = {
        "ticker": ticker,
        "name": info.get("shortName", ticker),
        "sector": info.get("sector", "Unknown"),
        "industry": info.get("industry", "Unknown"),
        "price": round(price, 2),
        "market_cap": info.get("marketCap"),
        "fundamentals": _analyze_fundamentals(info),
        "technicals": _analyze_technicals(close, volume, price),
        "valuation": _analyze_valuation(info, price),
        "performance": _analyze_performance(hist),
    }

    analysis["verdict"] = _compute_verdict(analysis)
    return analysis


def _analyze_fundamentals(info: dict) -> dict:
    return {
        "pe_ratio": info.get("trailingPE"),
        "forward_pe": info.get("forwardPE"),
        "peg_ratio": info.get("pegRatio"),
        "revenue": info.get("totalRevenue"),
        "revenue_growth": info.get("revenueGrowth"),
        "profit_margin": info.get("profitMargins"),
        "operating_margin": info.get("operatingMargins"),
        "roe": info.get("returnOnEquity"),
        "roa": info.get("returnOnAssets"),
        "debt_to_equity": info.get("debtToEquity"),
        "current_ratio": info.get("currentRatio"),
        "free_cash_flow": info.get("freeCashflow"),
        "earnings_growth": info.get("earningsGrowth"),
        "dividend_yield": info.get("dividendYield"),
    }


def _analyze_technicals(close: pd.Series, volume: pd.Series, price: float) -> dict:
    sma_50 = compute_sma(close, 50)
    sma_200 = compute_sma(close, 200)

    trend = "neutral"
    if sma_50 and sma_200:
        if sma_50 > sma_200 and price > sma_50:
            trend = "strong_bullish"
        elif sma_50 > sma_200:
            trend = "bullish"
        elif sma_50 < sma_200 and price < sma_50:
            trend = "strong_bearish"
        else:
            trend = "bearish"

    return {
        "rsi": compute_rsi(close),
        "sma_50": sma_50,
        "sma_200": sma_200,
        "macd": compute_macd(close),
        "bollinger": compute_bollinger(close),
        "volume_spike": compute_volume_spike(volume),
        "trend": trend,
        "price_vs_sma50": round((price / sma_50 - 1) * 100, 2) if sma_50 else None,
        "price_vs_sma200": round((price / sma_200 - 1) * 100, 2) if sma_200 else None,
    }


def _analyze_valuation(info: dict, price: float) -> dict:
    high_52w = info.get("fiftyTwoWeekHigh")
    low_52w = info.get("fiftyTwoWeekLow")
    target = info.get("targetMeanPrice")

    return {
        "52w_high": high_52w,
        "52w_low": low_52w,
        "off_52w_high": round((high_52w - price) / high_52w * 100, 1) if high_52w else None,
        "above_52w_low": round((price - low_52w) / low_52w * 100, 1) if low_52w else None,
        "analyst_target": target,
        "upside_to_target": round((target - price) / price * 100, 1) if target else None,
        "analyst_recommendation": info.get("recommendationKey"),
        "num_analysts": info.get("numberOfAnalystOpinions"),
        "price_to_book": info.get("priceToBook"),
        "enterprise_to_ebitda": info.get("enterpriseToEbitda"),
    }


def _analyze_performance(hist: pd.DataFrame) -> dict:
    close = hist["Close"]
    price = close.iloc[-1]

    periods = {"1w": 5, "1m": 21, "3m": 63, "6m": 126, "1y": 252}
    perf = {}
    for label, days in periods.items():
        if len(close) > days:
            past_price = close.iloc[-days - 1]
            perf[label] = round((price / past_price - 1) * 100, 2)
    return perf


def _compute_verdict(analysis: dict) -> dict:
    score = 0
    reasons_bull = []
    reasons_bear = []

    fund = analysis["fundamentals"]
    tech = analysis["technicals"]
    val = analysis["valuation"]

    # Fundamentals scoring
    growth = fund.get("revenue_growth")
    if growth is not None:
        if growth > 0.15:
            score += 2
            reasons_bull.append(f"Strong revenue growth ({growth:.0%})")
        elif growth < 0:
            score -= 2
            reasons_bear.append(f"Revenue declining ({growth:.0%})")

    margin = fund.get("profit_margin")
    if margin is not None:
        if margin > 0.20:
            score += 1
            reasons_bull.append(f"High profit margin ({margin:.0%})")
        elif margin < 0:
            score -= 2
            reasons_bear.append("Unprofitable")

    roe = fund.get("roe")
    if roe is not None and roe > 0.20:
        score += 1
        reasons_bull.append(f"Strong ROE ({roe:.0%})")

    dte = fund.get("debt_to_equity")
    if dte is not None and dte > 200:
        score -= 1
        reasons_bear.append(f"High debt (D/E: {dte:.0f})")

    # Technicals scoring
    trend = tech.get("trend", "neutral")
    if "bullish" in trend:
        score += 1
        reasons_bull.append(f"Trend: {trend}")
    elif "bearish" in trend:
        score -= 1
        reasons_bear.append(f"Trend: {trend}")

    rsi = tech.get("rsi")
    if rsi is not None:
        if rsi < 30:
            score += 2
            reasons_bull.append(f"Oversold (RSI {rsi:.0f})")
        elif rsi > 75:
            score -= 1
            reasons_bear.append(f"Overbought (RSI {rsi:.0f})")

    # Valuation scoring
    upside = val.get("upside_to_target")
    if upside is not None:
        if upside > 20:
            score += 2
            reasons_bull.append(f"Analyst upside {upside:.0f}%")
        elif upside < -10:
            score -= 1
            reasons_bear.append(f"Above analyst target by {abs(upside):.0f}%")

    rec = val.get("analyst_recommendation")
    if rec in ("strongBuy", "buy"):
        score += 1
        reasons_bull.append(f"Analyst consensus: {rec}")

    if score >= 4:
        rating = "STRONG BUY"
    elif score >= 2:
        rating = "BUY"
    elif score >= 0:
        rating = "HOLD"
    elif score >= -2:
        rating = "SELL"
    else:
        rating = "STRONG SELL"

    return {
        "rating": rating,
        "score": score,
        "bull_case": reasons_bull,
        "bear_case": reasons_bear,
    }


def display_analysis(analysis: dict):
    if "error" in analysis:
        print(analysis["error"])
        return

    v = analysis["verdict"]
    fund = analysis["fundamentals"]
    tech = analysis["technicals"]
    val = analysis["valuation"]
    perf = analysis["performance"]

    print(f"\n{'='*70}")
    print(f"  {analysis['name']} ({analysis['ticker']})")
    print(f"  {analysis['sector']} — {analysis['industry']}")
    print(f"  Price: ${analysis['price']:.2f}    Market Cap: ${analysis['market_cap']/1e9:.1f}B" if analysis['market_cap'] else f"  Price: ${analysis['price']:.2f}")
    print(f"{'='*70}")

    print(f"\n  VERDICT: {v['rating']} (score: {v['score']:+d})")
    if v["bull_case"]:
        print(f"  Bull case:")
        for r in v["bull_case"]:
            print(f"    + {r}")
    if v["bear_case"]:
        print(f"  Bear case:")
        for r in v["bear_case"]:
            print(f"    - {r}")

    print(f"\n  FUNDAMENTALS")
    _print_kv("P/E (TTM)", fund["pe_ratio"], fmt=".1f")
    _print_kv("Forward P/E", fund["forward_pe"], fmt=".1f")
    _print_kv("Revenue Growth", fund["revenue_growth"], pct=True)
    _print_kv("Profit Margin", fund["profit_margin"], pct=True)
    _print_kv("ROE", fund["roe"], pct=True)
    _print_kv("Debt/Equity", fund["debt_to_equity"], fmt=".0f")
    _print_kv("Free Cash Flow", fund["free_cash_flow"], money=True)

    print(f"\n  TECHNICALS")
    _print_kv("RSI (14)", tech["rsi"], fmt=".1f")
    _print_kv("Trend", tech["trend"])
    _print_kv("SMA 50", tech["sma_50"], fmt=".2f", prefix="$")
    _print_kv("SMA 200", tech["sma_200"], fmt=".2f", prefix="$")
    _print_kv("Price vs SMA50", tech["price_vs_sma50"], fmt=".1f", suffix="%")
    _print_kv("Price vs SMA200", tech["price_vs_sma200"], fmt=".1f", suffix="%")
    if tech["bollinger"]:
        _print_kv("Bollinger Position", tech["bollinger"]["position"], fmt=".2f")

    print(f"\n  VALUATION")
    _print_kv("52W High", val["52w_high"], fmt=".2f", prefix="$")
    _print_kv("52W Low", val["52w_low"], fmt=".2f", prefix="$")
    _print_kv("Off 52W High", val["off_52w_high"], fmt=".1f", suffix="%")
    _print_kv("Analyst Target", val["analyst_target"], fmt=".2f", prefix="$")
    _print_kv("Upside to Target", val["upside_to_target"], fmt=".1f", suffix="%")
    _print_kv("Recommendation", val["analyst_recommendation"])

    print(f"\n  PERFORMANCE")
    for period, ret in perf.items():
        _print_kv(period, ret, fmt="+.2f", suffix="%")
    print()


def _print_kv(key, val, fmt=None, pct=False, money=False, prefix="", suffix=""):
    if val is None:
        print(f"    {key:20s}  N/A")
        return
    if pct:
        print(f"    {key:20s}  {val:.1%}")
    elif money:
        print(f"    {key:20s}  ${val/1e9:.2f}B" if abs(val) > 1e9 else f"    {key:20s}  ${val/1e6:.0f}M")
    elif fmt:
        print(f"    {key:20s}  {prefix}{val:{fmt}}{suffix}")
    else:
        print(f"    {key:20s}  {prefix}{val}{suffix}")


if __name__ == "__main__":
    import sys
    ticker = sys.argv[1] if len(sys.argv) > 1 else "AAPL"
    analysis = analyze_stock(ticker)
    display_analysis(analysis)
