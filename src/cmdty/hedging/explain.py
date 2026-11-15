"""P&L explain: split the daily option P&L with a Taylor expansion on yesterday's greeks.

    dV ~ delta dF + 1/2 gamma dF^2 + theta dt + vega dvol (+ cash paid)

What the expansion misses is `unexplained`. On a well hedged book the delta line and the
hedge P&L cancel, and what is left is gamma against theta: the volatility bet.
"""

from .book import BookGreeks

EXPLAIN_LINES = ("delta", "gamma", "theta", "vega", "cash", "unexplained")


def explain_day(
    option_pnl: float,
    deltas: dict[str, float],
    greeks: BookGreeks,
    theta: float,
    moves: dict[str, float],
    vol_moves: dict[str, float],
    cash: float,
) -> dict[str, float]:
    """One day of option P&L, line by line. Greeks are yesterday's, moves are since yesterday."""
    lines = {
        "delta": sum(d * moves.get(u, 0.0) for u, d in deltas.items()),
        "gamma": greeks.gamma_pnl(moves),
        "theta": theta,
        "vega": sum(v * vol_moves.get(u, 0.0) * 100 for u, v in greeks.vega.items()),
        "cash": cash,
    }
    lines["unexplained"] = option_pnl - sum(lines.values())
    return lines
