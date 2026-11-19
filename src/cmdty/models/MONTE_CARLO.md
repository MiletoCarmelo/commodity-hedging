# Monte Carlo: how to use it

How to turn a price dynamic into simulated paths, then into an option price.
For what the two dynamics mean and where they come from, see [README](README.md).

A simulation is not a forecast. It draws many futures that are *possible* under the model
and averages what the option pays in each of them.

## The general frame

Every price model is a **stochastic differential equation (SDE)**:

$$
dF = \mu(F, t)\, dt + \sigma(F, t)\, dW
$$

- $\mu$, the drift: where the price tends to go
- $\sigma$, the diffusion: how much it shakes
- $dW$, the random shock

Choosing a model means choosing $\mu$ and $\sigma$. The Monte Carlo is then always the same:
discretise the SDE, simulate paths, average the payoffs.

| model | $\mu$ | $\sigma(F, t)$ | captures |
|---|---|---|---|
| arithmetic Brownian motion | 0 | $\sigma_N$ | moves in $, negative prices |
| GBM (used here) | 0 | $\sigma F$ | moves in %, positive prices |
| mean reversion (Ornstein-Uhlenbeck, Schwartz) | $\kappa(\theta - F)$ | constant or $\sigma F$ | prices pulled back to a level (spot commodities) |
| local vol (Dupire) | 0 | $\sigma(F, t)$, a known function | the smile |
| stochastic vol (Heston, SABR) | 0 | $\sigma_t$ with its own SDE | vol that moves at random |
| jumps (Merton) | 0 | $\sigma F$ + a jump term | sudden gaps (outages, hurricanes) |

When the SDE has no exact step formula, the generic discretisation is the
**Euler-Maruyama scheme**: $F(t + \Delta t) = F(t) + \mu\,\Delta t + \sigma\sqrt{\Delta t}\, Z$,
with small steps.

GARCH also makes vol move over time, but it is a time-series model fitted on history
(used for VaR), not a pricing SDE.

## Why $\sigma$ is constant here

$\sigma$ is the **implied vol**: the number that, put into Black-76, gives back the option
price quoted by the market today for that maturity. It sums up, in one number, the average
vol the market expects until expiry.

Keeping it constant is the Black-76 assumption. Using the same assumption in the simulation
means the Monte Carlo reprices the market's options correctly. What grows along a path is not
$\sigma$ but the total uncertainty $\sigma\sqrt{t}$: $\sigma$ is a speed, $\sigma\sqrt{t}$
the distance covered.

At each step:

| | changes? |
|---|---|
| $F$ | yes: output of the step, input of the next |
| $Z$ | yes: a new draw |
| $\sigma$ | no: implied vol, fixed |
| $\Delta t$ | no: the step size |

## The recipe

1. **Pick a dynamic**: how the price moves over a tiny time $dt$
2. **Integrate it**: get a formula that moves the price by one step $\Delta t$
3. **Step forward**: from $F(t)$, $\sigma$, $\Delta t$ and a random $Z$, compute $F(t + \Delta t)$
4. **Repeat** up to the last fixing: that is one path
5. **Many paths**: compute the payoff on each, the price is the mean

In both dynamics the shock over a step is

$$
\Delta W = \sqrt{\Delta t}\; Z, \qquad Z \sim \mathcal{N}(0, 1)
$$

## 1–2. Pick a dynamic and integrate it

**Arithmetic Brownian motion**: the shock is in $/bbl.

$$
dF = \sigma_N\, dW
\quad\Longrightarrow\quad
F(t + \Delta t) = F(t) + \sigma_N \sqrt{\Delta t}\; Z
$$

Nothing to do: add up the shocks. Each step **adds** a few dollars. The price can go below zero.

**Geometric Brownian motion (GBM)**: the shock is in % of the price.

$$
\frac{dF}{F} = \sigma\, dW
\quad\Longrightarrow\quad
F(t + \Delta t) = F(t)\, \exp\big(-\tfrac12\sigma^2 \Delta t + \sigma \sqrt{\Delta t}\; Z\big)
$$

Integrate $\ln F$ instead of $F$ (Itô's lemma gives $d\ln F = -\tfrac12\sigma^2 dt + \sigma\, dW$),
then take the exponential. Each step **multiplies** by a factor close to 1. The price stays positive.
The $-\tfrac12\sigma^2 \Delta t$ term keeps the average price flat (a future has no drift).

Both formulas are **exact for any $\Delta t$**, not only for small steps (see section 5).

`montecarlo.py` and `SimulatedSource` use the GBM.

## 3–4. Step forward: one path

At each step you know everything you need:

| input | example |
|---|---|
| $F(t)$, the price at the previous step | 75.00 |
| $\sigma$, the vol (fixed) | 32% |
| $\Delta t$, the step | 1 day = 1/252 year, so $\sigma\sqrt{\Delta t} = 0.020$ |
| $Z$, a new random number | drawn from $\mathcal{N}(0,1)$ |

Brent with the GBM:

| step | Z | factor | price |
|---|---|---|---|
| 0 | | | 75.00 |
| 1 | +0.5 | $e^{+0.0099}$ | 75.74 |
| 2 | −1.2 | $e^{-0.0244}$ | 73.92 |
| 3 | +0.1 | $e^{+0.0018}$ | 74.05 |

The same three $Z$ with the arithmetic version ($\sigma_N = 24$, so $\sigma_N\sqrt{\Delta t} = 1.51$):
75.00 → 75.76 → 73.94 → 74.09. Close today, because $\sigma_N = \sigma F$ at 75; they drift apart
as the price moves away from 75.

The prices joined together are one **path**.

## 5. Many paths, one price

Repeat with new random numbers, $N = 200\,000$ times. For each path:

1. read the price on every fixing date of the APO
2. average them (with the fixings already known, if the month has started)
3. payoff: $\max(\phi\,(\bar F - K), 0)$

The price is the **mean of the $N$ payoffs** (then discounted, in `pricer.py`).
The error shrinks like $1/\sqrt{N}$: four times more paths for half the error.

## 6. Bigger steps when nothing happens in between

The APO only looks at the prices on its fixing dates. Because the step formulas are exact,
one step of $\Delta t = 150/252$ gives the **same distribution** as 150 steps of $1/252$:
the variances of the shocks add up, $150 \times \frac{1}{252} = \frac{150}{252}$.
Each path lands on a different number, but over 200 000 paths the spread of June prices is the same.

So `montecarlo.py` jumps from today straight to the first fixing (about 7 months for APO-003),
then steps fixing by fixing through June: about 21 draws per path instead of 150.

`SimulatedSource` steps every day anyway, because the hedging bot acts every day.

Small steps are required when the payoff looks at every day (a barrier), or when the vol
itself moves (no exact step formula).

## 7. Several legs move together

HO and Brent are correlated ($\rho = 0.95$). Draw one independent $Z$ per leg, then mix them
with the Cholesky factor $L$ of the correlation matrix ($L L^\top = C$): $X = L Z$.
With two legs: $x_{HO} = z_1$, $x_{B} = 0.95\, z_1 + \sqrt{1 - 0.95^2}\, z_2$.
Brent gets 95% of HO's shock plus a small shock of its own.

## In the code

| step | function |
|---|---|
| times of the fixings, $t_1 \dots t_n$ | `schedule.fixing_times` |
| $Z$, correlated, scaled by $\sqrt{\Delta t}$, summed into $W(t_i)$ | `correlated_brownians` |
| GBM price on each fixing | `futures_paths`: $F_0 \exp(-\tfrac12\sigma^2 t_i + \sigma W(t_i))$ |
| weights, average, payoff, mean over paths | `expected_payoff` |

All paths are computed at once with arrays of shape (paths, fixings, legs), no loop.
The seed is fixed (`seed=42`) so that the greeks, which bump and reprice, reuse the same $Z$:
the difference then comes from the bump, not from new random numbers.
