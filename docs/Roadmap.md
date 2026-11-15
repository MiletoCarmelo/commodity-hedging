# Roadmap

Back to [Home](Home.md)

Where this repo is going. The end goal is a systematic options strategy: rules decide when to
buy or sell the option, and the position is hedged automatically. Getting there in three steps.

## 1. Pricing (done)

- contract, averaging schedule, fixing calendars
- market data snapshot, implied vols, historical correlation
- Bachelier, Kirk, Monte Carlo
- discounting at trade level (pay date, premium style)
- greeks by bump and reprice

## 2. Hedging bot (next)

Sell the APO, hedge it with futures every day until it settles.

- [x] value the trade during the averaging month (known fixings, adjusted strike)
- [x] portfolio file (YAML) loaded into validated trades
- [x] simulated market source: one GBM path, realised vol and correlation apart from implied
- [x] daily loop: move the date, update the market, reprice, rebalance the hedge in lots
- [x] transaction costs and lot rounding
- [x] P&L explain: delta, gamma, theta, vega, unexplained
- [x] compare hedge frequency and model (Bachelier vs Kirk deltas)
- [ ] round the hedge in crack lots, then hedge the outright residual: rounding each leg on its
      own can leave a whole lot of flat price exposure (see notebook 03)

## 2b. Multi-leg spreads (extension)

- [x] legs as a list with signed weights, e.g. 3-2-1 crack: 2/3 RBOB + 1/3 HO - WTI
- [x] Bachelier with the full covariance matrix (w' Σ w), Monte Carlo in N dims
- [ ] Kirk is two assets only: try QuantLib basket engines (Deng-Li-Zhou, Choi)

## 2c. Futures curve and roll (extension)

The bot first runs with one forward per underlying. Real hedges sit in a given contract month.

- [ ] product specs in a `products.yaml`: exchange, lot size, unit, expiry rule (Brent M-2,
      HO M-1, WTI around the 20th), expiry dates derived from the rule and the calendar
- [ ] each leg says which contract it averages, e.g. `nearby: 1`
- [ ] MarketData holds a futures curve (one forward and vol per contract month)
- [ ] vol surface: contract month x strike instead of one vol per underlying
- [ ] simulation moves the whole curve
- [ ] hedge aggregated by contract month, rolled N days before expiry (bot setting)

## 3. Systematic strategy (later)

Turn the hedging bot into the execution engine of a rules-based strategy, for example trading
implied against realised volatility. Needs market option prices for the implied side.
