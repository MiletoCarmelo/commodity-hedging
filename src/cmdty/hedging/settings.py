"""Bot settings: what we hedge with, how often, and what it costs."""

from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator

from ..market.futures import FUTURES, futures_spec
from ..models import MODELS

# =============================================================================
# 1. Settings
# =============================================================================


class HedgeInstrument(BaseModel):
    """One future the desk allows the bot to trade. Contract specs come from futures.yaml."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    cost_per_lot: float = Field(default=5.0, ge=0)  # $ per lot traded: fees + half the bid-ask


class HedgeSettings(BaseModel):
    """Desk choices for the hedge. They are not trade terms, so they stay out of the portfolio."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    model: str = "kirk"  # pricing model used for PV and deltas
    rebalance_every: int = Field(default=1, ge=1)  # business days between two rebalancings
    explain: bool = True  # compute gammas, vegas and theta every day for the P&L explain
    # futures the bot may use, by underlying. Empty: every future of futures.yaml at cost_per_lot
    instruments: dict[str, HedgeInstrument] = Field(default_factory=dict)
    cost_per_lot: float = Field(default=5.0, ge=0)  # default cost when instruments is empty
    lot_size: float | None = Field(default=None, gt=0)  # override of the contract size, for studies

    @field_validator("model")
    @classmethod
    def _known_model(cls, v: str) -> str:
        if v not in MODELS:
            raise ValueError(f"unknown model {v!r}, choose from {sorted(MODELS)}")
        return v

    @field_validator("instruments")
    @classmethod
    def _known_futures(cls, v: dict) -> dict:
        unknown = sorted(set(v) - set(FUTURES))
        if unknown:
            raise ValueError(f"no futures contract for {unknown}, see futures.yaml")
        return v

    # --- per underlying ---
    def lot(self, underlying: str) -> float:
        """bbl per lot of the future hedging this underlying."""
        return self.lot_size or float(futures_spec(underlying)["lot_size"])

    def cost(self, underlying: str) -> float:
        """$ per lot traded on this underlying's future."""
        if self.instruments:
            return self.instruments[underlying].cost_per_lot
        return self.cost_per_lot

    def check_hedgeable(self, underlyings: set[str]) -> None:
        """Refuse a book with an underlying the desk cannot hedge."""
        allowed = set(self.instruments) or set(FUTURES)
        missing = sorted(underlyings - allowed)
        if missing:
            raise ValueError(f"no hedge instrument for {missing}, add them to the bot settings")


# =============================================================================
# 2. Loading
# =============================================================================


def load_hedge_settings(path: str | Path) -> HedgeSettings:
    """Read the bot settings file, e.g. config/hedging.yaml."""
    return HedgeSettings.model_validate(yaml.safe_load(Path(path).read_text()))
