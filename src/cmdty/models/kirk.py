"""Kirk approximation (ql.KirkEngine) with maturity T_eff for the averaging.

Two legs, one long and one short. Weights scale the forwards: w1 * F1 - |w2| * F2.
One leg is the outright case: Black-76 on the average, same T_eff.

The engine runs with a zero rate, so it returns the undiscounted payoff. Discounting
to the payment date is done by the Pricer (KirkEngine would discount to expiry).
"""

import warnings

import QuantLib as ql

from . import bachelier
from .averaging import averaging_state, settled_payoff

# =============================================================================
# 1. Pricing
# =============================================================================


def expected_payoff(apo, market) -> float:
    """Undiscounted expected payoff of a two-leg spread APO with Kirk.
    One leg (outright): Kirk with no second asset, i.e. Black-76 on the average."""
    state = averaging_state(apo, market)
    if state.done:
        return settled_payoff(apo, state)
    if len(apo.legs) == 1:
        return _black_outright(apo, market, state)

    today = market.today
    long, short = _long_short(apo)
    u1, u2 = long.underlying, short.underlying
    f1, f2 = long.weight * market.forward(u1), -short.weight * market.forward(u2)
    strike = state.adjusted_strike(apo.strike)
    days = int(round(apo.schedule.t_eff(today, state.today_fixed) * 365))

    if days == 0:  # only today's fixing left: no time value
        return state.weight * max(apo.phi * (f1 - f2 - strike), 0.0)
    if f2 + strike <= 0:  # Kirk needs F2 + K > 0 (deep in the money call)
        warnings.warn("Kirk undefined for F2 + K* <= 0, using Bachelier")
        return bachelier.expected_payoff(apo, market)

    ql.Settings.instance().evaluationDate = today
    zero = ql.YieldTermStructureHandle(ql.FlatForward(today, 0.0, apo.schedule.day_counter))

    # averaging approximated by a European option expiring at T_eff, strike K*
    option = ql.BasketOption(
        ql.SpreadBasketPayoff(ql.PlainVanillaPayoff(apo.option_type.ql, strike)),
        ql.EuropeanExercise(today + days),
    )
    dc = apo.schedule.day_counter
    leg1 = _black_process(today, f1, market.vol(u1), zero, dc)
    leg2 = _black_process(today, f2, market.vol(u2), zero, dc)
    option.setPricingEngine(ql.KirkEngine(leg1, leg2, market.corr(u1, u2)))
    return state.weight * option.NPV()


# =============================================================================
# 2. Kirk helpers
# =============================================================================


def _black_outright(apo, market, state) -> float:
    """Outright APO: lognormal average, Black-76 with T_eff and the adjusted strike."""
    leg = apo.legs[0]
    if leg.weight < 0:
        raise ValueError("outright APO needs a positive weight")
    forward = leg.weight * market.forward(leg.underlying)
    strike = state.adjusted_strike(apo.strike)
    t = apo.schedule.t_eff(market.today, state.today_fixed)
    if t == 0:  # only today's fixing left: no time value
        return state.weight * max(apo.phi * (forward - strike), 0.0)
    if strike <= 0:  # average already above any level: the call is a forward, the put is worth 0
        return state.weight * max(apo.phi * (forward - strike), 0.0)
    std = market.vol(leg.underlying) * t**0.5
    return state.weight * ql.blackFormula(apo.option_type.ql, strike, forward, std, 1.0)


def _long_short(apo):
    """The long and the short leg. Kirk is a two-leg formula, anything else is refused."""
    if len(apo.legs) != 2:
        raise ValueError(f"Kirk needs exactly 2 legs, got {len(apo.legs)}")
    a, b = apo.legs
    if a.weight * b.weight > 0:
        raise ValueError("Kirk needs one long and one short leg")
    return (a, b) if a.weight > 0 else (b, a)


def _black_process(
    today: ql.Date,
    forward: float,
    vol: float,
    rate: ql.YieldTermStructureHandle,
    day_counter: ql.DayCounter,
) -> ql.BlackProcess:
    """Lognormal process of a futures price (Black-76: no drift), constant vol."""
    return ql.BlackProcess(
        ql.QuoteHandle(ql.SimpleQuote(forward)),
        rate,
        ql.BlackVolTermStructureHandle(
            ql.BlackConstantVol(today, ql.NullCalendar(), vol, day_counter)
        ),
    )
