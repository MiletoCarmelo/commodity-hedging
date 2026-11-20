"""Realised vols and correlation from daily futures closes, roll jumps removed."""

from __future__ import annotations

from dataclasses import dataclass
from itertools import combinations

import numpy as np
import pandas as pd

TRADING_DAYS = 252

# =============================================================================
# 1. Returns and jump detection
# =============================================================================


def log_returns(prices: pd.DataFrame) -> pd.DataFrame:
    """Daily log-returns of each price column."""
    return np.log(prices).diff().dropna()


def flag_jumps(returns: pd.DataFrame, threshold: float = 5.0) -> pd.Series:
    """True on dates where any column has |robust z-score| > threshold (roll jumps)."""
    median = returns.median()
    mad = (returns - median).abs().median() * 1.4826  # MAD -> sigma for a normal
    z = (returns - median) / mad
    return (z.abs() > threshold).any(axis=1)


# =============================================================================
# 2. Market parameters
# =============================================================================


@dataclass(frozen=True)
class MarketParams:
    """Estimated vols and correlations, with the dates removed as jumps.

    `correlations` uses the same format as `MarketData.correlations`, so it can be passed
    straight to the market: `MarketData(..., correlations=params.correlations)`.
    """

    vols: dict[str, float]  # annualised realised lognormal vols
    correlations: dict[tuple[str, str], float]  # correlation of daily log-returns, per pair
    rolling_correlations: dict[tuple[str, str], pd.Series]  # for stability diagnostics
    n_obs: int
    flagged_dates: list

    def corr(self, a: str, b: str) -> float:
        """Correlation between two columns, in either order."""
        if a == b:
            return 1.0
        if (a, b) in self.correlations:
            return self.correlations[(a, b)]
        return self.correlations[(b, a)]

    def __str__(self) -> str:
        vols = " | ".join(f"{k} {v:.1%}" for k, v in self.vols.items())
        corrs = " | ".join(
            f"{a}-{b} {rho:.3f} (rolling {self.rolling_correlations[(a, b)].min():.2f}"
            f" to {self.rolling_correlations[(a, b)].max():.2f})"
            for (a, b), rho in self.correlations.items()
        )
        return (
            f"realised vols: {vols} | correlations: {corrs} "
            f"| {self.n_obs} obs, {len(self.flagged_dates)} jump(s) removed"
        )


def estimate_market_params(
    prices: pd.DataFrame, window: int = 60, jump_threshold: float | None = 5.0
) -> MarketParams:
    """Vols and pairwise correlations of the price columns (same units), jumps removed first."""
    if prices.shape[1] < 2:
        raise ValueError("expected at least two price columns")
    rets = log_returns(prices)
    flagged = flag_jumps(rets, jump_threshold) if jump_threshold else pd.Series(False, rets.index)
    clean = rets[~flagged]
    pairs = list(combinations(clean.columns, 2))
    return MarketParams(
        vols={c: float(clean[c].std(ddof=1) * np.sqrt(TRADING_DAYS)) for c in clean.columns},
        correlations={(a, b): float(clean[a].corr(clean[b])) for a, b in pairs},
        rolling_correlations={(a, b): clean[a].rolling(window).corr(clean[b]).dropna()
                              for a, b in pairs},
        n_obs=len(clean),
        flagged_dates=list(rets.index[flagged]),
    )
