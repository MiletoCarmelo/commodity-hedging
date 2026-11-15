"""Pricing models. Each exposes expected_payoff(apo, market, **kwargs) -> undiscounted $/bbl."""
from . import bachelier, kirk, montecarlo

MODELS = {
    "bachelier": bachelier.expected_payoff,
    "kirk": kirk.expected_payoff,
    "mc": montecarlo.expected_payoff,
}

