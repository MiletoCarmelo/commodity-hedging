"""The hedging bot: every day, price the book, rebalance the futures, book the P&L.

Backtest mode for now. The loop only talks to a MarketSource, so the same code will run on
historical or live data. All amounts in $, positions in lots.
"""

from dataclasses import dataclass, field

import QuantLib as ql

from ..market.sources import MarketSource
from ..portfolio import Portfolio
from ..pricer import Pricer
from ..risk.book import book_greeks, book_risk, book_theta, paid_cash
from .explain import explain_day
from .settings import HedgeSettings

# =============================================================================
# 1. Results
# =============================================================================


@dataclass(frozen=True)
class Day:
    """What happened on one date, end of day."""

    date: ql.Date
    forwards: dict[str, float]
    option_pv: float  # $, all trades
    deltas: dict[str, float]  # bbl, options only, before the hedge
    position: dict[str, int]  # futures lots held after rebalancing
    traded: dict[str, int]  # lots bought (+) or sold (-) today
    option_pnl: float  # change in PV + cash received
    hedge_pnl: float  # variation margin on yesterday's futures
    cost: float  # trading costs of today's rebalancing
    explain: dict[str, float] | None = None  # option P&L split by greek, see explain.py

    @property
    def pnl(self) -> float:
        return self.option_pnl + self.hedge_pnl - self.cost


@dataclass
class HedgeRun:
    """Every day of one backtest, in order."""

    days: list[Day] = field(default_factory=list)

    @property
    def total_pnl(self) -> float:
        return sum(d.pnl for d in self.days)

    def cumulative_pnl(self) -> list[float]:
        out, total = [], 0.0
        for d in self.days:
            total += d.pnl
            out.append(total)
        return out

    def to_frame(self):
        """One row per day (needs pandas)."""
        import pandas as pd

        rows = []
        for d in self.days:
            row = {"date": d.date.to_date(), "option_pv": d.option_pv,
                   "option_pnl": d.option_pnl, "hedge_pnl": d.hedge_pnl,
                   "cost": d.cost, "pnl": d.pnl}
            row.update({f"explain_{k}": v for k, v in (d.explain or {}).items()})
            for u in d.forwards:
                row[f"F_{u}"] = d.forwards[u]
                row[f"delta_{u}"] = d.deltas.get(u, 0.0)
                row[f"lots_{u}"] = d.position.get(u, 0)
            rows.append(row)
        frame = pd.DataFrame(rows).set_index("date")
        frame["cum_pnl"] = frame["pnl"].cumsum()
        return frame


# =============================================================================
# 2. Hedge decision
# =============================================================================


def target_lots(deltas: dict[str, float], lot_size: float) -> dict[str, int]:
    """Futures position that cancels the deltas, rounded to whole lots."""
    return {u: -round(d / lot_size) for u, d in deltas.items()}


# =============================================================================
# 3. Bot
# =============================================================================


class HedgingBot:
    """Delta hedges a portfolio with futures, one rebalancing per business day."""

    def __init__(
        self, portfolio: Portfolio, source: MarketSource, settings: HedgeSettings | None = None
    ) -> None:
        self.portfolio = portfolio
        self.source = source
        self.settings = settings or HedgeSettings()

    def run(self) -> HedgeRun:
        s = self.settings
        result = HedgeRun()
        position: dict[str, int] = {}
        prev_pricer, prev_pv, prev_risk, prev_greeks = None, 0.0, None, None

        for i, date in enumerate(self.source.dates()):
            pricer = Pricer(model=s.model, market=self.source.snapshot(date))
            forwards = {u: q.forward for u, q in pricer.market.quotes.items()}
            risk = book_risk(self.portfolio, pricer)

            greeks = book_greeks(self.portfolio, pricer) if s.explain else None

            # 1) P&L since yesterday, with yesterday's position
            option_pnl = hedge_pnl = 0.0
            explain = None
            if prev_pricer is not None:
                before = prev_pricer.market
                moves = {u: forwards[u] - before.forward(u) for u in forwards}
                cash = sum(paid_cash(t, prev_pricer, pricer) for t in self.portfolio)
                option_pnl = risk.pv + cash - prev_pv
                hedge_pnl = sum(lots * s.lot_size * moves[u] for u, lots in position.items())
                if prev_greeks is not None:
                    explain = explain_day(
                        option_pnl, prev_risk.deltas, prev_greeks,
                        theta=book_theta(self.portfolio, prev_pricer, date),
                        moves=moves,
                        vol_moves={u: pricer.market.vol(u) - before.vol(u) for u in forwards},
                        cash=cash,
                    )

            # 2) rebalance to the new deltas
            traded: dict[str, int] = {}
            if i % s.rebalance_every == 0:
                target = target_lots(risk.deltas, s.lot_size)
                for u in set(target) | set(position):
                    change = target.get(u, 0) - position.get(u, 0)
                    if change:
                        traded[u] = change
                position = {u: n for u, n in target.items() if n}
            cost = s.cost_per_lot * sum(abs(n) for n in traded.values())

            result.days.append(Day(
                date=date, forwards=forwards, option_pv=risk.pv, deltas=risk.deltas,
                position=dict(position), traded=traded,
                option_pnl=option_pnl, hedge_pnl=hedge_pnl, cost=cost, explain=explain,
            ))
            prev_pricer, prev_pv, prev_risk, prev_greeks = pricer, risk.pv, risk, greeks

        return result
