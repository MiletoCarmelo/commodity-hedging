"""Futures contract conventions: month codes and which contract a pricing month uses."""

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
    """Contract month referenced while pricing in (year, month).

    NY Harbor ULSD expires the last business day of the month before delivery, so
    during March the first nearby is April (months_ahead=1). ICE Brent expires two
    months before, so the first line during March is May (months_ahead=2).
    """
    index = year * 12 + (month - 1) + months_ahead
    return index // 12, index % 12 + 1
