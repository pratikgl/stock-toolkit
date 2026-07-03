"""Claude API integration for natural-language stock analysis."""

import os
import json

_CLIENT = None


def _get_client():
    global _CLIENT
    if _CLIENT is not None:
        return _CLIENT

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return None

    try:
        import anthropic
        _CLIENT = anthropic.Anthropic(api_key=api_key)
        return _CLIENT
    except Exception:
        return None


def analyze_signal(alert: dict, backtest: dict | None = None) -> str | None:
    """Ask Claude to analyze a stock signal and give a plain-English recommendation."""
    client = _get_client()
    if not client:
        return None

    bt_context = ""
    if backtest:
        bt_context = (
            f"\nBacktest (3 years): {backtest['return_pct']:+.1f}% total return, "
            f"{backtest['win_rate']:.0f}% win rate, {backtest['num_trades']} trades, "
            f"max drawdown {backtest['max_drawdown']:.1f}%"
        )

    prompt = f"""You are a stock trading advisor. Analyze this buy signal and give a SHORT recommendation (2-3 sentences max).

Stock: {alert.get('name', alert['ticker'])} ({alert['ticker']})
Sector: {alert.get('sector', 'Unknown')}
Price: ${alert['price']:.2f}
RSI: {alert.get('rsi', 'N/A')}
1-Day Change: {alert.get('change_1d', 0):+.2f}%
Off 52-Week High: {alert.get('off_high', 0):.1f}%
Volume vs Average: {alert.get('vol_ratio', 1.0):.1f}x
Strategies Triggered: {alert.get('strategy', 'unknown')}
Reasons: {', '.join(alert.get('reasons', []))}
Quality Score: {alert.get('quality_score', 0)}/40{bt_context}

Answer in this exact format:
VERDICT: [BUY NOW / WAIT / SKIP]
[2-3 sentence explanation of why, referencing the specific data above. Include timing advice — should they buy today or wait for a better entry?]"""

    try:
        response = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=150,
            messages=[{"role": "user", "content": prompt}],
        )
        return response.content[0].text.strip()
    except Exception as e:
        print(f"  AI analysis failed for {alert['ticker']}: {e}")
        return None


def batch_analyze(alerts: list[dict], backtests: dict | None = None) -> dict:
    """Analyze multiple signals, return ticker -> analysis mapping."""
    results = {}
    for alert in alerts:
        ticker = alert["ticker"]
        bt = backtests.get(ticker) if backtests else None
        analysis = analyze_signal(alert, bt)
        if analysis:
            results[ticker] = analysis
    return results
