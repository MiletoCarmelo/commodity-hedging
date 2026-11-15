# Math

Back to [Home](Home.md)

Notation: $F_k$ the forward of leg $k$ and $w_k$ its weight ($F_1, F_2$ for a two-leg spread), $K$ the strike,
$\sigma_1, \sigma_2$ lognormal vols, $\rho$ their correlation, $\phi = +1$ for a call and
$-1$ for a put.

## Payoff

$$
\text{payoff} = \max\big(\phi\,(A - K),\, 0\big),
\qquad
A = \frac{1}{n}\sum_{i=1}^{n}\sum_{k} w_k\,F_k(t_i)
$$

$t_i$ are the fixing dates (as year fractions from today, ACT/365), $w_k$ the leg weights.
The HO–Brent crack is $w = (+1, -1)$, an outright APO has a single leg.

## Effective time of the average

For a Brownian motion sampled at the fixings:

$$
\mathrm{Var}\,\Big(\frac{1}{n}\sum_i W(t_i)\Big) = T_{\text{eff}},
\qquad
T_{\text{eff}} = \frac{1}{n^2}\sum_{i,j}\min(t_i, t_j)
$$

With a continuous average from $T_1$ to $T_2$ this tends to $T_1 + (T_2 - T_1)/3$.
Code: `AveragingSchedule.t_eff`.

## During the pricing month

With $n$ fixings, $m$ already published with average value $A_{\text{known}}$:

$$
\text{payoff}
= \max\Big(\phi\,\Big(\tfrac{m\,A_{\text{known}} + (n-m)\,A_{\text{future}}}{n} - K\Big), 0\Big)
= \frac{n-m}{n}\,\max\big(\phi\,(A_{\text{future}} - K^*), 0\big)
$$

$$
K^* = \frac{nK - m\,A_{\text{known}}}{n - m}
$$

So the remaining trade is an APO on the future fixings only, strike $K^*$, weight
$(n-m)/n$. $T_{\text{eff}}$ is computed on the future fixings. When $m = n$ the payoff is
known, delta is zero, only discounting is left. After the pay date the PV is zero.

Which fixings count as published depends on the time of day. Before the settlement, today's
fixing is still to come and moves with the forward. At the end of the day the settlement is
out, today is fixed and drops out of the delta. The code counts today as fixed as soon as the
market holds today's settlement for every leg. The price is the same either way (fixing =
forward), the delta is not: about 1/n of the position less. Getting this wrong shows up as
unexplained P&L every day of the month.

Kirk needs $F_2 + K^* > 0$. Deep in the money late in the month $K^*$ can be very negative,
the code then falls back to Bachelier.
Code: `models.averaging`.

## Black-76 and implied vol

Option on a future, no drift:

$$
C = DF\,\big[F\,N(d_1) - K\,N(d_2)\big],
\qquad
d_{1,2} = \frac{\ln(F/K) \pm \sigma^2 T/2}{\sigma\sqrt{T}}
$$

The implied vol is the $\sigma$ that matches a market price. QuantLib's
`blackFormulaImpliedStdDev` returns $\sigma\sqrt{T}$, so we divide by $\sqrt{T}$.
Code: `market.vol.implied_vol_black76`.

## Spread vol in dollars

Normal vol of each leg (ATM approximation) and of their difference:

$$
v_i = \sigma_i F_i,
\qquad
\sigma_N = \sqrt{v_1^2 + v_2^2 - 2\rho\,v_1 v_2}
$$

With $v_1 = 31.5$, $v_2 = 24$, $\rho = 0.95$: $\sigma_N = 11.48$ $/bbl/yr.

For any number of legs it's the same idea with a matrix: $\sigma_N = \sqrt{w^\top C\, w}$,
with $C_{kl} = \rho_{kl}\, v_k v_l$. Two legs with $w = (1, -1)$ give the formula above.
Code: `market.vol.spread_vol`, `models.bachelier.spread_normal_vol`.

Side effect: $\partial \sigma_N / \partial v_2 \propto v_2 - \rho v_1 < 0$ here, so more Brent
vol means a *cheaper* option. That is why vega Brent is negative.

## Bachelier

$$
s = \sigma_N\sqrt{T_{\text{eff}}},
\qquad
d = \frac{F - K}{s},
\qquad
E[\text{payoff}] = (F - K)\,N(d) + s\,n(d)
$$

with $F = \sum_k w_k F_k$, $N$ the normal cdf and $n$ its density (call).
Code: `models.bachelier`.

## Kirk

Treat $F_2 + K$ as a second asset and price an exchange option with Black:

$$
w = \frac{F_2}{F_2 + K},
\qquad
\sigma_K = \sqrt{\sigma_1^2 - 2\rho\,\sigma_1\sigma_2\,w + \sigma_2^2 w^2}
$$

$$
d_1 = \frac{\ln\big(F_1/(F_2+K)\big) + \sigma_K^2 T/2}{\sigma_K\sqrt{T}},
\qquad
d_2 = d_1 - \sigma_K\sqrt{T}
$$

$$
E[\text{payoff}] = F_1\,N(d_1) - (F_2 + K)\,N(d_2)
$$

$T = T_{\text{eff}}$ for the average, each forward is multiplied by the size of its weight. QuantLib does this in
`KirkEngine`. Because $w$ depends on $F_2$, the two deltas are not symmetric.
Code: `models.kirk`.

## Monte Carlo

Each future is a driftless GBM:

$$
F_i(t) = F_i(0)\,\exp\big(-\tfrac{1}{2}\sigma_i^2 t + \sigma_i W_i(t)\big)
$$

Correlated shocks from independent ones with the Cholesky factor:

$$
C = L L^\top,
\qquad
X = L Z, \quad Z \sim \mathcal{N}(0, I)
$$

In 2D: $x_1 = z_1$, $x_2 = \rho z_1 + \sqrt{1-\rho^2}\,z_2$.
If $C$ is not positive definite, negative eigenvalues are clipped and the diagonal reset to 1.
Code: `models.montecarlo`.

## Discounting

In general a trade is a set of cash flows, each discounted on a curve:

$$
PV = \sum_k DF(t_k)\; E[\text{cash flow}_k] \;-\; \text{CVA}
$$

| piece | comes from | in this repo |
|---|---|---|
| $E[\text{cash flow}]$ | the payoff and the fixing conventions | the models |
| $t_k$, the pay dates | the contract (pay lag, premium style) | `AveragingSchedule.pay_date`, `premium_style` |
| $DF(t)$, the curve | the market, chosen by the collateral agreement (OIS if collateralised, a funding curve if not) | one flat rate in `MarketData` |
| CVA | the counterparty | not modelled |

So two trades on the same crack, same month, same strike, can have different PVs: different
pay dates, premium styles, collateral or counterparty.

For one APO paid once:

$$
PV = DF(T_{\text{pay}}) \cdot E[\text{payoff}],
\qquad
DF(T) = e^{-r T} \text{ (flat rate, continuous compounding)}
$$

$T$ follows a day count: ACT/365 here, ACT/360 is the usual one for USD rates. Not to be
confused with 252, the number of trading days used to annualise volatility.

Premium style:

- upfront: premium paid today, payoff discounted from the pay date
- futures-style margined: value settled every day, $DF = 1$

Same trade, same market (Kirk, notebook 01, section 3b):

| payment terms | DF | PV $/bbl |
|---|---|---|
| upfront, paid 8 Apr | 0.9838 | 3.580 |
| upfront, paid 12 May | 0.9801 | 3.567 |
| futures-style | 1 | 3.639 |

Code: `Pricer.discount_factor`, `MarketData.discount_factor`.

## Greeks

Central differences, the market is bumped, the trade is not:

$$
\Delta = \frac{PV(F+h) - PV(F-h)}{2h},
\qquad
\Gamma = \frac{PV(F+h) - 2PV(F) + PV(F-h)}{h^2}
$$

Crack and outright deltas from the leg deltas:

$$
\Delta_{\text{crack}} = \frac{\Delta_1 - \Delta_2}{2},
\qquad
\Delta_{\text{outright}} = \Delta_1 + \Delta_2
$$

Bachelier keeps $\sigma_N$ fixed in dollars during forward bumps, so its outright delta is 0.
Code: `risk.greeks`.

## Roll jumps

Continuous front-month series jump at each roll. Robust z-score on daily log-returns:

$$
z = \frac{r_t - \mathrm{median}\,(r)}{1.4826\,\mathrm{MAD}\,(r)}
$$

Dates with $|z| > 5$ are dropped before estimating vols and correlation.
Code: `data.estimation.flag_jumps`.
