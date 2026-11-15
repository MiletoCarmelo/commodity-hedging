"""Dates: conversions between Python and QuantLib, date ranges."""

import datetime as dt
import re
from typing import Annotated, Any

import QuantLib as ql
from pydantic import AfterValidator, BaseModel, ConfigDict, field_validator, model_validator


def to_ql_date(value: Any) -> Any:
    """Accept datetime.date or 'YYYY-MM-DD' as well as ql.Date."""
    if isinstance(value, str):
        value = dt.date.fromisoformat(value)
    if isinstance(value, dt.date):
        return ql.Date(value.day, value.month, value.year)
    return value


class DateRange(BaseModel):
    """Closed range of dates [start, end], e.g. the pricing period of an APO."""

    model_config = ConfigDict(frozen=True, arbitrary_types_allowed=True)

    start: ql.Date
    end: ql.Date

    @model_validator(mode="before")
    @classmethod
    def _from_month_code(cls, data: Any) -> Any:
        """Accept a month code 'YYYY-MM' (e.g. '2027-03') for a whole month."""
        if isinstance(data, str):
            match = re.fullmatch(r"(\d{4})-(\d{2})", data)
            if not match or not 1 <= int(match[2]) <= 12:
                raise ValueError(f"expected a month code 'YYYY-MM', got {data!r}")
            first = ql.Date(1, int(match[2]), int(match[1]))
            return {"start": first, "end": ql.Date.endOfMonth(first)}
        return data

    _to_date = field_validator("start", "end", mode="before")(to_ql_date)

    @model_validator(mode="after")
    def _check_order(self) -> "DateRange":
        if not self.start <= self.end:
            raise ValueError(f"start {self.start} must be on or before end {self.end}")
        return self

    @classmethod
    def month(cls, year: int, month: int) -> "DateRange":
        """Whole calendar month, e.g. DateRange.month(2027, 3), same as '2027-03'."""
        return cls.model_validate(f"{year:04d}-{month:02d}")

    def is_month(self) -> bool:
        """True if the range is exactly one whole calendar month."""
        return self.start.dayOfMonth() == 1 and self.end == ql.Date.endOfMonth(self.start)

    def __str__(self) -> str:
        """'2027-03' for a whole month, 'start -> end' otherwise."""
        if self.is_month():
            return f"{self.start.year()}-{self.start.month():02d}"
        return f"{self.start.ISO()} -> {self.end.ISO()}"

    def __contains__(self, d: ql.Date) -> bool:
        return self.start <= d <= self.end


def _require_month(r: DateRange) -> DateRange:
    if not r.is_month():
        raise ValueError(f"must be one whole calendar month, got {r}")
    return r


# DateRange restricted to one whole month, e.g. "2027-03"
MonthRange = Annotated[DateRange, AfterValidator(_require_month)]
