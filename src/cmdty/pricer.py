"""Pricer: a model applied to a market snapshot. Contracts stay untouched."""

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from .instruments.apo import APO
from .market.market_data import MarketData
from .models import MODELS
from .risk.greeks import GreekCalculator, Greeks, SpreadGreekCalculator


class Pricer(BaseModel):
    """Same idea as QuantLib's setPricingEngine, without touching the instrument."""

    # "model" and "model_kwargs" are our fields, not pydantic methods (silences pydantic < 2.10)
    model_config = ConfigDict(frozen=True, protected_namespaces=())

    model: str = "kirk"
    market: MarketData
    model_kwargs: dict[str, Any] = Field(default_factory=dict)  # e.g. n_paths, seed

    @field_validator("model")
    @classmethod
    def _check_model(cls, v: str) -> str:
        if v not in MODELS:
            raise ValueError(f"unknown model {v!r}, choose from {sorted(MODELS)}")
        return v

    # --- pricing ---
    def expected_payoff(self, apo: APO) -> float:
        """Undiscounted, $/bbl."""
        return MODELS[self.model](apo, self.market, **self.model_kwargs)

    def discount_factor(self, apo: APO) -> float:
        """Market curve read at the trade's pay date; 1 if futures-style margined."""
        if apo.premium_style == "futures_style":
            return 1.0
        return self.market.discount_factor(apo.schedule.pay_date, apo.schedule.day_counter)

    def pv(self, apo: APO) -> float:
        """Present value, $/bbl. Zero once the payoff has been paid."""
        if self.market.today > apo.schedule.pay_date:
            return 0.0
        return self.discount_factor(apo) * self.expected_payoff(apo)

    # --- risk ---
    def risk(self, apo: APO) -> GreekCalculator:
        """Calculator for one greek at a time, e.g. pricer.risk(apo).vega("HO").
        Two legs get the spread calculator (crack, outright, correlation)."""
        if len(apo.legs) == 2:
            return SpreadGreekCalculator(self, apo)
        return GreekCalculator(self, apo)

    def deltas(self, apo: APO, h: float = 0.01) -> dict[str, float]:
        """dPV/dF per underlying, any number of legs."""
        return self.risk(apo).deltas(h)

    def greeks(self, apo: APO) -> Greeks:
        """All sensitivities of a two-leg spread: deltas, gammas, vegas, correlation, theta, rho."""
        return SpreadGreekCalculator(self, apo).all()

    # --- variants ---
    def with_model(self, model: str) -> "Pricer":
        return Pricer(model=model, market=self.market, model_kwargs=self.model_kwargs)

    def with_market(self, market: MarketData) -> "Pricer":
        return Pricer(model=self.model, market=market, model_kwargs=self.model_kwargs)

    def with_model_kwargs(self, **kwargs: Any) -> "Pricer":
        return Pricer(
            model=self.model, market=self.market, model_kwargs={**self.model_kwargs, **kwargs}
        )
