# hedging

Back to [Home](../Home.md)

![hedging](../img/map_bot.png)

The bot: delta hedge the portfolio with futures, contract month by contract month, once per
business day, and book the P&L. Backtest mode for now, on a [simulated market](market.md#sourcespy).
A daily report shows what it did and why, like the screen a trader reads every morning.

```python
book = load_portfolio("portfolios/example_book.yaml")
source = SimulatedSource(market, end, any_exchange_calendar(["NYMEX", "ICE-EU"]), seed=7)
settings = load_hedge_settings("config/hedging.yaml")
result = HedgingBot(book, source, settings).run()
result.to_frame()                      # one row per day
print(daily_report(result, date))      # the morning screen of one day
```

## One day, end of day

1. take the market snapshot of the date
2. price every trade, split each delta over the futures contracts its remaining fixings use,
   add them up per (underlying, contract month): this is the netting
3. P&L since yesterday, with yesterday's futures:
   - option: change in PV, plus the cash if a trade paid today
   - hedge: lots x lot size x change in the futures price (variation margin)
4. new position = each contract's delta turned into lots with the opposite sign, rounded
5. cost = lots traded x cost per lot of that future

No explicit roll: a contract's hedge covers only the fixings that use it, so it fades to zero
by the contract's expiry while the next month carries the rest. A desk rolls when it hedges
in another month than the exposure (e.g. all in the most liquid one).

## settings.py

- `HedgeSettings`: `model`, `rebalance_every` (days), `explain`, and `instruments`: the futures
  the bot may trade with their cost per lot. Desk choices, so they live here and not in the
  portfolio file. Contract specs (lot size, expiry rule) come from `market/futures.yaml`.
  A book with an underlying that has no instrument is refused at start.
- `load_hedge_settings(path)`: reads `config/hedging.yaml`

## engine.py

- `target_lots(deltas, lot_size)`: futures that cancel the deltas, per contract, the only
  decision of the bot
- `trade_reasons(before, after)`: open, close or adjust, for each contract traded
- `HedgingBot(portfolio, source, settings).run()`: the loop above, returns a `HedgeRun`.
  It reads the book risk from [risk/book.py](risk.md#bookpy) and decides what to trade
- `Day`: everything about one date (forwards, PV, deltas, position, trades, P&L lines)
- `HedgeRun`: the list of days, `total_pnl`, `cumulative_pnl()`, `to_frame()`

## report.py

- `ladder(day)`: exposure per contract, in bbl: options, futures held, net, lots traded, reason
- `expiring(day, within=5)`: contracts held that stop trading soon
- `pnl_lines(day)`: options, futures, costs, and the explain
- `daily_report(run, date)`: all of the above as text

## explain.py

The option P&L of each day, split with yesterday's greeks:

dV ~ delta dF + 1/2 gamma dF² + theta dt + vega dvol, plus the payoff when it is paid.

- gamma is a matrix: HO, Brent and the HO x Brent cross term (`cross_gamma` in risk)
- theta is yesterday's market moved to today's date, nothing else changed
- `unexplained` is what is left, around 1 to 2% of the daily moves. It grows when an option
  is at the money close to the end of its month: gamma itself moves a lot within a day
- `HedgeSettings(explain=False)` skips it, about 3x faster for many-path studies

Read with the hedge: delta of the option + futures P&L is close to 0, so the hedged P&L is
mostly gamma against theta. That is the volatility bet of a hedged option.

## What the tests check

- the hedge of a sold crack call is long HO, short Brent
- Brent is netted across the three trades of the example book
- P&L bookkeeping: hedge P&L is exactly lots x size x price change, costs per lot
- summed option P&L = payoff paid - premium received
- sold option, realised vol below implied: the hedged book makes money on average, above: it
  loses. The hedge removes the direction, what is left is the volatility bet
- the hedge cuts the P&L dispersion by more than half
- explain lines add up to the option P&L, unexplained under 2% of the moves
