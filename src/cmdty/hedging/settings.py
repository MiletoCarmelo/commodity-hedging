"""Bot settings: how and how often we hedge, what it costs."""

from pydantic import BaseModel, ConfigDict, Field, field_validator

from ..models import MODELS


class HedgeSettings(BaseModel):
    """Desk choices for the hedge. They are not trade terms, so they stay out of the portfolio."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    model: str = "kirk"  # pricing model used for PV and deltas
    lot_size: float = Field(default=1000.0, gt=0)  # bbl per futures lot (HO and Brent)
    cost_per_lot: float = Field(default=5.0, ge=0)  # $ per lot traded: fees + half the bid-ask
    rebalance_every: int = Field(default=1, ge=1)  # business days between two rebalancings
    explain: bool = True  # compute gammas, vegas and theta every day for the P&L explain

    @field_validator("model")
    @classmethod
    def _known_model(cls, v: str) -> str:
        if v not in MODELS:
            raise ValueError(f"unknown model {v!r}, choose from {sorted(MODELS)}")
        return v
