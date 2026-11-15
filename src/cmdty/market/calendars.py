"""Exchange calendars for fixing dates."""

from importlib import resources

import holidays
import QuantLib as ql
import yaml

# =============================================================================
# 1. Generator — build a QuantLib calendar from the `holidays` package
# =============================================================================


def calendar_from_holidays(
    mic: str, first_year: int = 2020, last_year: int = 2035
) -> ql.Calendar:
    """QuantLib calendar built from the `holidays` package financial calendars.

    mic: ISO 10383 market identifier supported by holidays.financial_holidays,
         e.g. "IFEU" (ICE Futures Europe), "XNYS" (NYSE), "XLON" (LSE).
    """
    cal = ql.BespokeCalendar(f"{mic} (holidays package)")
    cal.addWeekend(ql.Saturday)
    cal.addWeekend(ql.Sunday)
    for d in holidays.financial_holidays(mic, years=range(first_year, last_year + 1)):
        cal.addHoliday(ql.Date(d.day, d.month, d.year))
    return cal


# =============================================================================
# 2. Calendars — exchange calendars
# =============================================================================


def nymex_calendar() -> ql.Calendar:
    """NYMEX settlement-day proxy: NYSE holidays (see module docstring)."""
    return ql.UnitedStates(ql.UnitedStates.NYSE)


def cme_calendar(first_year: int = 2020, last_year: int = 2035) -> ql.Calendar:
    """CME Group (Chicago) Globex TRADING calendar, MIC "XCME" (CME, CBOT, NYMEX, COMEX)."""
    return calendar_from_holidays("XCME", first_year, last_year)


def ice_futures_europe_calendar(
    first_year: int = 2020, last_year: int = 2035
) -> ql.Calendar:
    """ICE Futures Europe (Brent) trading/settlement days."""
    return calendar_from_holidays("IFEU", first_year, last_year)


# =============================================================================
# 3. Generic calendar functions
# =============================================================================


def joint_calendar(*calendars: ql.Calendar) -> ql.Calendar:
    """All common business days from ALL calendars."""
    cal = calendars[0]
    for other in calendars[1:]:
        cal = ql.JointCalendar(cal, other, ql.JoinHolidays)
    return cal


def business_days(calendar: ql.Calendar, start: ql.Date, end: ql.Date) -> list:
    """Business days of `calendar` in [start, end] (both included)."""
    out, d = [], start
    while d <= end:
        if calendar.isBusinessDay(d):
            out.append(d)
        d = d + 1
    return out


# =============================================================================
# 4. Lookup by exchange code (ISO 10383 MIC), used by the portfolio file
# =============================================================================


def nyse_calendar() -> ql.Calendar:
    """New York Stock Exchange."""
    return ql.UnitedStates(ql.UnitedStates.NYSE)


def _load_exchange_table() -> dict:
    """calendars.yaml: exchange name -> mic, function, days, note."""
    text = resources.files("cmdty.market").joinpath("calendars.yaml").read_text()
    table = yaml.safe_load(text)
    mics = [entry["mic"] for entry in table.values()]
    if len(mics) != len(set(mics)):
        raise ValueError("calendars.yaml: the same MIC is used twice")
    return table


EXCHANGES = _load_exchange_table()
_BY_MIC = {entry["mic"]: name for name, entry in EXCHANGES.items()}


def exchange_calendar(code: str) -> ql.Calendar:
    """Calendar of one exchange, by name ("NYMEX") or MIC ("XNYM")."""
    name = code if code in EXCHANGES else _BY_MIC.get(code)
    if name is not None:
        return globals()[EXCHANGES[name]["function"]]()
    if code in holidays.list_supported_financial():
        return calendar_from_holidays(code)
    raise KeyError(f"unknown exchange {code!r}, see available_calendars()")


def joint_exchange_calendar(codes: list[str]) -> ql.Calendar:
    """Common business days of several exchanges, e.g. ["NYMEX", "ICE-EU"].
    Each exchange once: "NYMEX" and "XNYM" together count as a duplicate."""
    names = [_BY_MIC.get(c, c) for c in codes]
    if not names:
        raise ValueError("no exchange given")
    if len(set(names)) != len(names):
        raise ValueError(f"exchange listed twice in {codes}")
    return joint_calendar(*(exchange_calendar(c) for c in codes))


def any_exchange_calendar(codes: list[str]) -> ql.Calendar:
    """Days when at least one of the exchanges is open, e.g. to simulate settlements for a
    book whose trades fix on different exchanges."""
    cals = [exchange_calendar(c) for c in codes]
    cal = cals[0]
    for other in cals[1:]:
        cal = ql.JointCalendar(cal, other, ql.JoinBusinessDays)
    return cal


def available_calendars() -> list[str]:
    """Every code exchange_calendar() knows: names and MICs from calendars.yaml, then holidays."""
    ours = set(EXCHANGES) | set(_BY_MIC)
    return sorted(ours | {m for m in holidays.list_supported_financial() if len(m) == 4})
