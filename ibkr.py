"""Interactive Brokers Client Portal API integration.

IBKR provides a REST API via their Client Portal Gateway. To use this:
1. Download the Client Portal Gateway from IBKR
2. Run it: bin/run.sh root/conf.yaml
3. Authenticate at https://localhost:5000
4. This module talks to that local gateway

Docs: https://www.interactivebrokers.com/campus/ibkr-api-page/cpapi-v1/
"""

import json
import urllib.request
import urllib.error
import ssl
from pathlib import Path

IBKR_CONFIG_PATH = Path(__file__).parent / "ibkr_config.json"

# IBKR Client Portal Gateway runs locally with self-signed cert
_SSL_CTX = ssl.create_default_context()
_SSL_CTX.check_hostname = False
_SSL_CTX.verify_mode = ssl.CERT_NONE


def _load_config() -> dict:
    if not IBKR_CONFIG_PATH.exists():
        return {"gateway_url": "https://localhost:5000", "account_id": ""}
    with open(IBKR_CONFIG_PATH) as f:
        return json.load(f)


def _save_config(config: dict):
    with open(IBKR_CONFIG_PATH, "w") as f:
        json.dump(config, f, indent=2)


def configure(gateway_url: str = "https://localhost:5000", account_id: str = ""):
    config = _load_config()
    config["gateway_url"] = gateway_url.rstrip("/")
    if account_id:
        config["account_id"] = account_id
    _save_config(config)
    print(f"IBKR configured: {gateway_url}")
    if account_id:
        print(f"Account ID: {account_id}")


def _api_request(method: str, endpoint: str, data: dict | None = None) -> dict | list | None:
    config = _load_config()
    url = f"{config['gateway_url']}/v1/api{endpoint}"

    body = json.dumps(data).encode() if data else None
    req = urllib.request.Request(
        url,
        data=body,
        method=method,
        headers={"Content-Type": "application/json"} if body else {},
    )

    try:
        with urllib.request.urlopen(req, context=_SSL_CTX, timeout=10) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        error_body = e.read().decode() if e.fp else ""
        print(f"IBKR API error {e.code}: {error_body}")
        return None
    except urllib.error.URLError as e:
        print(f"IBKR Gateway not reachable: {e.reason}")
        print("Make sure the Client Portal Gateway is running.")
        print("Download: https://www.interactivebrokers.com/en/trading/ib-api.php")
        return None


def check_auth() -> bool:
    result = _api_request("GET", "/iserver/auth/status")
    if result and result.get("authenticated"):
        print("Authenticated with IBKR.")
        return True
    print("Not authenticated. Open https://localhost:5000 in your browser to log in.")
    return False


def reauthenticate() -> bool:
    result = _api_request("POST", "/iserver/reauthenticate")
    if result:
        print("Re-authentication requested. Check the gateway.")
        return True
    return False


def get_accounts() -> list[dict] | None:
    result = _api_request("GET", "/portfolio/accounts")
    if result:
        for acc in result:
            print(f"  Account: {acc.get('id')}  Type: {acc.get('type')}  "
                  f"Currency: {acc.get('currency')}")
    return result


def get_positions() -> list[dict] | None:
    config = _load_config()
    acc_id = config.get("account_id")
    if not acc_id:
        print("Account ID not configured. Run: main.py ibkr setup --account YOUR_ACCOUNT_ID")
        return None

    result = _api_request("GET", f"/portfolio/{acc_id}/positions/0")
    if result:
        from tabulate import tabulate
        rows = []
        for pos in result:
            rows.append([
                pos.get("ticker", pos.get("contractDesc", "?")),
                pos.get("position", 0),
                f"${pos.get('avgCost', 0):.2f}",
                f"${pos.get('mktPrice', 0):.2f}",
                f"${pos.get('mktValue', 0):.2f}",
                f"${pos.get('unrealizedPnl', 0):+.2f}",
            ])
        if rows:
            print("\nIBKR Positions:\n")
            print(tabulate(rows, headers=["Ticker", "Qty", "Avg Cost", "Price", "Value", "P&L"],
                          tablefmt="simple"))
            print()
    return result


def search_contract(symbol: str) -> dict | None:
    result = _api_request("GET", f"/iserver/secdef/search?symbol={symbol}&secType=STK")
    if result and isinstance(result, list) and len(result) > 0:
        contract = result[0]
        conid = contract.get("conid")
        print(f"  Found: {contract.get('companyName')} (conid: {conid})")
        return contract
    print(f"  No contract found for {symbol}")
    return None


def get_quote(conid: int) -> dict | None:
    result = _api_request("GET", f"/iserver/marketdata/snapshot?conids={conid}&fields=31,84,86")
    if result and isinstance(result, list) and len(result) > 0:
        return result[0]
    return None


def place_order(
    symbol: str,
    quantity: float,
    side: str,  # "BUY" or "SELL"
    order_type: str = "MKT",
    limit_price: float | None = None,
    dry_run: bool = True,
) -> dict | None:
    config = _load_config()
    acc_id = config.get("account_id")
    if not acc_id:
        print("Account ID not configured.")
        return None

    contract = search_contract(symbol)
    if not contract:
        return None

    conid = contract.get("conid")
    if not conid:
        # conid might be nested in sections
        sections = contract.get("sections", [])
        for sec in sections:
            if sec.get("secType") == "STK":
                conid = sec.get("conid")
                break

    if not conid:
        print(f"Could not find conid for {symbol}")
        return None

    order = {
        "conid": conid,
        "orderType": order_type,
        "side": side.upper(),
        "quantity": quantity,
        "tif": "DAY",
    }

    if order_type == "LMT" and limit_price is not None:
        order["price"] = limit_price

    if dry_run:
        print(f"\n  DRY RUN — Order preview:")
        print(f"    {side.upper()} {quantity} x {symbol}")
        print(f"    Type: {order_type}")
        if limit_price:
            print(f"    Limit: ${limit_price:.2f}")
        print(f"    Account: {acc_id}")
        print(f"\n  To execute for real, add --execute flag")
        return {"dry_run": True, "order": order}

    result = _api_request("POST", f"/iserver/account/{acc_id}/orders", {"orders": [order]})
    if result:
        # IBKR may return order confirmation questions
        if isinstance(result, list) and result and "id" in result[0]:
            confirm_id = result[0]["id"]
            print(f"  Order requires confirmation (id: {confirm_id})")
            confirm = _api_request("POST", f"/iserver/reply/{confirm_id}", {"confirmed": True})
            if confirm:
                print(f"  Order confirmed and submitted!")
                return confirm
        else:
            print(f"  Order submitted: {result}")
    return result


def execute_signals(signals: list[dict], capital_per_trade: float = 500, dry_run: bool = True):
    """Take scanner signals and convert them to orders."""
    if not signals:
        print("No signals to execute.")
        return

    buy_signals = [s for s in signals if s["signal"] == "buy"]
    if not buy_signals:
        print("No buy signals to execute.")
        return

    print(f"\n{'='*60}")
    print(f"  SIGNAL-TO-ORDER PIPELINE")
    print(f"  Capital per trade: ${capital_per_trade:.2f}")
    print(f"  Mode: {'DRY RUN' if dry_run else 'LIVE'}")
    print(f"{'='*60}\n")

    for sig in buy_signals:
        ticker = sig["ticker"]
        price = sig["price"]
        shares = round(capital_per_trade / price, 4)

        print(f"  Signal: BUY {ticker} @ ${price:.2f} [{sig.get('strategy', '?')}]")
        if sig.get("reasons"):
            for r in sig["reasons"]:
                print(f"    Reason: {r}")

        place_order(ticker, shares, "BUY", dry_run=dry_run)
        print()


def display_setup_guide():
    print(f"""
{'='*60}
  IBKR SETUP GUIDE
{'='*60}

  1. OPEN AN IBKR ACCOUNT
     https://www.interactivebrokers.co.in
     - Need PAN, Aadhaar, bank details
     - Takes ~1 week for approval
     - Fund via LRS (Liberalised Remittance Scheme)

  2. DOWNLOAD CLIENT PORTAL GATEWAY
     https://www.interactivebrokers.com/en/trading/ib-api.php
     - Download "Client Portal Gateway"
     - Unzip, run: bin/run.sh root/conf.yaml
     - Opens at https://localhost:5000

  3. AUTHENTICATE
     - Open https://localhost:5000 in browser
     - Log in with your IBKR credentials
     - Gateway session lasts ~24 hours

  4. CONFIGURE THIS TOOLKIT
     main.py ibkr setup --account YOUR_ACCOUNT_ID
     main.py ibkr status    (verify connection)
     main.py ibkr positions (view holdings)

  5. AUTOMATED TRADING
     main.py ibkr auto-trade           (dry run from latest scan)
     main.py ibkr auto-trade --execute  (place real orders)

  NOTES
    - $0 commission on US stocks via IBKR Lite
    - Fractional shares supported
    - API rate limit: ~10 requests/second
    - Gateway must be running for API access
    - Re-auth needed every ~24 hours
""")
