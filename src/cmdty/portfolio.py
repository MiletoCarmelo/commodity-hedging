"""Portfolio: the trades we hold, read from a YAML file.

Each trade has an id and a `type` that says which instrument to build. Adding a product
means adding one builder to TRADE_TYPES, the rest of the loader does not change.
"""

from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator

from .instruments import APO, VanillaOption
from .market.calendars import joint_exchange_calendar

# =============================================================================
# 1. Builders: one per trade type
# =============================================================================


def _build_apo(terms: dict[str, Any]) -> APO:
    """APO from its YAML terms. The calendar comes as exchange codes, e.g. [NYMEX, ICE-EU]."""
    schedule = dict(terms["schedule"])
    schedule["calendar"] = joint_exchange_calendar(schedule["calendar"])
    return APO.model_validate({**terms, "schedule": schedule})


def _build_vanilla(terms: dict[str, Any]) -> VanillaOption:
    """Vanilla option on a futures contract, expiry as 'YYYY-MM-DD'."""
    return VanillaOption.model_validate(terms)


TRADE_TYPES: dict[str, Callable[[dict[str, Any]], Any]] = {
    "apo": _build_apo,
    "vanilla": _build_vanilla,
}


# =============================================================================
# 2. Trade and portfolio
# =============================================================================


class Trade(BaseModel):
    """One position: an id we can follow in the P&L, and the instrument itself."""

    model_config = ConfigDict(frozen=True, arbitrary_types_allowed=True)

    id: str = Field(min_length=1)
    instrument: Any


class Portfolio(BaseModel):
    """A named list of trades with unique ids."""

    model_config = ConfigDict(frozen=True)

    name: str
    trades: list[Trade]

    @model_validator(mode="after")
    def _unique_ids(self) -> "Portfolio":
        ids = [t.id for t in self.trades]
        if len(set(ids)) != len(ids):
            raise ValueError(f"duplicate trade ids in {ids}")
        return self

    def __iter__(self) -> Iterator[Trade]:
        return iter(self.trades)

    def __len__(self) -> int:
        return len(self.trades)

    def trade(self, trade_id: str) -> Trade:
        for t in self.trades:
            if t.id == trade_id:
                return t
        raise KeyError(f"no trade {trade_id!r}")


# =============================================================================
# 3. Loading
# =============================================================================


def _portfolio_from_dict(data: dict[str, Any]) -> Portfolio:
    """Portfolio from the parsed YAML. Errors name the trade they come from."""
    trades = []
    for raw in data.get("trades") or []:
        terms = dict(raw)
        trade_id, kind = terms.pop("id", None), terms.pop("type", None)
        if kind not in TRADE_TYPES:
            raise ValueError(f"trade {trade_id}: unknown type {kind!r}, choose from {sorted(TRADE_TYPES)}")
        try:
            instrument = TRADE_TYPES[kind](terms)
        except (ValueError, KeyError) as err:
            raise ValueError(f"trade {trade_id}: {err}") from err
        trades.append(Trade(id=trade_id, instrument=instrument))
    return Portfolio(name=data["portfolio"], trades=trades)


def load_portfolio(path: str | Path) -> Portfolio:
    """Read a portfolio file, e.g. portfolios/example_book.yaml."""
    return _portfolio_from_dict(yaml.safe_load(Path(path).read_text()))
