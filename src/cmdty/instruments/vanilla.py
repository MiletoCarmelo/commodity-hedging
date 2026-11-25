"""Vanilla option on a futures contract: max(phi * (F_T - K), 0) at expiry.

The building block of options strategies (straddles, spreads, butterflies) and of gamma and
vega hedging. Describes what is traded only; pricing lives in Pricer and models.black76.
"""

from typing import Literal

import QuantLib as ql
from pydantic import BaseModel, ConfigDict, Field, field_validator

from ..market.dates import to_ql_date
from .types import OptionType


class VanillaOption(BaseModel):
    """European option on one futures contract, cash-settled at expiry."""

    model_config = ConfigDict(frozen=True, arbitrary_types_allowed=True, extra="forbid")

    # --- contract terms ---
    underlying: str = Field(min_length=1)  # e.g. "BRENT"
    contract: str = Field(pattern=r"^\d{4}-\d{2}$", description="futures delivery month, 'YYYY-MM'")
    strike: float
    option_type: OptionType = OptionType.CALL
    quantity: float = Field(default=1.0, description="bbl, negative = sold")

    # --- dates ---
    expiry: ql.Date  # last day the option lives; 'YYYY-MM-DD' accepted
    day_counter: ql.DayCounter = Field(default_factory=ql.Actual365Fixed)

    # --- premium ---
    premium_style: Literal["upfront", "futures_style"] = "upfront"

    _to_date = field_validator("expiry", mode="before")(to_ql_date)

    @field_validator("quantity")
    @classmethod
    def _non_zero(cls, v: float) -> float:
        if v == 0:
            raise ValueError("quantity cannot be 0")
        return v

    # --- same interface as APO ---
    @property
    def underlyings(self) -> list[str]:
        return [self.underlying]

    @property
    def phi(self) -> float:
        """+1 for a call, -1 for a put."""
        return self.option_type.sign

    @property
    def pay_date(self) -> ql.Date:
        """Cash-settled at expiry."""
        return self.expiry
