# Findings log

Back to [Home](Home.md)

What the project taught us along the way: bugs found, wrong assumptions, effects that only
show up once the numbers are checked. One entry each: symptom, how it was found, cause, fix,
lesson. Newest first.

## Why a P&L explain

A desk splits its daily P&L by risk factor: delta, gamma, theta, vega, and what is left
(unexplained). It is standard practice for two reasons:

- it tells traders and management where the money came from
- it checks the risk numbers: if the greeks are right, the unexplained stays small. A large or
  persistent unexplained means a wrong greek or a missing risk factor

Here it was built for the first reason and paid off through the second (finding 1).

---

## 1. Today's fixing counted twice in the delta

- **Symptom**: during the averaging month the explain left an unexplained P&L every day, with
  the sign of the move in the crack.
- **Found by**: the P&L explain.
- **Cause**: the bot runs at end of day, when today's settlement is already published. The
  model still treated today's fixing as a future one, so a forward bump also moved a price
  that was already fixed. The delta was too large by about 1/n of the position.
- **Fix**: today counts as fixed as soon as the market holds today's settlement for every leg
  (`today_fixed` in the averaging state). Same price, smaller delta.
- **Lesson**: the time of day of a snapshot is part of the data. An explain catches it, a
  pricing test does not, because the price itself was right.

## 2. Netting by underlying hid a calendar spread risk

- **Symptom**: the Brent delta of the example book netted to -4.7 k bbl, a small hedge.
- **Found by**: splitting each delta by the futures contract its fixings use.
- **Cause**: the three trades fix on different Brent contracts (March, June, August). By
  contract month the exposures are -7.0, -7.6 and +10.0 k bbl and do not offset.
- **Fix**: deltas split and netted per (underlying, contract month), hedge per contract.
- **Lesson**: a future is an underlying and a delivery month. Netting across months is a bet
  on the time spreads.

## 3. Rounding each leg to whole lots left outright exposure

- **Symptom**: on the sold crack, the hedged P&L dispersion was 9.5 k$ with whole lots and
  6.6 k$ hedging in barrels. On a smaller first version of the trade (10 000 bbl), whole-lot
  Kirk hedging even did worse than Bachelier, although Kirk is the right model for the market.
- **Found by**: comparing hedge settings on the same 40 simulated paths (notebook 04).
- **Cause**: Kirk deltas of a spread are not symmetric. Rounded leg by leg, deltas like
  +10 600 / -10 400 bbl become 11 HO lots against 10 Brent, i.e. 1 000 bbl of flat price risk,
  which moves much more than the crack. Bachelier deltas are symmetric and round the same way.
- **Fix**: not yet; roadmap: round in crack lots first, hedge the outright residual apart.
- **Lesson**: the hedge has to respect the structure of the risk, not only its size.

## 4. Bachelier deltas came out asymmetric

- **Symptom**: delta HO and delta Brent of a Bachelier spread did not cancel, while the model
  only sees the spread.
- **Found by**: a test on the sum of the leg deltas.
- **Cause**: the $ normal vol is built from the legs' lognormal vols times their forwards, so
  bumping a forward also moved the vol.
- **Fix**: keep the $ normal vol fixed during forward bumps (sticky normal vol).
- **Lesson**: a greek depends on what is held fixed when the market moves.

## 5. The simulated market missed settlement days

- **Symptom**: the backtest stopped with a missing Brent fixing on 18 January 2027.
- **Found by**: the error raised when a fixing is not in the market data.
- **Cause**: the simulation stepped on days when both NYMEX and ICE are open. The Brent put
  fixes on ICE days only, and ICE settles on Martin Luther King day.
- **Fix**: simulate on every day either exchange settles (`any_exchange_calendar`).
- **Lesson**: fail loudly on missing data. A silent default would have priced a wrong average.

## 6. QuantLib engines and the APO payment date

- **Symptom**: Kirk prices were discounted to the option expiry, not to the pay date.
- **Found by**: reading `KirkEngine`; the APO pays days after the last fixing.
- **Cause**: QuantLib's European engines discount to the exercise date.
- **Fix**: run the engine at zero rate (undiscounted payoff), then discount separately, to the
  pay date if paid upfront, not at all if margined (futures-style).
- **Lesson**: who pays what and when is a contract term, not a model choice.

## 7. Monte Carlo moved after a refactor

- **Symptom**: the Monte Carlo price changed in the second decimal after rewriting the
  correlated draws.
- **Found by**: comparing outputs before and after the change.
- **Cause**: different random numbers, not a bug: the gap was within the Monte Carlo noise.
- **Fix**: checked over 20 seeds, kept a fixed seed so bumps reuse the same draws.
- **Lesson**: before calling a change a regression, measure the noise.
