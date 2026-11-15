"""What is already known during the pricing month: past fixings, adjusted strike.

With n fixings, m of them published with average value A, the payoff is

    max(phi * ((m * A + (n - m) * A_future) / n - K), 0)
  = (n - m) / n * max(phi * (A_future - K*), 0),   K* = (n * K - m * A) / (n - m)

so the remaining option is an APO on the future fixings only, with strike K* and weight
(n - m) / n. Shared by the closed-form models.
"""

from dataclasses import dataclass

# =============================================================================
# 1. Averaging state
# =============================================================================


@dataclass(frozen=True)
class AveragingState:
    """Where we are in the pricing month: n fixings in total, m already published,
    and the average basket value of those m. K*, the weight and `done` are derived from it."""

    n: int
    m: int
    known_average: float  # average basket value of the published fixings, 0 if none
    today_fixed: bool = False  # today's settlement already counted in m

    @property
    def done(self) -> bool:
        """All fixings known: the payoff is certain."""
        return self.m == self.n

    @property
    def weight(self) -> float:
        """Share of the average still to come."""
        return (self.n - self.m) / self.n

    def adjusted_strike(self, strike: float) -> float:
        """Strike the remaining fixings have to beat, given what is already fixed."""
        return (self.n * strike - self.m * self.known_average) / (self.n - self.m)


# =============================================================================
# 2. Reading the published fixings
# =============================================================================


def averaging_state(apo, market) -> AveragingState:
    """Basket value of each past fixing date (sum of weight * published price), then
    their average. Before the month starts m = 0 and the average is 0.
    Today counts as fixed when the market already has today's settlement (end of day)."""
    today = market.today
    today_fixed = today in apo.schedule.fixing_dates() and all(
        today in market.fixings.get(u, {}) for u in apo.underlyings
    )
    past = apo.schedule.past_fixings(today, today_fixed)
    values = [apo.combine({u: market.fixing(u, d) for u in apo.underlyings}) for d in past]
    n = len(apo.schedule.fixing_dates())
    average = sum(values) / len(past) if past else 0.0
    return AveragingState(n=n, m=len(past), known_average=average, today_fixed=today_fixed)


# =============================================================================
# 3. Payoff once everything is fixed
# =============================================================================


def settled_payoff(apo, state: AveragingState) -> float:
    """Payoff per bbl once every fixing is known. Only valid at the end of the month,
    before that the average is partial and the result would be wrong."""
    if not state.done:
        raise ValueError(
            f"pricing period not finished: {state.m}/{state.n} fixings published"
        )
    return max(apo.phi * (state.known_average - apo.strike), 0.0)
