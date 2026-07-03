import requests
import pandas as pd
from io import StringIO

_CACHE = None

def get_sp500_tickers() -> list[str]:
    global _CACHE
    if _CACHE is not None:
        return _CACHE

    url = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
    resp = requests.get(url, timeout=15)
    tables = pd.read_html(StringIO(resp.text))
    df = tables[0]
    tickers = df["Symbol"].str.replace(".", "-", regex=False).tolist()
    _CACHE = tickers
    return tickers
