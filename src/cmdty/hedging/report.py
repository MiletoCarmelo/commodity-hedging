"""Monitoring: what a trader looks at every morning, from one day of a HedgeRun.

The bot decides by itself, the report says why: exposure per contract month before and
after the hedge, each trade with its reason, contracts close to expiry, and yesterday's P&L
split by greek. Needs pandas.
"""

import QuantLib as ql

from ..market.futures import contract_label, expiry_date
from .engine import Day, HedgeRun

# =============================================================================
# 1. Tables
# =============================================================================


def ladder(day: Day):
    """Exposure per futures contract, in bbl: options, futures held, and what is left."""
    import pandas as pd

    rows = []
    for key in sorted(set(day.deltas_by_contract) | set(day.position) | set(day.traded)):
        u, month = key
        y, m = (int(x) for x in month.split("-"))
        lots = day.position.get(key, 0)
        options = day.deltas_by_contract.get(key, 0.0)
        futures = lots * day.lot_sizes[u]
        rows.append({
            "underlying": u, "contract": contract_label(u, y, m),
            "expiry": expiry_date(u, y, m).to_date(),
            "options bbl": options, "futures lots": lots, "futures bbl": futures,
            "net bbl": options + futures,
            "traded lots": day.traded.get(key, 0), "reason": day.reasons.get(key, ""),
        })
    return pd.DataFrame(rows).set_index(["underlying", "contract"])


def expiring(day: Day, within: int = 5):
    """Contracts held that stop trading within `within` calendar days: time to roll."""
    table = ladder(day)
    if table.empty:
        return table
    days_left = (table["expiry"] - day.date.to_date()).apply(lambda d: d.days)
    held = table["futures lots"] != 0
    return table.loc[held & (days_left <= within), ["expiry", "futures lots"]].assign(
        days_left=days_left[held & (days_left <= within)])


def pnl_lines(day: Day) -> dict[str, float]:
    """Yesterday to today: option, futures, costs, and the option P&L by greek."""
    lines = {"options": day.option_pnl, "futures": day.hedge_pnl, "costs": -day.cost,
             "total": day.pnl}
    for name, value in (day.explain or {}).items():
        lines[f"  explain {name}"] = value
    return lines


# =============================================================================
# 2. Report
# =============================================================================


def daily_report(run: HedgeRun, date: ql.Date | None = None) -> str:
    """Text report of one day (default: the last one), as a trader would read it."""
    days = {d.date: d for d in run.days}
    day = days[date] if date is not None else run.days[-1]
    table = ladder(day)
    out = [f"=== {day.date.ISO()} ===", "", "P&L since yesterday ($)"]
    out += [f"  {k:<22}{v:>12,.0f}" for k, v in pnl_lines(day).items()]
    out += ["", "Exposure by contract (bbl)"]
    out += [table.drop(columns=["expiry"]).round(0).to_string()] if not table.empty else ["  flat"]
    traded = table[table["traded lots"] != 0] if not table.empty else table
    out += ["", "Trades today"]
    if traded.empty:
        out += ["  none"]
    else:
        for (u, c), r in traded.iterrows():
            side = "buy" if r["traded lots"] > 0 else "sell"
            out += [f"  {side} {abs(int(r['traded lots']))} {c} ({r['reason']})"]
    soon = expiring(day)
    out += ["", "Expiring within 5 days"]
    out += [f"  {c}: {int(r['futures lots'])} lots, expires {r['expiry']}" for (u, c), r in soon.iterrows()] or ["  none"]
    return "\n".join(out)
