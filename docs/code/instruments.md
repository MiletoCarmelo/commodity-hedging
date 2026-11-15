# instruments

Back to [Home](../Home.md)

The contract only: what is traded. No prices, no model.

## leg.py

- `Leg("HO", 1)`: one leg, the name of the underlying and its weight. The name is the key
  used to look up the forward and vol in `MarketData`. Positive weight = long, negative =
  short, 0 is refused. The weight defaults to 1, so `Leg("BRENT")` alone is an outright.

## schedule.py

- `AveragingSchedule`: pricing month (`"2027-03"`), fixing calendar, payment lag in business
  days, day counter. Reused by any averaging product (APO, average price swap).
  - `fixing_dates()`: business days of the calendar inside the pricing month
  - `past_fixings(today)`: already published, strictly before today
  - `future_fixings(today)`: still to come, today included
  - `fixing_times(today)`: future fixings as year fractions from today
  - `t_eff(today)`: effective time of the remaining average, see
    [Math](../Math.md#effective-time-of-the-average). 0 once everything is fixed.
  - `pay_date`: last fixing + `pay_lag` business days. Computed, so it can never fall before
    the end of the period.

## types.py

- `OptionType`: `"call"` or `"put"`, anything else is rejected.
  - `.ql`: the QuantLib constant
  - `.sign`: +1 / -1, used in the payoff

## apo.py

- `APO`: legs, strike, option type, quantity (negative = sold), schedule, premium style
  (`"upfront"` or `"futures_style"`). Same underlying twice and a zero quantity are refused.
  - `underlyings`, `weights`: read from the legs
  - `combine(prices)`: sum of weight x price, the number that gets averaged
  - `phi`: payoff sign, same as `option_type.sign`

One class for every shape:

| Trade | legs |
|---|---|
| Brent outright APO | `[Leg("BRENT")]` |
| HO–Brent crack | `[Leg("HO", 1), Leg("BRENT", -1)]` |
| 3-2-1 crack, per bbl of crude | `[Leg("RBOB", 2/3), Leg("HO", 1/3), Leg("WTI", -1)]` |

Kirk only prices two legs of opposite sign, Bachelier and Monte Carlo take any number.

APOs are European. The payoff needs the whole month average, so nothing can be exercised
early: it's auto-exercised at the end and paid in cash. If you want out before, you unwind
it at its PV, which is what `Pricer.pv` gives at any date.
