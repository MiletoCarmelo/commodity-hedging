# portfolio

Back to [Home](../Home.md)

What we hold, read from a YAML file. Example: `portfolios/example_book.yaml`.

```yaml
portfolio: example-book
trades:
  - id: APO-001                 # outright: one leg, weight 1 by default
    type: apo
    quantity: 20000             # bbl, positive = bought
    legs:
      - underlying: BRENT
    strike: 72.0
    option_type: put
    schedule:
      pricing_period: 2027-01
      calendar: [ICE-EU]
      pay_lag: 5

  - id: APO-003                 # crack: two legs
    type: apo
    quantity: -25000            # negative = sold
    legs:
      - underlying: HO
        weight: 1
      - underlying: BRENT
        weight: -1
    strike: 32.0
    option_type: call
    premium_style: upfront
    schedule:
      pricing_period: 2027-06
      calendar: [NYMEX, ICE-EU]
      pay_lag: 5
```

The file holds a third trade, APO-002, a WTI - Brent spread put. Brent is in all three, which
is what makes netting at book level worth it.

- `load_portfolio(path)`: reads the file, returns a `Portfolio`
- `Portfolio`: name and trades, ids must be unique. Iterate over it, or `trade("APO-001")`
- `Trade`: `id` and `instrument` (an `APO` for now)
- `TRADE_TYPES`: `type` in the file -> builder. A new product is one more builder here

Checked at load time, with the trade id in the error:

- unknown `type`, unknown field (a typo like `strik` is an error, not ignored)
- calendar codes: unknown exchange, empty list, the same exchange twice (`NYMEX` and
  `XNYM` count as the same)
- everything the instrument already checks: legs, weights, quantity, pricing month

The model is not in the file. Kirk refusing three legs happens when the trade is priced.
