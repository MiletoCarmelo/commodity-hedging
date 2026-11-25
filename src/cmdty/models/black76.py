"""Vanilla options on futures with QuantLib's Black-76 (and Bachelier) formulas.

Black-76: the future is lognormal, sigma is the quoted (lognormal) implied vol.
Bachelier: the future is normal, the $ vol is sigma * F frozen at today's forward.
Both return the undiscounted expected payoff in $/bbl; the Pricer discounts.
"""

import math
from dataclasses import dataclass

import QuantLib as ql

from ..instruments.vanilla import VanillaOption
from ..market.market_data import MarketData


def time_to_expiry(option: VanillaOption, market: MarketData) -> float:
    """Years from today to expiry, 0 once expired."""
    return max(option.day_counter.yearFraction(market.today, option.expiry), 0.0)


def expected_payoff(option: VanillaOption, market: MarketData, normal: bool = False) -> float:
    """Undiscounted price in $/bbl. normal=True uses Bachelier instead of Black-76."""
    f, k = market.forward(option.underlying), option.strike
    t = time_to_expiry(option, market)
    if t == 0.0:
        return max(option.phi * (f - k), 0.0)  # intrinsic on the expiry day
    sigma = market.vol(option.underlying)
    if normal:
        return ql.bachelierBlackFormula(option.option_type.ql, k, f, sigma * f * math.sqrt(t))
    return ql.blackFormula(option.option_type.ql, k, f, sigma * math.sqrt(t))


@dataclass(frozen=True)
class AnalyticGreeks:
    """Black-76 greeks from QuantLib, per unit (undiscounted, like expected_payoff)."""

    price: float
    delta: float  # per +1 $ on the future
    gamma: float  # change of delta per $
    vega: float  # per +1 vol point


def analytic_greeks(option: VanillaOption, market: MarketData) -> AnalyticGreeks:
    """Closed-form greeks with ql.BlackCalculator, to check the bump-and-reprice ones."""
    f, t = market.forward(option.underlying), time_to_expiry(option, market)
    if t == 0.0:
        itm = option.phi * (f - option.strike) > 0
        return AnalyticGreeks(max(option.phi * (f - option.strike), 0.0),
                              option.phi if itm else 0.0, 0.0, 0.0)
    std = market.vol(option.underlying) * math.sqrt(t)
    calc = ql.BlackCalculator(ql.PlainVanillaPayoff(option.option_type.ql, option.strike), f, std, 1.0)
    return AnalyticGreeks(calc.value(), calc.deltaForward(), calc.gammaForward(),
                          calc.vega(t) / 100)
