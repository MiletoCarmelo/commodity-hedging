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

## I have … → to hedge it, I do …

To **hedge**, take the **opposite** of what you have. (To take a view, take the same sign: the
table above.)

| I have | To hedge it, I do |
|---|---|
| Long delta (+0.3) | **Sell** futures (−0.3) |
| Short delta (−0.3) | **Buy** futures (+0.3) |
| Long gamma | **Sell** options, then reset the delta with futures |
| Short gamma | **Buy** options, then reset the delta with futures |
| Long vega | **Sell** options, preferably longer-dated |
| Short vega | **Buy** options, preferably longer-dated |
| Theta | not hedged on its own: it goes away with the gamma |

### Delta hedge, by position

Only the **sign of the delta** matters, not call or put. The delta hedge is always futures
(a future has delta 1).

| I have | Possible delta | Example | To hedge it, I do |
|---|---|---|---|
| Long call | 0 to +1 (always +) | +0.3 | **Sell** 0.3 future |
| Long put | −1 to 0 (always −) | −0.3 | **Buy** 0.3 future |
| Short call | −1 to 0 (always −) | −0.3 | **Buy** 0.3 future |
| Short put | 0 to +1 (always +) | +0.3 | **Sell** 0.3 future |

On 10,000 bbl of options, delta 0.3 means 3,000 bbl of futures. A single option never changes
sign; a book mixing several options (a straddle, say) can.

### Gamma, by position

Gamma = how much the delta moves when the future moves by 1 $. It depends only on **buying or
selling**, not on call or put. A future has gamma 0, so only an option can hedge gamma.

| I have | Gamma | Example | After the delta hedge, the Brent moves | To hedge it, I do |
|---|---|---|---|---|
| Long call | always + | +0.03 | I gain, whatever the direction | **Sell** an option |
| Long put | always + | +0.03 | I gain, whatever the direction | **Sell** an option |
| Short call | always − | −0.03 | I lose, whatever the direction | **Buy** an option |
| Short put | always − | −0.03 | I lose, whatever the direction | **Buy** an option |

Example: long call, delta +0.3, gamma +0.03, hedged with −0.3 future (K=83, F=75, σ=32%, 3m).

| Brent move | Start delta | Gamma | Delta change = gamma × move | New call delta | Future | Total delta | To re-hedge |
|---|---|---|---|---|---|---|---|
| +5 $ (75 → 80) | +0.3 | +0.03 | +0.03 × 5 = **+0.15** | ≈ 0.44 | −0.3 | **+0.14** | sell 0.14 future: **sell high** |
| −5 $ (75 → 70) | +0.3 | +0.03 | +0.03 × (−5) = **−0.15** | ≈ 0.16 | −0.3 | **−0.14** | buy 0.14 future: **buy low** |

(0.15 vs 0.14: gamma itself moves a bit along the way; exact values from QuantLib.)

Long gamma re-hedges by selling high and buying low, so it gains. Short gamma does the opposite
(buys high, sells low) and loses. On 10,000 bbl, re-hedging 0.14 means 1,400 bbl of futures.

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
