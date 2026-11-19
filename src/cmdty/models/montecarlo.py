"""Monte Carlo on the actual fixing dates: one correlated driftless Geometric Brownian Motion (GBM) future per leg."""

import warnings

import numpy as np
import QuantLib as ql

from .averaging import averaging_state, settled_payoff

# =============================================================================
# 1. Pricing
# =============================================================================


def expected_payoff(apo, market, n_paths: int = 200_000, seed: int = 42) -> float:
    """Undiscounted expected payoff of the APO by Monte Carlo."""
    u = apo.underlyings
    state = averaging_state(apo, market)
    if state.done:
        return settled_payoff(apo, state)

    # 1) times of the future fixings, in years from today
    t = apo.schedule.fixing_times(market.today, state.today_fixed)

    # 2) correlated Brownian motions, one value per path and per fixing
    corr = np.array([[market.corr(a, b) for b in u] for a in u])
    w = correlated_brownians(t, corr, n_paths, seed)

    # 3) futures prices of each leg on every fixing date, weighted and summed
    basket = sum(
        leg.weight * futures_paths(market.forward(x), market.vol(x), t, w[..., k])
        for k, (x, leg) in enumerate(zip(u, apo.legs))
    )

    # 4) average = known fixings + simulated ones, payoff per path, mean over paths
    future_sum = basket.sum(axis=1)
    average = (state.m * state.known_average + future_sum) / state.n
    payoffs = np.maximum(apo.phi * (average - apo.strike), 0.0)
    return float(payoffs.mean())


# =============================================================================
# 2. Monte Carlo helpers
# =============================================================================


def cholesky_factor(corr: np.ndarray) -> np.ndarray:
    """Lower factor L with L @ L.T = corr; repairs corr if not positive definite."""
    m = ql.Matrix(np.asarray(corr, dtype=float).tolist())
    try:
        L = ql.pseudoSqrt(m, ql.SalvagingAlgorithm.NoAlgorithm)  # plain Cholesky, lower triangular
    except RuntimeError:
        # not a valid correlation: Higham finds the nearest one (semi-definite), then a
        # square root of it; that factor is no longer triangular, L @ L.T still holds
        warnings.warn("correlation matrix not positive definite, repaired")
        L = ql.pseudoSqrt(m, ql.SalvagingAlgorithm.Higham)
    return np.array([[L[i][j] for j in range(L.columns())] for i in range(L.rows())])


def correlated_brownians(
    t: np.ndarray, corr: np.ndarray, n_paths: int, seed: int
) -> np.ndarray:
    """N correlated Brownian motions sampled at times t. Shape (n_paths, len(t), N)."""
    rng = np.random.default_rng(seed)  # fixed seed: same draws for every bump
    L = cholesky_factor(corr)  # L @ L.T = corr

    # independent N(0,1), one per path, fixing and factor
    z = rng.standard_normal((n_paths, len(t), L.shape[0]))
    x = z @ L.T  # correlated across factors, still N(0,1) each

    dt = np.diff(np.concatenate([[0.0], t]))  # time steps between fixings
    # increment = sqrt(dt) * x; [None, :, None] applies dt along the time axis
    # W(t) = sum of increments up to t, i.e. cumsum over time (axis=1)
    return np.cumsum(x * np.sqrt(dt)[None, :, None], axis=1)


def futures_paths(
    forward: float, vol: float, t: np.ndarray, w: np.ndarray
) -> np.ndarray:
    """Driftless GBM (Black-76): F(t) = F0 * exp(-vol^2 t / 2 + vol W(t))."""
    # the -vol^2 t / 2 term keeps E[F(t)] = F0 (a future has no drift)
    return forward * np.exp(-0.5 * vol**2 * t + vol * w)
