"""Greeks of a whole portfolio: each trade's greeks (risk/greeks.py) times its signed
quantity, added up per underlying. Nothing is repriced here that greeks.py does not already do."""

from dataclasses import dataclass
from itertools import combinations_with_replacement
from typing import TYPE_CHECKING

import QuantLib as ql

from ..market.futures import front_contract
from ..models.averaging import averaging_state
from ..portfolio import Portfolio, Trade

if TYPE_CHECKING:  # avoid a circular import, only for type hints
    from ..pricer import Pricer

# =============================================================================
# 1. One trade
# =============================================================================


def _is_alive(trade: Trade, pricer: "Pricer") -> bool:
    """Still has a value: the payoff has not been paid yet."""
    return pricer.market.today <= trade.instrument.pay_date


def trade_pv(trade: Trade, pricer: "Pricer") -> float:
    """PV of the position in $: quantity (signed) x PV per bbl."""
    if not _is_alive(trade, pricer):
        return 0.0
    return trade.instrument.quantity * pricer.pv(trade.instrument)


def trade_deltas(trade: Trade, pricer: "Pricer") -> dict[str, float]:
    """$ change per +1 $/bbl on each underlying, i.e. an exposure in bbl."""
    if not _is_alive(trade, pricer):
        return {}
    apo = trade.instrument
    return {u: apo.quantity * d for u, d in pricer.deltas(apo).items()}


def contract_weights(trade: Trade, pricer: "Pricer") -> dict[tuple[str, str], float]:
    """Share of each futures contract in the remaining average, per leg.

    Each fixing uses the front contract of its date. A leg whose fixings straddle an
    expiry (WTI in April: May contract until the 20th, June after) splits over two months.
    Keys are (underlying, "YYYY-MM") of the delivery month.
    """
    apo, market = trade.instrument, pricer.market
    if not hasattr(apo, "schedule"):  # vanilla option: one futures contract
        return {(apo.underlying, apo.contract): 1.0}
    state = averaging_state(apo, market)
    remaining = apo.schedule.future_fixings(market.today, state.today_fixed)
    weights: dict[tuple[str, str], float] = {}
    for u in apo.underlyings:
        for d in remaining:
            y, m = front_contract(u, d)
            key = (u, f"{y}-{m:02d}")
            weights[key] = weights.get(key, 0.0) + 1.0 / len(remaining)
    return weights


def trade_deltas_by_contract(trade: Trade, pricer: "Pricer") -> dict[tuple[str, str], float]:
    """Deltas of one trade split by futures contract: what has to be hedged, month by month."""
    deltas = trade_deltas(trade, pricer)
    return {key: deltas[key[0]] * w for key, w in contract_weights(trade, pricer).items()
            if key[0] in deltas}


def paid_cash(trade: Trade, before: "Pricer", after: "Pricer") -> float:
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
    deltas_by_contract: dict[tuple[str, str], float]  # bbl per (underlying, "YYYY-MM")


def book_risk(portfolio: Portfolio, pricer: "Pricer") -> BookRisk:
    """Price every trade and add up the deltas per underlying and per contract (netting)."""
    deltas: dict[str, float] = {}
    by_contract: dict[tuple[str, str], float] = {}
    pvs = {}
    for trade in portfolio:
        pvs[trade.id] = trade_pv(trade, pricer)
        if not _is_alive(trade, pricer):
            continue
        trade_delta = trade_deltas(trade, pricer)  # priced once, then split by contract
        for u, d in trade_delta.items():
            deltas[u] = deltas.get(u, 0.0) + d
        for key, w in contract_weights(trade, pricer).items():
            by_contract[key] = by_contract.get(key, 0.0) + trade_delta[key[0]] * w
    return BookRisk(pv=sum(pvs.values()), deltas=deltas, pv_by_trade=pvs,
                    deltas_by_contract=by_contract)


# =============================================================================
# 3. Second-order greeks and theta, for the P&L explain
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


def book_greeks(portfolio: Portfolio, pricer: "Pricer") -> BookGreeks:
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


def book_theta(portfolio: Portfolio, before: "Pricer", today: ql.Date) -> float:
    """PV change from time passing only, yesterday's market moved to `today`."""
    return sum(
        t.instrument.quantity * before.risk(t.instrument).theta_to(today)
        for t in portfolio
        if _is_alive(t, before)
    )
