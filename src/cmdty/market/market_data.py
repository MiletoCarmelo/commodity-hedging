"""Market snapshot: everything that moves every day, kept out of the contracts."""

from typing import Any

import QuantLib as ql
from pydantic import BaseModel, ConfigDict, Field, field_validator

from .curves import flat_discount_factor
from .dates import to_ql_date

# =============================================================================
# 1. Quote
# =============================================================================


class Quote(BaseModel):
    """Forward price and implied vol of one underlying."""

    model_config = ConfigDict(frozen=True)

    forward: float = Field(gt=0, description="futures price, $/bbl")
    vol: float = Field(gt=0, le=5, description="annualised lognormal vol (0.30 = 30%)")

    def __init__(self, forward: float, vol: float, **kwargs: Any) -> None:
        """Allow Quote(105.0, 0.30) as well as keyword arguments."""
        super().__init__(forward=forward, vol=vol, **kwargs)


# =============================================================================
# 2. Market data
# =============================================================================


class MarketData(BaseModel):
    """Valuation date, rate, quotes per underlying and correlations between them."""

    model_config = ConfigDict(frozen=True, arbitrary_types_allowed=True)

    today: ql.Date
    rate: float = Field(description="flat discount rate, continuous compounding")
    quotes: dict[str, Quote]
    correlations: dict[tuple[str, str], float] = Field(default_factory=dict)
    fixings: dict[str, dict[Any, float]] = Field(default_factory=dict)  # published settlements

    _to_date = field_validator("today", mode="before")(to_ql_date)

    @field_validator("fixings", mode="before")
    @classmethod
    def _fixing_dates(cls, v: dict) -> dict:
        """Accept dates as ql.Date, datetime.date or 'YYYY-MM-DD'."""
        return {u: {to_ql_date(d): float(p) for d, p in series.items()} for u, series in v.items()}

    @field_validator("correlations")
    @classmethod
    def _check_correlations(cls, v: dict) -> dict:
        for pair, rho in v.items():
            if not -1 <= rho <= 1:
                raise ValueError(f"correlation {pair} = {rho} outside [-1, 1]")
        return v

    # --- lookups ---
    def quote(self, underlying: str) -> Quote:
        try:
            return self.quotes[underlying]
        except KeyError:
            raise KeyError(f"no quote for {underlying!r}, have {sorted(self.quotes)}") from None

    def forward(self, underlying: str) -> float:
        return self.quote(underlying).forward

    def vol(self, underlying: str) -> float:
        return self.quote(underlying).vol

    def corr(self, a: str, b: str) -> float:
        """Symmetric lookup; 1 for the same underlying."""
        if a == b:
            return 1.0
        for pair in ((a, b), (b, a)):
            if pair in self.correlations:
                return self.correlations[pair]
        raise KeyError(f"no correlation between {a!r} and {b!r}")

    def discount_factor(self, pay_date: ql.Date, day_counter: ql.DayCounter | None = None) -> float:
        return flat_discount_factor(self.today, pay_date, self.rate, day_counter)

    # --- fixings ---
    def fixing(self, underlying: str, date: ql.Date) -> float:
        """Published settlement of one underlying on one date."""
        try:
            return self.fixings[underlying][date]
        except KeyError:
            raise KeyError(f"no fixing for {underlying!r} on {date.ISO()}") from None

    def with_fixings(self, underlying: str, fixings: dict) -> "MarketData":
        """Copy with more published settlements for one underlying."""
        series = {**self.fixings.get(underlying, {}), **{to_ql_date(d): float(p) for d, p in fixings.items()}}
        return self.model_copy(update={"fixings": {**self.fixings, underlying: series}})

    # --- scenarios ---
    def bump_forward(self, underlying: str, h: float) -> "MarketData":
        """Copy with the forward of one underlying moved by h."""
        q = self.quote(underlying)
        quotes = {**self.quotes, underlying: Quote(q.forward + h, q.vol)}
        return self.model_copy(update={"quotes": quotes})

    def bump_vol(self, underlying: str, h: float) -> "MarketData":
        """Copy with the vol of one underlying moved by h (0.01 = 1 vol point)."""
        q = self.quote(underlying)
        quotes = {**self.quotes, underlying: Quote(q.forward, q.vol + h)}
        return self.model_copy(update={"quotes": quotes})

    def bump_corr(self, a: str, b: str, h: float) -> "MarketData":
        """Copy with the correlation between a and b moved by h."""
        correlations = {k: v for k, v in self.correlations.items() if set(k) != {a, b}}
        correlations[(a, b)] = self.corr(a, b) + h
        return self.model_copy(update={"correlations": correlations})

    def bump_rate(self, h: float) -> "MarketData":
        """Copy with the discount rate moved by h (0.0001 = 1 bp)."""
        return self.model_copy(update={"rate": self.rate + h})

    def roll_to(self, today: ql.Date, fill_fixings: bool = True) -> "MarketData":
        """Same quotes, another valuation date (for theta).

        Days skipped get the current forward as fixing, i.e. "the market did not move".
        """
        fixings = {u: dict(series) for u, series in self.fixings.items()}
        if fill_fixings:
            d = self.today
            while d < today:
                for u, q in self.quotes.items():
                    fixings.setdefault(u, {}).setdefault(d, q.forward)
                d = d + 1
        return self.model_copy(update={"today": today, "fixings": fixings})
