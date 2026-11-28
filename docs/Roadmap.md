# Roadmap

Back to [Home](Home.md)

Where this repo is going: price the book, hedge it, measure its risk, then extend the market
model to a full futures curve. The end goal is a systematic options strategy, where rules decide
when to buy or sell the option and the position is hedged automatically.

## 1. Pricing (done)

- contract, averaging schedule, fixing calendars
- market data snapshot, implied vols, historical correlation
- Bachelier, Kirk, Monte Carlo
- discounting at trade level (pay date, premium style)
- greeks by bump and reprice

## 2. Hedging bot (done)

Sell the APO, hedge it with futures every day until it settles.

- [x] value the trade during the averaging month (known fixings, adjusted strike)
- [x] portfolio file (YAML) loaded into validated trades
- [x] simulated market source: one GBM path, realised vol and correlation apart from implied
- [x] daily loop: move the date, update the market, reprice, rebalance the hedge in lots
- [x] transaction costs and lot rounding
- [x] P&L explain: delta, gamma, theta, vega, unexplained
- [x] compare hedge frequency and model (Bachelier vs Kirk deltas)
- [ ] round the hedge in crack lots, then hedge the outright residual: rounding each leg on its
      own can leave a whole lot of flat price exposure (see notebook 04)

## 2b. Multi-leg spreads (extension)

- [x] legs as a list with signed weights, e.g. 3-2-1 crack: 2/3 RBOB + 1/3 HO - WTI
- [x] Bachelier with the full covariance matrix (w' Σ w), Monte Carlo in N dims
- [ ] Kirk is two assets only: try QuantLib basket engines (Deng-Li-Zhou, Choi)

## 3. Market risk: VaR (next)

What a risk desk computes every day on the book: how much can it lose, and does the model hold.

- [x] Monte Carlo VaR and ES of the unhedged book: correlated scenarios (Cholesky), full
      revaluation, trade contributions, delta / delta-gamma / parametric vs full, 1 vs 10 days
      (notebook 05)
- [x] VaR of the hedged book: the futures held by the bot, and what is left once the delta is
      covered: lot rounding and gamma on the spread; delta-normal blind to it, square-root rule
      broken (notebook 06). The basis between contract months needs the curve
- [ ] historical VaR: replay the last 250 real daily moves (Yahoo) instead of normal shocks,
      compared with the Monte Carlo VaR
- [ ] backtesting: count the days the loss beat the VaR, Kupiec test, Basel traffic-light zones
- [ ] stress tests: historical scenarios (April 2020 negative WTI, March 2022, Covid) and
      hypothetical ones (Brent −30%, crack +50%, vols +10 points)
- [ ] limits: VaR, delta and vega per underlying, with breaches flagged
- [ ] vols as risk factors, so that the vega shows up in the VaR
- [ ] daily risk report: P&L and explain, VaR and ES, limit usage, stress results on one page
      (extends `daily_report`)

## 4. Options strategies and greek hedging (next)

Why a desk takes a given options position, and how it hedges more than the delta.
Cheat sheet: [Options](Options.md).

- [x] vanilla options on futures (Black-76 with QuantLib), analytic greeks checked against
      bump-and-reprice
- [x] strategy builder: straddle, strangle, call/put spreads, butterfly, risk reversal
- [x] notebook: the greeks in pictures and how to hedge them: delta with futures, gamma with options (notebook 07)
- [x] greeks playground: sliders for future price, vol and time on a hedged book, with a P&L explain (notebook 08)
- [x] P&L explain day by day, delta re-hedged daily: gamma against theta, plus vega; realised vs implied vol (notebook 09)
- [ ] market data checks: stale prices, abnormal jumps, consistency between products
- [ ] vol smile: price vanillas with `ql.VanillaOption` + `ql.BlackProcess` +
  `ql.AnalyticEuropeanEngine` on a `ql.BlackVarianceSurface`, so each strike gets its own vol;
  rename `VanillaOption` to `FuturesOption` at the same time (same name as QuantLib's class)
- [x] notebook: strategies, the view each one expresses and its greek profile (notebook 10)
- [ ] notebook: trading vol, a delta-hedged straddle, implied vs realised (gamma scalping)
- [ ] gamma and vega hedging in the bot: options as hedge instruments, then futures for delta
- [ ] VaR and P&L explain with delta-only vs delta + gamma + vega hedging

## 5. Futures curve and roll

The bot first runs with one forward per underlying. Real hedges sit in a given contract month,
and the risk between contract months (calendar spreads, butterflies) needs a curve to move.

- [x] futures specs in `market/futures.yaml`: exchange, lot size, expiry rule (Brent M-2,
      HO M-1, WTI around the 20th), expiry dates derived from the rule and the calendar
- [x] each fixing uses the front contract of its date (first nearby, the market standard)
- [ ] MarketData holds a futures curve (one forward and vol per contract month)
- [ ] vol surface: contract month x strike instead of one vol per underlying
- [ ] simulation moves the whole curve, so the VaR sees the basis between contract months
- [ ] futures calendar spreads and butterflies (+1 M1 −2 M2 +1 M3) as spread underlyings
- [x] hedge aggregated by contract month, bot settings in `config/hedging.yaml`
- [x] daily report: exposure per contract, trades with their reason, expiries, P&L explain
- [ ] hedge in a chosen month (the most liquid) and roll with calendar spreads before expiry

## 6. Systematic strategy (later)

Turn the hedging bot into the execution engine of a rules-based strategy, for example trading
implied against realised volatility. Needs market option prices for the implied side.
