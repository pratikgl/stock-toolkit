SCREENER_FILTERS = {
    "min_market_cap": 10_000_000_000,   # $10B+ (large cap)
    "max_pe_ratio": 35,
    "min_revenue_growth": 0.05,         # 5%+ YoY
    "min_profit_margin": 0.10,          # 10%+
    "max_debt_to_equity": 2.0,
    "rsi_oversold": 35,                 # RSI below this = buy signal
    "rsi_overbought": 70,               # RSI above this = caution
    "ma_short": 50,                     # 50-day moving average
    "ma_long": 200,                     # 200-day moving average
}

TOP_N_RESULTS = 15

USD_INR_TICKER = "USDINR=X"

SECTORS = [
    "Technology", "Healthcare", "Financial Services",
    "Consumer Cyclical", "Communication Services",
    "Industrials", "Consumer Defensive", "Energy",
    "Utilities", "Real Estate", "Basic Materials",
]
