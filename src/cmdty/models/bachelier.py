"""Normal (Bachelier) model on the basket, exact variance of the discrete average.

Works for any number of legs: the basket is a sum of normal variables.
"""

import math

import numpy as np
import QuantLib as ql

from ..market.vol import lognormal_to_normal_vol
from .averaging import averaging_state, settled_payoff

# =============================================================================
# 1. Pricing
# =============================================================================


def expected_payoff(apo, market, normal_vol: float | None = None) -> float:
    """Undiscounted expected payoff. normal_vol ($/bbl/yr) replaces the vol built from the legs."""
    state = averaging_state(apo, market)
    if state.done:
        return settled_payoff(apo, state)

    sigma_n = normal_vol if normal_vol is not None else spread_normal_vol(apo, market)
    forward = apo.combine({u: market.forward(u) for u in apo.underlyings})
    std = sigma_n * math.sqrt(apo.schedule.t_eff(market.today, state.today_fixed))
    # option on the remaining fixings: adjusted strike, weighted by their share
    strike = state.adjusted_strike(apo.strike)
    return state.weight * ql.bachelierBlackFormula(apo.option_type.ql, strike, forward, std, 1.0)


# =============================================================================
# 2. Bachelier helpers
# =============================================================================


def spread_normal_vol(apo, market) -> float:
    """Bachelier input: $ vol of the basket, sqrt(w' C w) with C the $ covariance of the legs."""
    u = apo.underlyings
    w = np.array(apo.weights)
    v = np.array([lognormal_to_normal_vol(market.vol(x), market.forward(x)) for x in u])
    corr = np.array([[market.corr(a, b) for b in u] for a in u])
    cov = corr * np.outer(v, v)
    return math.sqrt(max(w @ cov @ w, 0.0))
