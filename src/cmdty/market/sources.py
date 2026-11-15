"""Market sources: where the bot gets its MarketData, one snapshot per day.

The bot only knows `dates()` and `snapshot(date)`. Simulated for now, historical and
live sources will follow the same interface.
"""

from typing import Protocol

import numpy as np
import QuantLib as ql

from ..models.montecarlo import correlated_brownians, futures_paths
from .calendars import business_days
from .market_data import MarketData, Quote

# =============================================================================
# 1. Interface
# =============================================================================


class MarketSource(Protocol):
    """Anything that can give the end-of-day market on a list of dates."""

    def dates(self) -> list[ql.Date]: ...

    def snapshot(self, date: ql.Date) -> MarketData: ...


# =============================================================================
# 2. Simulated source
# =============================================================================


class SimulatedSource:
    """One random path of the futures, driftless GBM, from a starting market.

    The pricer keeps seeing the implied vols of `start`. The path moves with
    `realized_vol` and `realized_corr`, which default to the implied ones. Setting them
    apart is how we test selling at 30% implied when the market realises 25%.
    Snapshots are end of day: the day's settlement is the forward and is already published
    as that day's fixing.
    Simplification: one forward per underlying, no contract roll.
    """

    def __init__(
        self,
        start: MarketData,
        end: ql.Date,
        calendar: ql.Calendar,
        realized_vol: dict[str, float] | None = None,
        realized_corr: float | dict[tuple[str, str], float] | None = None,
        seed: int = 0,
    ) -> None:
        self.start = start
        self.underlyings = list(start.quotes)
        self.realized_vol = {u: start.vol(u) for u in self.underlyings} | (realized_vol or {})
        self.corr = self._corr_matrix(realized_corr)

        # business days after the start date, up to end
        self._dates = [d for d in business_days(calendar, start.today, end) if d > start.today]
        self.settlements = self._simulate(seed)  # underlying -> {date: price}

    # --- interface ---
    def dates(self) -> list[ql.Date]:
        """Start date, then every simulated business day."""
        return [self.start.today, *self._dates]

    def snapshot(self, date: ql.Date) -> MarketData:
        """End-of-day market: today's settlement is the forward and today's fixing."""
        if date == self.start.today:
            return self.start
        if date not in self.settlements[self.underlyings[0]]:
            raise KeyError(f"{date.ISO()} is not a simulated date")
        quotes = {
            u: Quote(self.settlements[u][date], self.start.vol(u)) for u in self.underlyings
        }
        fixings = {u: dict(self.start.fixings.get(u, {})) for u in self.underlyings}
        for u in self.underlyings:
            fixings[u][self.start.today] = self.start.forward(u)
            fixings[u].update({d: p for d, p in self.settlements[u].items() if d <= date})
        return self.start.model_copy(update={"today": date, "quotes": quotes, "fixings": fixings})

    # --- simulation ---
    def _corr_matrix(self, realized_corr) -> np.ndarray:
        """Realised correlation matrix: one number for every pair, a dict, or the implied one."""
        u = self.underlyings

        def rho(a: str, b: str) -> float:
            if a == b:
                return 1.0
            if isinstance(realized_corr, (int, float)):
                return float(realized_corr)
            pairs = realized_corr or {}
            return pairs.get((a, b), pairs.get((b, a), self.start.corr(a, b)))

        return np.array([[rho(a, b) for b in u] for a in u])

    def _simulate(self, seed: int) -> dict[str, dict[ql.Date, float]]:
        """Settlement of every underlying on every business day of the path."""
        if not self._dates:
            return {u: {} for u in self.underlyings}
        dc = ql.Actual365Fixed()
        t = np.array([dc.yearFraction(self.start.today, d) for d in self._dates])
        w = correlated_brownians(t, self.corr, n_paths=1, seed=seed)[0]  # (dates, underlyings)
        out = {}
        for k, u in enumerate(self.underlyings):
            path = futures_paths(self.start.forward(u), self.realized_vol[u], t, w[:, k])
            out[u] = dict(zip(self._dates, path.tolist()))
        return out
