"""APO contract: max(phi * (average of sum(weight * leg) - K), 0), averaged on a schedule.

One leg is an outright APO, two legs a crack or spread, three a 3-2-1 crack.
Describes what is traded only. Pricing lives in Pricer and cmdty.models.
Valuation works before, during and after the pricing month (see models.averaging).
"""

from collections.abc import Mapping
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from .leg import Leg
from .schedule import AveragingSchedule
from .types import OptionType

# =============================================================================
# APO
# =============================================================================


class APO(BaseModel):
    """Average price option on a weighted basket of futures legs."""

    model_config = ConfigDict(frozen=True, extra="forbid")  # a typo in a field name is an error

    # --- contract terms ---
    legs: list[Leg] = Field(min_length=1)  # e.g. [Leg("HO", 1), Leg("BRENT", -1)]
    strike: float = Field(description="$/bbl, may be negative for spreads")
    option_type: OptionType = OptionType.CALL  # "call" or "put"
    quantity: float = Field(default=1.0, description="bbl, negative = sold")

    # --- dates ---
    schedule: AveragingSchedule  # pricing period, fixing calendar, payment lag

    # --- premium ---
    # upfront: premium paid at trade date, payoff discounted from schedule.pay_date
    # futures_style: margined daily like a future, no discounting (DF = 1)
    premium_style: Literal["upfront", "futures_style"] = "upfront"

    # --- checks ---
    @field_validator("legs")
    @classmethod
    def _unique_underlyings(cls, legs: list[Leg]) -> list[Leg]:
        names = [leg.underlying for leg in legs]
        if len(set(names)) != len(names):
            raise ValueError(f"same underlying used twice in {names}")
        return legs

    @field_validator("quantity")
    @classmethod
    def _non_zero(cls, v: float) -> float:
        if v == 0:
            raise ValueError("quantity cannot be 0")
        return v

    # --- legs ---
    @property
    def underlyings(self) -> list[str]:
        return [leg.underlying for leg in self.legs]

    @property
    def weights(self) -> list[float]:
        return [leg.weight for leg in self.legs]

    def combine(self, prices: Mapping[str, float]) -> float:
        """sum(weight * price) over the legs: the number that gets averaged."""
        return sum(leg.weight * prices[leg.underlying] for leg in self.legs)

    # --- payoff ---
    @property
    def phi(self) -> float:
        """Payoff sign: +1 for a call, -1 for a put."""
        return self.option_type.sign
