"""India tax calculator for US stock investments.

Tax rules for Indian residents investing in US stocks (as of FY 2025-26):
- US stocks are treated as "foreign assets" — must be declared in ITR Schedule FA
- Capital gains taxed in India (with DTAA credit for US withholding)
- Dividends: 25% withheld by US (DTAA rate), taxable in India at slab rate (credit for US tax)
- LTCG (held > 24 months): 12.5% without indexation
- STCG (held <= 24 months): taxed at income slab rate
- TCS: 20% on remittance above Rs.7 lakh/FY under LRS (adjustable against tax liability)
"""

import json
from datetime import datetime, date
from pathlib import Path
from tabulate import tabulate

PORTFOLIO_PATH = Path(__file__).parent / "portfolio.json"

LTCG_RATE = 0.125          # 12.5% LTCG on foreign stocks (> 24 months)
LTCG_HOLDING_MONTHS = 24   # 24 months for foreign assets
STCG_SLAB_RATES = {        # FY 2025-26 new regime
    "0-400000": 0.0,
    "400001-800000": 0.05,
    "800001-1200000": 0.10,
    "1200001-1600000": 0.15,
    "1600001-2000000": 0.20,
    "2000001-2400000": 0.25,
    "2400001+": 0.30,
}
TCS_THRESHOLD = 700000     # Rs.7 lakh per FY
TCS_RATE = 0.20            # 20% TCS above threshold
US_DIVIDEND_WITHHOLDING = 0.25  # 25% under DTAA
CESS_RATE = 0.04           # 4% health & education cess


def _months_held(buy_date: str, sell_date: str = None) -> int:
    buy = datetime.strptime(buy_date, "%Y-%m-%d")
    sell = datetime.strptime(sell_date, "%Y-%m-%d") if sell_date else datetime.now()
    return (sell.year - buy.year) * 12 + (sell.month - buy.month)


def calculate_capital_gains_tax(
    buy_price_usd: float,
    sell_price_usd: float,
    shares: float,
    buy_date: str,
    sell_date: str = None,
    buy_usd_inr: float = 83.0,
    sell_usd_inr: float = 85.0,
) -> dict:
    months = _months_held(buy_date, sell_date)
    is_ltcg = months > LTCG_HOLDING_MONTHS

    cost_inr = buy_price_usd * shares * buy_usd_inr
    proceeds_inr = sell_price_usd * shares * sell_usd_inr
    gain_inr = proceeds_inr - cost_inr

    if is_ltcg:
        tax_rate = LTCG_RATE
        tax_type = "LTCG (>24 months)"
    else:
        tax_rate = 0.20  # approximate — depends on total income slab
        tax_type = "STCG (slab rate, est. 20%)"

    base_tax = max(0, gain_inr * tax_rate)
    cess = base_tax * CESS_RATE
    total_tax = base_tax + cess

    return {
        "type": tax_type,
        "holding_months": months,
        "cost_inr": cost_inr,
        "proceeds_inr": proceeds_inr,
        "gain_inr": gain_inr,
        "tax_rate": tax_rate,
        "base_tax": base_tax,
        "cess": cess,
        "total_tax": total_tax,
        "net_gain_inr": gain_inr - total_tax,
        "effective_rate": total_tax / gain_inr * 100 if gain_inr > 0 else 0,
    }


def calculate_tcs(remittance_inr: float, already_remitted_fy: float = 0) -> dict:
    total = already_remitted_fy + remittance_inr
    if total <= TCS_THRESHOLD:
        return {
            "remittance": remittance_inr,
            "tcs_amount": 0,
            "total_outflow": remittance_inr,
            "note": f"Within Rs.{TCS_THRESHOLD/100000:.0f}L FY limit — no TCS",
        }

    taxable = max(0, total - TCS_THRESHOLD) - max(0, already_remitted_fy - TCS_THRESHOLD)
    tcs = taxable * TCS_RATE

    return {
        "remittance": remittance_inr,
        "tcs_amount": tcs,
        "total_outflow": remittance_inr + tcs,
        "note": f"TCS of {TCS_RATE*100:.0f}% on Rs.{taxable:,.0f} above Rs.{TCS_THRESHOLD/100000:.0f}L threshold. "
                f"This is adjustable against your income tax liability.",
    }


def calculate_dividend_tax(
    dividend_usd: float,
    usd_inr: float = 85.0,
    income_slab_rate: float = 0.20,
) -> dict:
    gross_inr = dividend_usd * usd_inr
    us_withholding = dividend_usd * US_DIVIDEND_WITHHOLDING * usd_inr
    india_tax = gross_inr * income_slab_rate
    dtaa_credit = min(us_withholding, india_tax)
    net_india_tax = max(0, india_tax - dtaa_credit)
    cess = net_india_tax * CESS_RATE
    total_tax = us_withholding + net_india_tax + cess

    return {
        "gross_dividend_inr": gross_inr,
        "us_withholding": us_withholding,
        "india_tax_before_credit": india_tax,
        "dtaa_credit": dtaa_credit,
        "net_india_tax": net_india_tax,
        "cess": cess,
        "total_tax": total_tax,
        "net_received_inr": gross_inr - total_tax,
        "effective_rate": total_tax / gross_inr * 100 if gross_inr > 0 else 0,
    }


def display_tax_summary(
    buy_price: float, sell_price: float, shares: float,
    buy_date: str, sell_date: str = None,
    buy_rate: float = 83.0, sell_rate: float = 85.0,
):
    result = calculate_capital_gains_tax(
        buy_price, sell_price, shares, buy_date, sell_date, buy_rate, sell_rate
    )

    print(f"\n{'='*60}")
    print(f"  TAX ESTIMATE — Capital Gains")
    print(f"{'='*60}")
    print(f"    Type:              {result['type']}")
    print(f"    Holding Period:    {result['holding_months']} months")
    print(f"    Cost (INR):        Rs.{result['cost_inr']:>12,.0f}")
    print(f"    Proceeds (INR):    Rs.{result['proceeds_inr']:>12,.0f}")
    print(f"    Gain (INR):        Rs.{result['gain_inr']:>+12,.0f}")
    print(f"    Tax Rate:          {result['tax_rate']*100:.1f}%")
    print(f"    Base Tax:          Rs.{result['base_tax']:>12,.0f}")
    print(f"    Cess (4%):         Rs.{result['cess']:>12,.0f}")
    print(f"    Total Tax:         Rs.{result['total_tax']:>12,.0f}")
    print(f"    Net Gain:          Rs.{result['net_gain_inr']:>+12,.0f}")
    print(f"    Effective Rate:    {result['effective_rate']:.1f}%")
    print()


def display_tcs_estimate(remittance_inr: float, already_remitted: float = 0):
    result = calculate_tcs(remittance_inr, already_remitted)

    print(f"\n{'='*60}")
    print(f"  TCS ESTIMATE — LRS Remittance")
    print(f"{'='*60}")
    print(f"    Remittance:        Rs.{result['remittance']:>12,.0f}")
    print(f"    TCS:               Rs.{result['tcs_amount']:>12,.0f}")
    print(f"    Total Outflow:     Rs.{result['total_outflow']:>12,.0f}")
    print(f"    Note: {result['note']}")
    print()


def display_full_tax_guide():
    print(f"""
{'='*60}
  INDIA TAX GUIDE — US Stock Investments
{'='*60}

  CAPITAL GAINS
    LTCG (held > 24 months):   12.5% flat (no indexation)
    STCG (held <= 24 months):  At your income slab rate
    + 4% Health & Education Cess on tax

  DIVIDENDS
    US withholds 25% (DTAA rate)
    Taxable in India at slab rate
    DTAA credit available (no double taxation)

  TCS ON REMITTANCE (LRS)
    First Rs.7 lakh/FY:  No TCS
    Above Rs.7 lakh:     20% TCS (adjustable against tax)

  REPORTING
    Schedule FA (Foreign Assets) in ITR — mandatory
    Schedule FSI (Foreign Source Income)
    Schedule TR (Tax Relief under DTAA)

  KEY DATES
    US tax year: Jan-Dec
    India tax year: Apr-Mar
    Form 67 must be filed before ITR for DTAA credit

  TIPS
    - Hold > 24 months for LTCG (12.5% vs slab rate)
    - TCS is NOT extra tax, it's advance tax (claim refund)
    - Keep records of USD/INR rate on buy & sell dates
    - Currency gains are part of capital gains
""")
