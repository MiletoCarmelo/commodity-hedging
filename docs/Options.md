# Options: which position for which exposure

Back to [Home](Home.md)

The building blocks behind every options strategy. Notebook 07 shows each of them with the
pricer's own greeks.

## Two rules

**1. Buying or selling sets gamma, vega and theta.**

| | gamma | vega | theta |
|---|---|---|---|
| **Buy** an option (call or put) | + | + | − |
| **Sell** an option (call or put) | − | − | + |

Buying an option: you gain if the price moves a lot or the vol rises, and you pay for time.
Selling: you collect time decay, and lose when the market moves or vol rises.

**2. Call or put sets the sign of the delta.**

| | delta |
|---|---|
| Long call | + (between 0 and 1) |
| Long put | − (between −1 and 0) |
| Short call | − |
| Short put | + |

## I want … → I do …

| I want | I do |
|---|---|
| Long delta, no gamma | Buy a **future** |
| Long delta + long gamma | **Buy a call** |
| Short delta + long gamma | **Buy a put** |
| Long delta + short gamma | **Sell a put** |
| Short delta + short gamma | **Sell a call** |
| Long gamma, no direction | **Buy a straddle** (ATM call + put), or buy an option and delta-hedge it |
| Short gamma, collect time decay | **Sell a straddle** or a **strangle** |
| Long vega | Buy options, preferably **longer-dated** (vega grows with maturity) |

The trick: **gamma only depends on buying or selling**. Then **call or put** gives the delta.

## Hedging the greeks

| Greek to neutralise | With | Why |
|---|---|---|
| Delta | **Futures** | linear: delta 1, gamma 0, vega 0 |
| Gamma | **Options** | only options have curvature |
| Vega | **Options**, often a different maturity | only options depend on vol |
| Theta | not hedged on its own | comes with gamma: long gamma pays theta |

Order: **first gamma and vega with options, then clean the delta with futures**, since
futures do not touch gamma or vega. To hedge gamma and vega together, use two options (two
maturities) and solve a 2 × 2 system.

Example: the book has gamma +0.4 per $, an ATM option has gamma 0.1 → **sell 4 options**.
That also lowers vega, raises theta and moves the delta, which the futures then reset to zero.

## Strategies are combinations

Add up the greeks of the building blocks:

| Strategy | Built from | View |
|---|---|---|
| Straddle (long) | buy call K + buy put K | big move, either side; vol up |
| Strangle (long) | buy call K2 + buy put K1 (K1 < K2) | same, cheaper, needs a bigger move |
| Bull call spread | buy call K1, sell call K2 | moderate rise, capped gain |
| Bear put spread | buy put K2, sell put K1 | moderate fall, capped gain |
| Butterfly | +1 call K1, −2 calls K2, +1 call K3 | price stays near K2; vol down |
| Risk reversal | buy call K2, sell put K1 | bullish, little premium; trades the skew |

In oil, the same building blocks apply to spreads: an option on a crack or a calendar spread
is the underlying, the strategy is the combination.
