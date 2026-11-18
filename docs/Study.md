# Study: goals, hypotheses, results, limits

Back to [Home](Home.md)

The project is set up like an experiment: what we wanted to learn, what we expected, what came out,
what got in the way, and what the setup cannot say.

## Goals

1. Price a commodity spread APO (HO - Brent crack) the way a desk would: before and during
   the averaging month, with exchange calendars and payment terms.
2. Measure its risk: deltas per leg, gamma, vega, correlation, theta, rho.
3. Hedge a small book of APOs with futures every day, and explain the P&L line by line.
4. Keep trade, market and model apart, so the same loop can later run on historical or live data.

## Data flow: where the numbers come from

| Step | Input | Computation |
|---|---|---|
| Trades | `portfolios/example_book.yaml` | validated APOs: weighted legs, strike, pricing month, calendar, pay lag |
| Forwards | fixed snapshot, or Yahoo dated contracts (notebook 02) | one forward per underlying |
| Implied vols | ATM option premiums | Black-76 inverted (`blackFormulaImpliedStdDev`) |
| Correlation | Yahoo history | log-returns, roll jumps removed (robust z-score) |
| Fixings | published settlements | average so far, adjusted strike K* for the rest |
| Price | model + market snapshot | expected payoff on the remaining fixings x DF to the pay date |
| Greeks | the same trade, bumped market | central differences, model kept fixed |
| Hedge | one end-of-day snapshot per day | deltas split by futures contract, netted, rounded to lots |
| P&L | yesterday vs today | options (MTM + payoffs), futures (variation margin), costs, explain by greek |

## Hypotheses and results

| # | Hypothesis | Result |
|---|---|---|
| H1 | Kirk with the effective time of the average is close to a Monte Carlo on the real fixing dates | yes: within ~0.02 $/bbl (< 1%) |
| H2 | Normal vs lognormal view of the crack is a real model risk | yes: Bachelier 2.52 vs Kirk 2.62 $/bbl, ~2 500 $ on the trade |
| H3 | Lognormal deltas of a spread are not symmetric | yes: delta HO + delta Brent = +0.017, ~430 bbl of outright risk a single crack delta misses |
| H4 | Correlation is the input that matters most | yes: -0.18 $/bbl per +0.01 of correlation, and it has no liquid market |
| H5 | During the month the option is an APO on the remaining fixings, strike K*, weighted (n-m)/n | yes: matches the Monte Carlo, delta goes to 0 on the last fixing |
| H6 | A hedged short option earns about 1/2 gamma F^2 (implied^2 - realised^2): a bet on volatility | yes: realised at 60% of implied +30 k$, 100% ~0, 140% -35 k$ (40 paths) |
| H7 | Hedging more often reduces the P&L dispersion | yes: daily 9.5 k$, weekly 16.0 k$ of std |
| H8 | A Taylor explain (delta, gamma with cross term, theta, vega) explains the daily P&L | mostly: unexplained < 2% of daily moves, larger for at-the-money options near the end of their month |
| H9 | Netting by underlying is enough | no: Brent nets to -4.7 k bbl overall but -7.0 / -7.6 / +10.0 k bbl by contract month, a calendar spread risk that only per-contract hedging shows |

## Problems met

Each one in detail (symptom, how it was found, cause, fix, lesson) in [Findings](Findings.md).

- QuantLib has no spread option class: `BasketOption` + `SpreadBasketPayoff` + `KirkEngine`.
- `KirkEngine` discounts to expiry, the APO pays later: engine at zero rate, separate discount
  to the pay date (upfront) or none (futures-style).
- Kirk breaks when F2 + K* <= 0 (deep in the money late in the month): falls back to Bachelier.
- Bachelier deltas came out asymmetric under bumps: the $ normal vol has to stay frozen.
- QuantLib has no commodity exchange calendars: ICE built from `holidays` (Brent settles on
  Easter Monday), NYMEX from NYSE; 18 June 2027 (Juneteenth) is out of the common days.
- The explain revealed a bug: at end of day today's settlement is already a fixing, so it no
  longer moves the delta (about 1/n of the position).
- Rounding each leg to whole lots can leave a full lot of outright exposure when the two deltas differ.
- Speed: fixing dates and calendars were rebuilt every call; cached, a backtest runs in ~2 s.

## Limitations

- One forward per underlying: all contract months move together, no curve shape, no time-spread P&L.
- Flat implied vols, no smile, no vol dynamics: vega P&L is zero in the backtest.
- Constant correlation and discount rate.
- Simulated market: correlated driftless GBM, no jumps, fat tails or mean reversion.
- Not yet run on historical data; no VaR, stress tests or risk limits in the bot.
- Full delta hedge every day at settlement prices, flat cost per lot, no slippage or liquidity.
- Exchange calendars approximated; no credit, CVA or FX.
- Kirk prices two legs only; multi-leg spreads use Bachelier or Monte Carlo.

## Next

See the [Roadmap](Roadmap.md): futures curve and roll, historical data, then VaR, stress tests
and limits on the same book.
