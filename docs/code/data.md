# data

Back to [Home](../Home.md)

Optional extra (`pip install -e ".[data]"`). Network needed.

## yahoo.py

1. Helpers: `YahooFinanceError`, `_to_unix`
2. `YahooFinanceClient`: retries on 429 / 5xx, raises instead of returning None.
   - `history(symbol, start, end)`: daily OHLCV
   - `closes({"HO": "HO=F", ...}, start, multipliers={"HO": 42})`: closes on common dates
   - `last_price(symbol)`
   - `futures_ticker("HO", 2027, 4)` -> `"HOJ27.NYM"`
   - `futures_price(root, year, month)`: dated contract, front month if Yahoo does not have
     it (with a warning)

Yahoo has no options on commodity futures, so vols stay inputs.

## estimation.py

1. `log_returns`, `flag_jumps` (roll jumps, see [Math](../Math.md#roll-jumps))
2. `MarketParams` and `estimate_market_params(prices, window=60)`: realised vols, correlation,
   rolling correlation, removed dates.
