"""Risk of the whole portfolio, netted by underlying: what the bot has to hedge."""

from dataclasses import dataclass
from itertools import combinations_with_replacement

import QuantLib as ql

from ..portfolio import Portfolio, Trade
from ..pricer import Pricer

# =============================================================================
# 1. One trade
# =============================================================================


def _is_alive(trade: Trade, pricer: Pricer) -> bool:
    """Still has a value: the payoff has not been paid yet."""
    return pricer.market.today <= trade.instrument.schedule.pay_date


def trade_pv(trade: Trade, pricer: Pricer) -> float:
    """PV of the position in $: quantity (signed) x PV per bbl."""
    if not _is_alive(trade, pricer):
        return 0.0
    return trade.instrument.quantity * pricer.pv(trade.instrument)


def trade_deltas(trade: Trade, pricer: Pricer) -> dict[str, float]:
    """$ change per +1 $/bbl on each underlying, i.e. an exposure in bbl."""
    if not _is_alive(trade, pricer):
        return {}
    apo = trade.instrument
    return {u: apo.quantity * d for u, d in pricer.deltas(apo).items()}


def paid_cash(trade: Trade, before: Pricer, after: Pricer) -> float:
    """Cash received if the trade pays between the two dates, 0 otherwise."""
    if _is_alive(trade, before) and not _is_alive(trade, after):
        return trade.instrument.quantity * after.expected_payoff(trade.instrument)
    return 0.0


# =============================================================================
# 2. The book
# =============================================================================


@dataclass(frozen=True)
class BookRisk:
    """PV and deltas of all trades on one date."""

    pv: float  # $, sum over trades
    deltas: dict[str, float]  # bbl per underlying, netted across trades
    pv_by_trade: dict[str, float]


def book_risk(portfolio: Portfolio, pricer: Pricer) -> BookRisk:
    """Price every trade and add up the deltas per underlying (netting)."""
    deltas: dict[str, float] = {}
    pvs = {}
    for trade in portfolio:
        pvs[trade.id] = trade_pv(trade, pricer)
        for u, d in trade_deltas(trade, pricer).items():
            deltas[u] = deltas.get(u, 0.0) + d
    return BookRisk(pv=sum(pvs.values()), deltas=deltas, pv_by_trade=pvs)


# =============================================================================
# 3. Second-order greeks, for the P&L explain
# =============================================================================


@dataclass(frozen=True)
class BookGreeks:
    """Book gammas (including cross terms) and vegas on one date."""

    gamma: dict[tuple[str, str], float]  # d2PV / dFa dFb, $ per $^2, a <= b
    vega: dict[str, float]  # $ per vol point

    def gamma_pnl(self, moves: dict[str, float]) -> float:
        """1/2 sum over a, b of gamma_ab dFa dFb."""
        total = 0.0
        for (a, b), g in self.gamma.items():
            weight = 0.5 if a == b else 1.0  # cross terms appear twice in the full sum
            total += weight * g * moves.get(a, 0.0) * moves.get(b, 0.0)
        return total


def book_greeks(portfolio: Portfolio, pricer: Pricer) -> BookGreeks:
    """Gammas and vegas of every live trade, added up."""
    gamma: dict[tuple[str, str], float] = {}
    vega: dict[str, float] = {}
    for trade in portfolio:
        if not _is_alive(trade, pricer):
            continue
        apo, calc = trade.instrument, pricer.risk(trade.instrument)
        for a, b in combinations_with_replacement(sorted(apo.underlyings), 2):
            gamma[(a, b)] = gamma.get((a, b), 0.0) + apo.quantity * calc.cross_gamma(a, b)
        for u in apo.underlyings:
            vega[u] = vega.get(u, 0.0) + apo.quantity * calc.vega(u)
    return BookGreeks(gamma=gamma, vega=vega)


def book_theta(portfolio: Portfolio, before: Pricer, today: ql.Date) -> float:
    """PV change from time passing only: yesterday's market moved to today's date."""
    rolled = before.with_market(before.market.roll_to(today))
    return sum(trade_pv(t, rolled) - trade_pv(t, before) for t in portfolio)


def target_lots(deltas: dict[str, float], lot_size: float) -> dict[str, int]:
    """Futures position that cancels the deltas, rounded to whole lots."""
    return {u: -round(d / lot_size) for u, d in deltas.items()}
