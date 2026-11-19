# Price dynamics: GBM vs Bachelier

Two ways to say how a futures price moves. Every model in this folder uses one of them,
and so does the simulated market (`market.sources.SimulatedSource`).
How the Monte Carlo runs, step by step: [MONTE_CARLO](MONTE_CARLO.md).

| | Equation | Shocks are in | Price can go negative | Used by |
|---|---|---|---|---|
| Bachelier (arithmetic Brownian motion) | $dF = \sigma_N\, dW$ | $/bbl | yes | `bachelier.py` |
| GBM (geometric Brownian motion) | $dF / F = \sigma\, dW$ | % of the price | no | `montecarlo.py`, `kirk.py` (each leg), `SimulatedSource` |

## The ingredients

**$F$** is the futures price of one delivery month, e.g. Brent Jun-27 at 75 $/bbl.
It is the price agreed today for delivery later, so nobody expects it to drift:
if traders expected it to rise, they would buy it today until it didn't. That is why
there is no $\mu\,dt$ term in either equation.

**$W$** is a standard Brownian motion: the sum of many small independent random shocks.
- $W(0) = 0$
- over a time step $dt$, the shock $dW$ is normal with mean 0 and variance $dt$
- so $W(t) \sim \mathcal{N}(0, t)$: the spread of outcomes grows like $\sqrt{t}$

One trading day is $dt = 1/252$ year, so a daily shock has a standard deviation of
$\sqrt{1/252} \approx 0.063$.

**$\sigma$** scales the shock. Its unit is what differs between the two models:
- Bachelier: $\sigma_N$ in $/bbl per $\sqrt{\text{year}}$ (the "normal vol")
- GBM: $\sigma$ in % per $\sqrt{\text{year}}$ (the "lognormal" or Black vol, the one quoted on screens)

## Bachelier: $dF = \sigma_N\, dW$

Each day the price moves by $\sigma_N\, dW$ dollars, whatever its level.

**Example.** Brent at 75, $\sigma_N = 24$ $/bbl/yr.
- one day: std $= 24 \times 0.063 = 1.51$ $/bbl
- if Brent falls to 40, the daily std is still 1.51 $
- after one year: $F_T = 75 + 24\,W_T$, normal. 90% of outcomes between
  $75 \pm 1.645 \times 24$, i.e. **35.5 to 114.5**, symmetric around 75

**Why the option formula is simple.** Since $F_T$ is normal with mean $F$ and std
$s = \sigma_N\sqrt{T}$, the expected call payoff is an integral over a normal density:

$$
E[(F_T - K)^+] = (F - K)\,N(d) + s\,n(d),
\qquad
d = \frac{F - K}{s}
$$

with $N$ the normal cdf and $n$ its density. At the money ($F = K$) it reduces to
$s \times 0.399$. That is the Bachelier formula in [Math](../../../docs/Math.md#bachelier).

The name comes from Louis Bachelier, who modelled Paris bond prices this way in his 1900
thesis *Théorie de la spéculation*, the first option pricing model.

## GBM: $dF / F = \sigma\, dW$

Each day the price moves by $\sigma\, dW$ **percent**. In dollars the move is
$\sigma F\, dW$: big when the price is high, small when it is low.

**Example.** Brent at 75, $\sigma = 32\%$.
- one day: std $= 0.32 \times 0.063 = 2.0\%$, i.e. **1.51 $** (same as above: $0.32 \times 75 = 24$)
- if Brent falls to 40, the daily std is 2.0% of 40 = **0.81 $**
- after one year: $F_T = 75\,\exp(-\tfrac12\sigma^2 T + \sigma W_T)$, lognormal. 90% of
  outcomes between **42.1 and 120.6**: the upside is longer than the downside, and the
  price never reaches zero

The $-\tfrac12\sigma^2 T$ term keeps the *mean* at 75. The *median* is lower,
$75\,e^{-\sigma^2 T/2} \approx 71.3$: most paths end a bit below 75, a few end very high.
That is the gap between the two lines in notebook 04's fan chart.

The option formula is Black-76 (see [Math](../../../docs/Math.md#black-76-and-implied-vol)).
It needs $\ln(F/K)$, so **both $F$ and $K$ must be positive**.

## Same vol today, different tomorrow

The two models agree today when $\sigma_N = \sigma F$. This is the conversion used in
`market.vol.spread_vol`: $v_i = \sigma_i F_i$. They disagree once the price moves:

| Brent | GBM 32% daily move | Bachelier 24 $ daily move |
|---|---|---|
| 120 | 2.42 $ | 1.51 $ |
| 75 | 1.51 $ | 1.51 $ |
| 40 | 0.81 $ | 1.51 $ |

Outright prices behave more like GBM: a 100 $ barrel moves more in dollars than a 40 $ one.

## Why Bachelier fits spreads

A spread is a difference of prices, e.g. the crack $S = F_{HO} - F_{Brent}$ or
the location spread $S = F_{WTI} - F_{Brent}$.

**1. A spread can be negative.** In the example book WTI−Brent trades around −4 $/bbl and
APO-002 has a strike of −4. Black-76 would need $\ln(-4 / -4)$: it has no answer.
Bachelier only needs $F - K = 0$, which is fine.

**2. A difference of normals is normal.** If each leg moves in dollars,

$$
dS = dF_1 - dF_2 = v_1\,dW_1 - v_2\,dW_2
$$

and $S$ is itself a Bachelier process with

$$
\sigma_N = \sqrt{v_1^2 + v_2^2 - 2\rho\, v_1 v_2}
$$

So one formula prices the whole spread, exactly. A difference of two lognormals has no
closed form: that is why Kirk is an approximation and Monte Carlo exists.

**3. The spread's dollar vol is fairly stable.** Desks quote and think about a crack in
$/bbl, and its move does not scale with its level (a crack at 5 $ does not move ten times
less than at 50 $).

**Examples with the book's numbers** ($v_i = \sigma_i F_i$):
- HO−Brent: $v_{HO} = 0.30 \times 105 = 31.5$, $v_{B} = 24$, $\rho = 0.95$ → $\sigma_N = 11.5$ $/bbl/yr
- WTI−Brent: $v_{WTI} \approx 0.33 \times 71.5 = 23.6$, $v_B = 24$, $\rho = 0.97$ → $\sigma_N \approx 5.9$ $/bbl/yr.
  High correlation makes the spread much quieter than either leg.

When outright prices themselves went below zero (WTI May-20 settled at −37 $ on 20 April 2020),
CME moved its crude option settlement to Bachelier for the same reason.

## Where each one is used here

- `bachelier.py`: the basket $\sum_k w_k F_k$ is one normal process. Fast, works with any
  sign. Approximation: $v_i = \sigma_i F_i$ is frozen at today's prices.
- `kirk.py`: each leg is lognormal, the spread is approximated with Black on
  $F_1 / (F_2 + K)$. Falls back to Bachelier when $F_2 + K \le 0$.
- `montecarlo.py` and `SimulatedSource`: each leg is a GBM, correlated. The spread is
  whatever the difference gives, no formula needed.

## What neither captures

Both use a constant vol and normal shocks: no jumps, no fat tails, no smile, no mean
reversion. Real crack spreads spike (refinery outages, hurricanes) more often than a
normal distribution allows. See Limitations in [Study](../../../docs/Study.md#limitations).
