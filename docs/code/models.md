# models

Back to [Home](../Home.md)

Each model has the same signature: `expected_payoff(apo, market, **kwargs)`, undiscounted,
in $/bbl. They are registered by name in `MODELS` (`"bachelier"`, `"kirk"`, `"mc"`).
Formulas in [Math](../Math.md). GBM vs Bachelier, and why Bachelier fits spreads:
[models/README](../../src/cmdty/models/README.md).

## averaging.py

What is already known during the pricing month, shared by the three models.

- `averaging_state(apo, market)` -> `AveragingState(n, m, known_average)`: reads the published
  fixings from the market
  - `weight`: share of the average still to come, (n - m) / n
  - `adjusted_strike(K)`: K* for the future fixings
  - `done`: every fixing known
- `settled_payoff(apo, state)`: payoff once everything is fixed

## bachelier.py

1. `expected_payoff(apo, market, normal_vol=None)`: normal model on the crack, with
   $T_{\text{eff}}$, strike K* and weight during the month. `normal_vol` overrides the vol built from the legs (used by the greeks).
2. `spread_normal_vol(apo, market)`: converts each leg to a $ vol and combines them.

## kirk.py

1. `expected_payoff(apo, market)`: QuantLib `BasketOption` + `SpreadBasketPayoff` +
   `KirkEngine`, European exercise at today + $T_{\text{eff}}$, strike K*.
   Falls back to Bachelier if $F_2 + K^* \le 0$. Runs with a zero rate so the
   result is undiscounted (KirkEngine would otherwise discount to expiry, not to the pay date).
   Two legs of opposite sign only. One leg (an outright APO) goes to `_black_outright`.
2. `_black_outright(...)`: Kirk with no second asset, i.e. Black-76 on the average with
   $T_{\text{eff}}$ and K*.
3. `_black_process(...)`: one leg as a lognormal future, constant vol.

## montecarlo.py

1. `expected_payoff(apo, market, n_paths=200_000, seed=42)`, four steps: future fixing
   times, correlated Brownians, futures paths, average (known + simulated) and payoff.
2. Helpers:
   - `cholesky_factor(corr)`: L with L L^T = corr, repairs the matrix if needed (QuantLib `pseudoSqrt`, Higham)
   - `correlated_brownians(t, corr, n_paths, seed)`: shape (paths, fixings, factors)
   - `futures_paths(forward, vol, t, w)`: driftless GBM

The seed is fixed so a delta reprices up and down on the same draws. Standard error with 200k
paths is about 0.01 $/bbl.
