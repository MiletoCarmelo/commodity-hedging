# risk

Back to [Home](../Home.md)

Bump the market, reprice, take the difference. Formulas in [Math](../Math.md#greeks).

## greeks.py

1. `Greeks`: result object for a two-leg spread, `to_dict()` for a table.
2. `GreekCalculator(pricer, instrument)`: generic, works per underlying name, any number of legs.
   - `deltas()`: delta of every leg as a dict, what the hedging bot nets
   - `delta(u)`, `gamma(u)`, `vega(u)`, `theta(days=1)`, `theta_to(date)`, `rho()`
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

## book.py

The same greeks for a whole portfolio. Nothing is repriced here that `greeks.py` does not
already do: each trade's greeks are multiplied by its signed quantity and added up per
underlying.

- `trade_pv`, `trade_deltas`: one trade, signed by its quantity, 0 once paid
- `paid_cash`: payoff received when a trade passes its pay date
- `book_risk(portfolio, pricer)`: PV and deltas of the whole book, netted per underlying
- `book_greeks`, `book_theta`: gammas (with cross terms), vegas and theta of the book, used by
  the P&L explain. Here the units are $ and bbl: per bbl times the quantity
