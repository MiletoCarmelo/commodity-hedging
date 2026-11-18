"""Futures contracts: month codes, expiry rules, and which contract a date refers to."""

from functools import lru_cache
from importlib import resources

import QuantLib as ql
import yaml

from .calendars import exchange_calendar

# =============================================================================
# 1. Month codes and symbols
# =============================================================================

# CME/ICE month codes: F=Jan G=Feb H=Mar J=Apr K=May M=Jun N=Jul Q=Aug U=Sep V=Oct X=Nov Z=Dec
MONTH_CODES = "FGHJKMNQUVXZ"


def month_code(month: int) -> str:
    """Futures month letter, e.g. 4 -> 'J'."""
    if not 1 <= month <= 12:
        raise ValueError(f"month must be in 1..12, got {month}")
    return MONTH_CODES[month - 1]


def contract_symbol(root: str, year: int, month: int) -> str:
    """Exchange symbol of a contract, e.g. ('HO', 2027, 4) -> 'HOJ27'."""
    return f"{root}{month_code(month)}{year % 100:02d}"


def nearby_contract(year: int, month: int, months_ahead: int) -> tuple[int, int]:
    """Contract month `months_ahead` after (year, month), e.g. (2027, 3, 2) -> (2027, 5)."""
    index = year * 12 + (month - 1) + months_ahead
    return index // 12, index % 12 + 1


# =============================================================================
# 2. Contract specs (futures.yaml)
# =============================================================================


def _load_futures_table() -> dict:
    """futures.yaml: underlying -> contract, exchange, symbol, lot_size, expiry rule."""
    text = resources.files("cmdty.market").joinpath("futures.yaml").read_text()
    return yaml.safe_load(text)


FUTURES = _load_futures_table()


def futures_spec(underlying: str) -> dict:
    """Spec of the future hedging one underlying."""
    try:
        return FUTURES[underlying]
    except KeyError:
        raise KeyError(f"no futures contract for {underlying!r}, see futures.yaml") from None


# =============================================================================
# 3. Expiry and front contract
# =============================================================================


def _last_business_day(calendar: ql.Calendar, year: int, month: int) -> ql.Date:
    return calendar.endOfMonth(ql.Date(1, month, year))


@lru_cache(maxsize=None)  # rules are fixed: compute each contract once
def expiry_date(underlying: str, year: int, month: int) -> ql.Date:
    """Last trading day of the (year, month) delivery contract of one underlying."""
    spec = futures_spec(underlying)
    cal = exchange_calendar(spec["exchange"])
    rule = spec["expiry"]
    if rule == "m1_last":
        return _last_business_day(cal, *nearby_contract(year, month, -1))
    if rule == "m2_last":
        return _last_business_day(cal, *nearby_contract(year, month, -2))
    if rule == "wti":
        y, m = nearby_contract(year, month, -1)
        day25 = cal.adjust(ql.Date(25, m, y), ql.Preceding)  # the 25th, or the business day before
        return cal.advance(day25, -3, ql.Days)
    raise ValueError(f"unknown expiry rule {rule!r} for {underlying}")


def front_contract(underlying: str, date: ql.Date) -> tuple[int, int]:
    """Delivery month of the first contract still trading on `date` (the one a fixing uses)."""
    return _front_contract(underlying, date.serialNumber())


@lru_cache(maxsize=None)
def _front_contract(underlying: str, serial: int) -> tuple[int, int]:
    date = ql.Date(serial)
    year, month = date.year(), date.month()
    for k in range(0, 4):
        y, m = nearby_contract(year, month, k)
        if expiry_date(underlying, y, m) >= date:
            return y, m
    raise ValueError(f"no live contract found for {underlying} on {date.ISO()}")


def contract_label(underlying: str, year: int, month: int) -> str:
    """Readable contract name, e.g. ('BRENT', 2027, 3) -> 'BH27'."""
    return contract_symbol(futures_spec(underlying)["symbol"], year, month)
