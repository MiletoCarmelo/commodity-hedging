"""Options strategies built from vanilla options on one futures contract.

Each function returns a list of Trade: the building blocks of the strategy. A positive
size buys the strategy, a negative size sells it (a short straddle is size < 0).
position_greeks adds up the greeks of any list of trades, the way a desk reads a book.
"""

from dataclasses import dataclass
from typing import TYPE_CHECKING

from .instruments.types import OptionType
from .instruments.vanilla import VanillaOption
from .portfolio import Trade

if TYPE_CHECKING:  # avoid a circular import, only for type hints
    from .pricer import Pricer

# =============================================================================
# 1. Building blocks
# =============================================================================


def option(name: str, underlying: str, contract: str, expiry: str, strike: float,
           option_type: str, size: float) -> Trade:
    """One vanilla option as a trade. size in bbl, negative = sold."""
    return Trade(id=name, instrument=VanillaOption(
        underlying=underlying, contract=contract, expiry=expiry, strike=strike,
        option_type=OptionType(option_type), quantity=size))


# =============================================================================
# 2. Strategies
# =============================================================================


def straddle(u: str, contract: str, expiry: str, k: float, size: float) -> list[Trade]:
    """Call K + put K. Bought: long gamma and vega, no direction."""
    return [option("call", u, contract, expiry, k, "call", size),
            option("put", u, contract, expiry, k, "put", size)]


def strangle(u: str, contract: str, expiry: str, k_put: float, k_call: float,
             size: float) -> list[Trade]:
    """Put K1 + call K2 (K1 < K2). A cheaper straddle that needs a bigger move."""
    return [option("put", u, contract, expiry, k_put, "put", size),
            option("call", u, contract, expiry, k_call, "call", size)]


def call_spread(u: str, contract: str, expiry: str, k1: float, k2: float,
                size: float) -> list[Trade]:
    """Bull call spread: buy call K1, sell call K2 (K1 < K2). Capped upside, cheaper."""
    return [option("call low", u, contract, expiry, k1, "call", size),
            option("call high", u, contract, expiry, k2, "call", -size)]


def put_spread(u: str, contract: str, expiry: str, k1: float, k2: float,
               size: float) -> list[Trade]:
    """Bear put spread: buy put K2, sell put K1 (K1 < K2)."""
    return [option("put high", u, contract, expiry, k2, "put", size),
            option("put low", u, contract, expiry, k1, "put", -size)]


def butterfly(u: str, contract: str, expiry: str, k1: float, k2: float, k3: float,
              size: float) -> list[Trade]:
    """+1 call K1, -2 calls K2, +1 call K3. Bought: the price stays near K2, vol falls."""
    return [option("call low", u, contract, expiry, k1, "call", size),
            option("call mid", u, contract, expiry, k2, "call", -2 * size),
            option("call high", u, contract, expiry, k3, "call", size)]


def risk_reversal(u: str, contract: str, expiry: str, k_put: float, k_call: float,
                  size: float) -> list[Trade]:
    """Buy call K2, sell put K1. Bullish for little premium; trades the skew."""
    return [option("call", u, contract, expiry, k_call, "call", size),
            option("put", u, contract, expiry, k_put, "put", -size)]


# =============================================================================
# 3. Greeks of a position
# =============================================================================


@dataclass(frozen=True)
class PositionGreeks:
    """Greeks of a list of trades on one underlying, in $ (signed quantities included)."""

    pv: float
    delta: float  # $ per +1 $ on the future, i.e. bbl
    gamma: float  # change of delta per $
    vega: float  # $ per +1 vol point
    theta: float  # $ for one calendar day passing


def position_greeks(trades: list[Trade], pricer: "Pricer", underlying: str) -> PositionGreeks:
    """Bump-and-reprice greeks of each trade, times its quantity, added up."""
    totals = dict(pv=0.0, delta=0.0, gamma=0.0, vega=0.0, theta=0.0)
    for t in trades:
        q, calc = t.instrument.quantity, pricer.risk(t.instrument)
        totals["pv"] += q * pricer.pv(t.instrument)
        totals["delta"] += q * calc.delta(underlying)
        totals["gamma"] += q * calc.gamma(underlying)
        totals["vega"] += q * calc.vega(underlying)
        totals["theta"] += q * calc.theta(1)
    return PositionGreeks(**totals)
