"""Averaging schedule: when prices are observed and when the payoff is paid.

Shared by every averaging product (APO, average price swap...).
"""

import numpy as np
import QuantLib as ql
from pydantic import BaseModel, ConfigDict, Field

from ..market.calendars import business_days
from ..market.dates import MonthRange


class AveragingSchedule(BaseModel):
    """Pricing period, fixing calendar and payment lag of an averaging contract."""

    model_config = ConfigDict(frozen=True, arbitrary_types_allowed=True, extra="forbid")

    pricing_period: MonthRange  # month code, e.g. "2027-03"
    calendar: ql.Calendar  # fixing calendar, e.g. joint NYMEX/ICE
    pay_lag: int = Field(default=5, ge=0, description="business days after the last fixing")
    day_counter: ql.DayCounter = Field(default_factory=ql.Actual365Fixed)

    # --- fixings ---
    def fixing_dates(self) -> list:
        """Days whose settlement prices enter the average (pricing days)."""
        return business_days(self.calendar, self.pricing_period.start, self.pricing_period.end)

    # today_fixed: today's settlement is already published (end of day), so today's
    # fixing counts as past. Otherwise it is still to come.
    def past_fixings(self, today: ql.Date, today_fixed: bool = False) -> list:
        """Fixings already published: before today, and today if already settled."""
        return [d for d in self.fixing_dates() if d < today or (today_fixed and d == today)]

    def future_fixings(self, today: ql.Date, today_fixed: bool = False) -> list:
        """Fixings still to come."""
        past = set(self.past_fixings(today, today_fixed))
        return [d for d in self.fixing_dates() if d not in past]

    def fixing_times(self, today: ql.Date, today_fixed: bool = False) -> np.ndarray:
        """Future fixing dates as year fractions from today."""
        return np.array([
            self.day_counter.yearFraction(today, d)
            for d in self.future_fixings(today, today_fixed)
        ])

    def t_eff(self, today: ql.Date, today_fixed: bool = False) -> float:
        """Effective time of the remaining average: mean_ij min(t_i, t_j) over future fixings."""
        t = self.fixing_times(today, today_fixed)
        if len(t) == 0:
            return 0.0
        return float(np.minimum.outer(t, t).mean())

    # --- payment ---
    @property
    def pay_date(self) -> ql.Date:
        """Last fixing + pay_lag business days: never before the pricing period ends."""
        return self.calendar.advance(self.fixing_dates()[-1], self.pay_lag, ql.Days)
