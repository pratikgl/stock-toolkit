import sys
import yfinance as yf
import pandas as pd
from concurrent.futures import ThreadPoolExecutor, as_completed

from config import SCREENER_FILTERS, TOP_N_RESULTS
from sp500 import get_sp500_tickers
from indicators import compute_rsi, compute_sma, compute_macd, compute_volume_spike


def _fetch_stock_data(ticker: str) -> dict | None:
    try:
        stock = yf.Ticker(ticker)
        info = stock.info
        if not info or info.get("quoteType") != "EQUITY":
            return None

        hist = stock.history(period="1y")
        if hist.empty or len(hist) < 50:
            return None

        close = hist["Close"]
        volume = hist["Volume"]

        rsi = compute_rsi(close)
        sma_50 = compute_sma(close, 50)
        sma_200 = compute_sma(close, 200)
        macd = compute_macd(close)
        vol_spike = compute_volume_spike(volume)

        price = close.iloc[-1]

        return {
            "ticker": ticker,
            "name": info.get("shortName", ticker),
            "sector": info.get("sector", "Unknown"),
            "price": round(price, 2),
            "market_cap": info.get("marketCap", 0),
            "pe_ratio": info.get("trailingPE"),
            "forward_pe": info.get("forwardPE"),
            "revenue_growth": info.get("revenueGrowth"),
            "profit_margin": info.get("profitMargins"),
            "debt_to_equity": info.get("debtToEquity"),
            "rsi": rsi,
            "sma_50": sma_50,
            "sma_200": sma_200,
            "macd": macd,
            "volume_spike": vol_spike,
            "52w_high": info.get("fiftyTwoWeekHigh"),
            "52w_low": info.get("fiftyTwoWeekLow"),
            "dividend_yield": info.get("dividendYield"),
        }
    except Exception:
        return None


def _score_stock(data: dict) -> float:
    score = 50.0
    f = SCREENER_FILTERS

    pe = data.get("pe_ratio")
    if pe is not None:
        if pe < 15:
            score += 15
        elif pe < 25:
            score += 8
        elif pe > f["max_pe_ratio"]:
            score -= 10

    growth = data.get("revenue_growth")
    if growth is not None:
        if growth > 0.20:
            score += 20
        elif growth > 0.10:
            score += 12
        elif growth > f["min_revenue_growth"]:
            score += 5
        else:
            score -= 10

    margin = data.get("profit_margin")
    if margin is not None:
        if margin > 0.25:
            score += 12
        elif margin > f["min_profit_margin"]:
            score += 5
        else:
            score -= 8

    dte = data.get("debt_to_equity")
    if dte is not None:
        if dte < 50:
            score += 8
        elif dte > f["max_debt_to_equity"] * 100:
            score -= 10

    rsi = data.get("rsi")
    if rsi is not None:
        if rsi < f["rsi_oversold"]:
            score += 15  # oversold = potential buy
        elif rsi < 45:
            score += 5
        elif rsi > f["rsi_overbought"]:
            score -= 8  # overbought = caution

    sma_50 = data.get("sma_50")
    sma_200 = data.get("sma_200")
    price = data.get("price")
    if sma_50 and sma_200 and price:
        if sma_50 > sma_200:
            score += 10  # golden cross
        else:
            score -= 5   # death cross
        if price > sma_50:
            score += 5   # above short-term trend

    macd = data.get("macd")
    if macd:
        if macd["histogram"] > 0:
            score += 5
        else:
            score -= 3

    vol_spike = data.get("volume_spike")
    if vol_spike and vol_spike > 2.0 and rsi and rsi < 40:
        score += 8  # high volume + oversold = potential reversal

    high_52w = data.get("52w_high")
    if high_52w and price:
        discount = (high_52w - price) / high_52w
        if 0.15 < discount < 0.35:
            score += 8  # 15-35% off highs can be opportunity

    return round(score, 1)


def _passes_basic_filters(data: dict) -> bool:
    f = SCREENER_FILTERS
    cap = data.get("market_cap", 0)
    if cap and cap < f["min_market_cap"]:
        return False
    return True


def run_screener(tickers: list[str] | None = None, max_workers: int = 10) -> pd.DataFrame:
    if tickers is None:
        print("Fetching S&P 500 ticker list...")
        tickers = get_sp500_tickers()

    print(f"Screening {len(tickers)} stocks...")
    results = []
    done = 0

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(_fetch_stock_data, t): t for t in tickers}
        for future in as_completed(futures):
            done += 1
            if done % 50 == 0:
                print(f"  Progress: {done}/{len(tickers)}")
            data = future.result()
            if data and _passes_basic_filters(data):
                data["score"] = _score_stock(data)
                results.append(data)

    df = pd.DataFrame(results)
    if df.empty:
        return df
    df = df.sort_values("score", ascending=False).reset_index(drop=True)
    return df


def display_results(df: pd.DataFrame, top_n: int = TOP_N_RESULTS):
    if df.empty:
        print("No stocks matched the criteria.")
        return

    from tabulate import tabulate

    top = df.head(top_n)
    display_cols = [
        "ticker", "name", "sector", "price", "pe_ratio",
        "revenue_growth", "profit_margin", "rsi", "score",
    ]
    display = top[display_cols].copy()
    display["revenue_growth"] = display["revenue_growth"].apply(
        lambda x: f"{x:.1%}" if pd.notna(x) else "N/A"
    )
    display["profit_margin"] = display["profit_margin"].apply(
        lambda x: f"{x:.1%}" if pd.notna(x) else "N/A"
    )
    display["pe_ratio"] = display["pe_ratio"].apply(
        lambda x: f"{x:.1f}" if pd.notna(x) else "N/A"
    )
    display["price"] = display["price"].apply(lambda x: f"${x:.2f}")

    print(f"\n{'='*90}")
    print(f"  TOP {top_n} STOCK PICKS")
    print(f"{'='*90}")
    print(tabulate(display, headers="keys", tablefmt="simple", showindex=False))
    print()

    signals = top[top["rsi"].notna() & (top["rsi"] < SCREENER_FILTERS["rsi_oversold"])]
    if not signals.empty:
        print("OVERSOLD SIGNALS (RSI < 35):")
        for _, row in signals.iterrows():
            print(f"  {row['ticker']:6s} — RSI {row['rsi']:.1f}, Price ${row['price']:.2f}")
        print()


if __name__ == "__main__":
    df = run_screener()
    display_results(df)
    df.to_csv("screener_output.csv", index=False)
    print("Full results saved to screener_output.csv")
