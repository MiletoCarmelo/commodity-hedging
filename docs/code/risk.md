# risk

Back to [Home](../Home.md)

Bump the market, reprice, take the difference. Formulas in [Math](../Math.md#greeks).

## greeks.py

1. `Greeks`: result object for a two-leg spread, `to_dict()` for a table.
2. `GreekCalculator(pricer, instrument)`: generic, works per underlying name, any number of legs.
   - `deltas()`: delta of every leg as a dict, what the hedging bot nets
   - `delta(u)`, `gamma(u)`, `vega(u)`, `theta(days=1)`, `rho()`
   - `cross_gamma(a, b)`: how the delta of `a` moves when `b` moves
   - `forward_pricer`: the pricer used when forwards move, subclasses can change it
3. `SpreadGreekCalculator`: two legs only, inherits all of the above and adds
   - `delta_legs`, `gamma_legs`, `vega_legs`: the generic greeks on both legs
   - `delta_crack`: leg 1 +0.5 $, leg 2 -0.5 $
   - `delta_outright`: both legs +1 $, the flat price risk left after a crack hedge
   - `gamma_crack`, `corr_sens`
   - `all()`: everything in one `Greeks`
   - for Bachelier, the $ normal vol is frozen during forward bumps

Units: per bbl, vega per vol point, correlation per +0.01, theta per calendar day, rho per bp.
