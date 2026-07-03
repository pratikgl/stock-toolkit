"""Advanced signal sources — news sentiment, insider trading, earnings momentum.

These supplement the technical strategies with fundamental/alternative data.
"""

import json
import urllib.request
import urllib.error
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed

import yfinance as yf


# ─── News Sentiment ─────────────────────────────────────────────────────────

def get_news_sentiment(ticker: str) -> dict | None:
    """Get news sentiment using yfinance news feed + keyword scoring.
    No API key needed — uses Yahoo Finance news headlines."""
    try:
        stock = yf.Ticker(ticker)
        news = stock.news
        if not news:
            return None

        positive_words = {
            "beat", "beats", "surpass", "exceed", "record", "high", "growth",
            "upgrade", "buy", "bullish", "strong", "surge", "soar", "rally",
            "profit", "gain", "positive", "outperform", "raises", "boost",
            "innovation", "breakthrough", "partnership", "launch", "expansion",
            "dividend", "buyback", "repurchase", "revenue",
        }
        negative_words = {
            "miss", "decline", "fall", "drop", "cut", "downgrade", "sell",
            "bearish", "weak", "crash", "plunge", "loss", "negative",
            "underperform", "lowers", "warns", "risk", "layoff", "lawsuit",
            "investigation", "recall", "debt", "default", "bankruptcy",
            "overvalued", "bubble", "fraud", "scandal",
        }

        scores = []
        recent_headlines = []
        for item in news[:10]:
            title = item.get("title", "").lower()
            words = set(title.split())
            pos = len(words & positive_words)
            neg = len(words & negative_words)
            score = pos - neg
            scores.append(score)
            if pos > 0 or neg > 0:
                recent_headlines.append({
                    "title": item.get("title", ""),
                    "score": score,
                    "publisher": item.get("publisher", ""),
                })

        if not scores:
            return None

        avg_score = sum(scores) / len(scores)
        sentiment = "positive" if avg_score > 0.3 else "negative" if avg_score < -0.3 else "neutral"

        return {
            "ticker": ticker,
            "sentiment": sentiment,
            "score": round(avg_score, 2),
            "articles_analyzed": len(scores),
            "top_headlines": recent_headlines[:3],
        }
    except Exception:
        return None


# ─── Insider Trading ────────────────────────────────────────────────────────

def get_insider_activity(ticker: str) -> dict | None:
    """Get recent insider trading activity via yfinance.
    Insider buys are one of the strongest bullish signals —
    executives buying their own stock with their own money."""
    try:
        stock = yf.Ticker(ticker)
        insider = stock.insider_transactions
        if insider is None or insider.empty:
            return None

        recent = insider.head(20)

        buys = 0
        sells = 0
        buy_value = 0
        sell_value = 0

        for _, row in recent.iterrows():
            text = str(row.get("Text", "")).lower()
            shares = abs(row.get("Shares", 0) or 0)
            value = abs(row.get("Value", 0) or 0)

            if "purchase" in text or "buy" in text or "acquisition" in text:
                buys += 1
                buy_value += value
            elif "sale" in text or "sell" in text or "disposition" in text:
                sells += 1
                sell_value += value

        if buys + sells == 0:
            return None

        buy_ratio = buys / (buys + sells)
        signal = "strong_buy" if buy_ratio > 0.6 and buys >= 3 else \
                 "buy" if buy_ratio > 0.4 else \
                 "sell" if buy_ratio < 0.2 and sells >= 3 else \
                 "neutral"

        return {
            "ticker": ticker,
            "signal": signal,
            "buys": buys,
            "sells": sells,
            "buy_ratio": round(buy_ratio, 2),
            "buy_value": buy_value,
            "sell_value": sell_value,
            "net_value": buy_value - sell_value,
        }
    except Exception:
        return None


# ─── Earnings Momentum ──────────────────────────────────────────────────────

def get_earnings_momentum(ticker: str) -> dict | None:
    """Check earnings surprise history. Stocks that consistently beat
    estimates tend to continue outperforming (PEAD — Post-Earnings
    Announcement Drift)."""
    try:
        stock = yf.Ticker(ticker)
        earnings = stock.earnings_history
        if earnings is None or earnings.empty:
            return None

        recent = earnings.tail(4)  # last 4 quarters

        surprises = []
        for _, row in recent.iterrows():
            estimate = row.get("epsEstimate")
            actual = row.get("epsActual")
            if estimate and actual and estimate != 0:
                surprise_pct = (actual - estimate) / abs(estimate) * 100
                surprises.append(surprise_pct)

        if not surprises:
            return None

        beats = sum(1 for s in surprises if s > 0)
        avg_surprise = sum(surprises) / len(surprises)

        signal = "strong_buy" if beats == len(surprises) and avg_surprise > 5 else \
                 "buy" if beats >= len(surprises) * 0.75 and avg_surprise > 0 else \
                 "sell" if beats <= 1 and avg_surprise < -5 else \
                 "neutral"

        return {
            "ticker": ticker,
            "signal": signal,
            "beats": beats,
            "total_quarters": len(surprises),
            "avg_surprise_pct": round(float(avg_surprise), 2),
            "consecutive_beats": beats == len(surprises),
            "surprises": [round(float(s), 2) for s in surprises],
        }
    except Exception:
        return None


# ─── Combined Signal Score ──────────────────────────────────────────────────

def get_enhanced_signals(ticker: str) -> dict:
    """Get all advanced signals for a ticker."""
    news = get_news_sentiment(ticker)
    insider = get_insider_activity(ticker)
    earnings = get_earnings_momentum(ticker)

    bonus_score = 0
    reasons = []

    if news:
        if news["sentiment"] == "positive":
            bonus_score += 10
            reasons.append(f"Positive news sentiment ({news['score']:+.1f})")
        elif news["sentiment"] == "negative":
            bonus_score -= 10
            reasons.append(f"Negative news sentiment ({news['score']:+.1f})")

    if insider:
        if insider["signal"] in ("strong_buy", "buy"):
            bonus_score += 15
            reasons.append(f"Insider buying ({insider['buys']} buys vs {insider['sells']} sells)")
        elif insider["signal"] == "sell":
            bonus_score -= 10
            reasons.append(f"Insider selling ({insider['sells']} sells vs {insider['buys']} buys)")

    if earnings:
        if earnings["signal"] in ("strong_buy", "buy"):
            bonus_score += 12
            reasons.append(f"Beat earnings {earnings['beats']}/{earnings['total_quarters']} quarters "
                          f"(avg surprise: {earnings['avg_surprise_pct']:+.1f}%)")
        elif earnings["signal"] == "sell":
            bonus_score -= 10
            reasons.append(f"Missed earnings (avg surprise: {earnings['avg_surprise_pct']:+.1f}%)")

    return {
        "ticker": ticker,
        "bonus_score": bonus_score,
        "reasons": reasons,
        "news": news,
        "insider": insider,
        "earnings": earnings,
    }


def display_enhanced_signals(ticker: str):
    """Display all advanced signals for a ticker."""
    print(f"\nFetching advanced signals for {ticker}...")
    result = get_enhanced_signals(ticker)

    print(f"\n{'='*60}")
    print(f"  ADVANCED SIGNALS — {ticker}")
    print(f"  Bonus Score: {result['bonus_score']:+d}")
    print(f"{'='*60}")

    news = result["news"]
    if news:
        print(f"\n  NEWS SENTIMENT: {news['sentiment'].upper()} ({news['score']:+.2f})")
        print(f"    Articles analyzed: {news['articles_analyzed']}")
        for h in news.get("top_headlines", []):
            marker = "+" if h["score"] > 0 else "-" if h["score"] < 0 else " "
            print(f"    [{marker}] {h['title'][:70]}")
    else:
        print(f"\n  NEWS SENTIMENT: No data")

    insider = result["insider"]
    if insider:
        print(f"\n  INSIDER ACTIVITY: {insider['signal'].upper()}")
        print(f"    Buys: {insider['buys']}  Sells: {insider['sells']}  "
              f"Buy ratio: {insider['buy_ratio']:.0%}")
        if insider["buy_value"]:
            print(f"    Buy value: ${insider['buy_value']:,.0f}  "
                  f"Sell value: ${insider['sell_value']:,.0f}")
    else:
        print(f"\n  INSIDER ACTIVITY: No data")

    earnings = result["earnings"]
    if earnings:
        print(f"\n  EARNINGS MOMENTUM: {earnings['signal'].upper()}")
        print(f"    Beat {earnings['beats']}/{earnings['total_quarters']} quarters")
        print(f"    Avg surprise: {earnings['avg_surprise_pct']:+.1f}%")
        print(f"    History: {earnings['surprises']}")
    else:
        print(f"\n  EARNINGS MOMENTUM: No data")

    if result["reasons"]:
        print(f"\n  SUMMARY:")
        for r in result["reasons"]:
            print(f"    {'+'  if result['bonus_score'] > 0 else '-'} {r}")
    print()
