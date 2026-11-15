"""Realised vols and correlation from daily futures closes, roll jumps removed."""

from __future__ import annotations

from dataclasses import dataclass

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
    """Estimated vols and correlation, with the dates removed as jumps."""

    vols: dict[str, float]  # annualised realised lognormal vols
    rho: float  # correlation of daily log-returns
    rolling_rho: pd.Series  # for stability diagnostics
    n_obs: int
    flagged_dates: list

    def __str__(self) -> str:
        vols = " | ".join(f"{k} {v:.1%}" for k, v in self.vols.items())
        return (
            f"realised vols: {vols} | rho {self.rho:.3f} "
            f"(rolling min {self.rolling_rho.min():.2f} / max {self.rolling_rho.max():.2f}) "
            f"| {self.n_obs} obs, {len(self.flagged_dates)} jump(s) removed"
        )


def estimate_market_params(
    prices: pd.DataFrame, window: int = 60, jump_threshold: float | None = 5.0
) -> MarketParams:
    """Vols and correlation of two price columns (same units), jumps removed first."""
    if prices.shape[1] != 2:
        raise ValueError("expected exactly two price columns")
    rets = log_returns(prices)
    flagged = flag_jumps(rets, jump_threshold) if jump_threshold else pd.Series(False, rets.index)
    clean = rets[~flagged]
    a, b = clean.columns
    return MarketParams(
        vols={c: float(clean[c].std(ddof=1) * np.sqrt(TRADING_DAYS)) for c in clean.columns},
        rho=float(clean[a].corr(clean[b])),
        rolling_rho=clean[a].rolling(window).corr(clean[b]).dropna(),
        n_obs=len(clean),
        flagged_dates=list(rets.index[flagged]),
    )
