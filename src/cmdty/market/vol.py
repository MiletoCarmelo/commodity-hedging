"""Volatilities."""

import math

import QuantLib as ql

# =============================================================================
# 1. Implied volatilities
# =============================================================================


def implied_vol_black76(
    price: float,
    forward: float,
    strike: float,
    t: float,
    option_type=ql.Option.Call,
    discount: float = 1.0,
) -> float:
    """Annualised Black-76 implied vol from a European option price on a future."""
    # QuantLib returns sigma * sqrt(T), not sigma
    std = ql.blackFormulaImpliedStdDev(option_type, strike, forward, price, discount)
    return std / math.sqrt(t)


def implied_vol_normal(
    price: float,
    forward: float,
    strike: float,
    t: float,
    option_type=ql.Option.Call,
    discount: float = 1.0,
) -> float:
    """Annualised normal (Bachelier) implied vol, in price units per year ($/bbl)."""
    return ql.bachelierBlackFormulaImpliedVol(
        option_type, strike, forward, t, price, discount
    )


# =============================================================================
# 2. Generic volatility functions
# =============================================================================


def lognormal_to_normal_vol(vol: float, forward: float) -> float:
    """ATM approximation: normal vol = lognormal vol x forward."""
    return vol * forward


def normal_to_lognormal_vol(normal_vol: float, forward: float) -> float:
    """ATM approximation: lognormal vol = normal vol / forward."""
    return normal_vol / forward


def spread_vol(vol1: float, vol2: float, rho: float) -> float:
    """Vol of X1 - X2 for two correlated variables with vols vol1, vol2."""
    return math.sqrt(vol1**2 + vol2**2 - 2 * rho * vol1 * vol2)
