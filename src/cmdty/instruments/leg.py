"""Contract leg: what is referenced and with which weight, not what it is worth."""

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class Leg(BaseModel):
    """One leg of a trade: an underlying quoted in MarketData and its weight.

    The averaged price is sum(weight * price) over the legs. Positive weight = long
    the leg, negative = short. Leg("HO") alone is an outright.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")  # a typo in a field name is an error

    underlying: str = Field(min_length=1, description="market data key, e.g. 'HO'")
    weight: float = 1.0

    def __init__(self, underlying: str, weight: float = 1.0, **kwargs: Any) -> None:
        """Allow Leg("BRENT", -1) as well as Leg(underlying="BRENT", weight=-1)."""
        super().__init__(underlying=underlying, weight=weight, **kwargs)

    @field_validator("weight")
    @classmethod
    def _non_zero(cls, v: float) -> float:
        if v == 0:
            raise ValueError("leg weight cannot be 0")
        return v
