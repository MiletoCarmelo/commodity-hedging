"""Pricer: a model applied to a market snapshot. Contracts stay untouched."""

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from .instruments.apo import APO
from .instruments.vanilla import VanillaOption
from .market.market_data import MarketData
from .models import MODELS, black76
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
    def expected_payoff(self, instrument: APO | VanillaOption) -> float:
        """Undiscounted, $/bbl. Vanillas: Black-76 (Bachelier if model="bachelier")."""
        if isinstance(instrument, VanillaOption):
            return black76.expected_payoff(instrument, self.market,
                                           normal=self.model == "bachelier")
        return MODELS[self.model](instrument, self.market, **self.model_kwargs)

    def discount_factor(self, instrument: APO | VanillaOption) -> float:
        """Market curve read at the trade's pay date; 1 if futures-style margined."""
        if instrument.premium_style == "futures_style":
            return 1.0
        day_counter = (instrument.day_counter if isinstance(instrument, VanillaOption)
                       else instrument.schedule.day_counter)
        return self.market.discount_factor(instrument.pay_date, day_counter)

    def pv(self, instrument: APO | VanillaOption) -> float:
        """Present value, $/bbl. Zero once the payoff has been paid."""
        if self.market.today > instrument.pay_date:
            return 0.0
        return self.discount_factor(instrument) * self.expected_payoff(instrument)

    # --- risk ---
    def risk(self, apo: APO) -> GreekCalculator:
        """Calculator for one greek at a time, e.g. pricer.risk(apo).vega("HO").
        Two legs get the spread calculator (crack, outright, correlation)."""
        if len(getattr(apo, "legs", [])) == 2:
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
