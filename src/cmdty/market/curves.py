"""Discount curves."""

import QuantLib as ql

# =============================================================================
# 3. Discounting methods
# =============================================================================


def flat_discount_factor(
    today: ql.Date,
    pay_date: ql.Date,
    rate: float,
    day_counter: ql.DayCounter | None = None,
) -> float:
    """DF to the payment date on a flat, continuously compounded curve."""
    # same rate for every maturity, starting at the valuation date
    curve = ql.FlatForward(
        today, rate, day_counter or ql.Actual365Fixed(), ql.Continuous
    )
    # continuous compounding: DF = exp(-r * T), T from today to pay_date
    return curve.discount(pay_date)
