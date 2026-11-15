import numpy as np
import pytest
import QuantLib as ql

from cmdty import MarketData, Portfolio, Quote, load_portfolio
from cmdty.hedging import HedgeSettings, HedgingBot, book_risk, target_lots
from cmdty.market import SimulatedSource, any_exchange_calendar
from cmdty.pricer import Pricer

BOOK = load_portfolio("portfolios/example_book.yaml")              # three trades
CRACK = Portfolio(name="crack", trades=[BOOK.trade("APO-003")])    # the sold crack call alone
CAL = any_exchange_calendar(["NYMEX", "ICE-EU"])  # every settlement day of either exchange
END = ql.Date(15, 7, 2027)
FREE = HedgeSettings(cost_per_lot=0, explain=False)  # explain off: faster
IMPLIED = {"HO": 0.30, "BRENT": 0.32, "WTI": 0.33}


def start_market():
    return MarketData(today=ql.Date(10, 11, 2026), rate=0.04,
                      quotes={u: Quote(f, IMPLIED[u]) for u, f in
                              (("HO", 105.0), ("BRENT", 75.0), ("WTI", 71.0))},
                      correlations={("HO", "BRENT"): 0.95, ("WTI", "BRENT"): 0.97,
                                    ("HO", "WTI"): 0.93})


def run(book=CRACK, seed=1, vol_scale=1.0, settings=None):
    vols = {u: v * vol_scale for u, v in IMPLIED.items()}
    src = SimulatedSource(start_market(), END, CAL, realized_vol=vols, seed=seed)
    return HedgingBot(book, src, settings).run()


def test_target_lots_cancel_the_delta():
    assert target_lots({"HO": -12580.0, "BRENT": 2543.0}, 1000) == {"HO": 13, "BRENT": -3}


def test_short_crack_is_hedged_long_ho_short_brent():
    risk = book_risk(CRACK, Pricer(market=start_market()))
    assert risk.pv < 0                                    # we sold the option
    assert risk.deltas["HO"] < 0 < risk.deltas["BRENT"]
    first = run().days[0].position
    assert first["HO"] > 0 > first["BRENT"]


def test_brent_is_netted_across_the_book():
    pricer = Pricer(market=start_market())
    per_trade = [book_risk(Portfolio(name=t.id, trades=[t]), pricer).deltas.get("BRENT", 0.0)
                 for t in BOOK]
    net = book_risk(BOOK, pricer).deltas["BRENT"]
    assert net == pytest.approx(sum(per_trade))
    assert abs(net) < sum(abs(d) for d in per_trade) / 4  # most of the Brent risk cancels
    assert run(BOOK, settings=FREE).days[0].position == target_lots(
        book_risk(BOOK, pricer).deltas, 1000)


def test_pnl_bookkeeping():
    days = run(BOOK, settings=HedgeSettings(explain=False)).days
    lot = HedgeSettings().lot_size
    for prev, day in zip(days, days[1:]):
        expected = sum(n * lot * (day.forwards[u] - prev.forwards[u])
                       for u, n in prev.position.items())
        assert day.hedge_pnl == pytest.approx(expected)
        assert day.cost == pytest.approx(5.0 * sum(abs(n) for n in day.traded.values()))
    assert days[0].option_pnl == days[0].hedge_pnl == 0.0
    assert days[-1].option_pv == 0.0 and days[-1].position == {}   # all paid and unwound


def test_option_pnl_adds_up_to_payoffs_minus_premiums():
    r = run(BOOK, seed=4, settings=FREE)
    market = SimulatedSource(start_market(), END, CAL, seed=4).snapshot(r.days[-1].date)
    payoffs = sum(t.instrument.quantity * Pricer(market=market).expected_payoff(t.instrument)
                  for t in BOOK)
    assert sum(d.option_pnl for d in r.days) == pytest.approx(payoffs - r.days[0].option_pv)


def test_rebalance_every_week_trades_less():
    daily = run(settings=FREE)
    weekly = run(settings=HedgeSettings(rebalance_every=5, cost_per_lot=0, explain=False))
    lots = lambda r: sum(abs(n) for d in r.days for n in d.traded.values())
    assert lots(weekly) < lots(daily)


def test_short_vol_earns_when_realised_is_below_implied():
    seeds = range(10)
    low = [run(seed=s, vol_scale=0.5, settings=FREE).total_pnl for s in seeds]
    high = [run(seed=s, vol_scale=1.5, settings=FREE).total_pnl for s in seeds]
    assert np.mean(low) > 0 > np.mean(high)


def test_hedge_cuts_the_risk():
    runs = [run(seed=s, settings=FREE) for s in range(10)]
    hedged = np.std([r.total_pnl for r in runs])
    unhedged = np.std([sum(d.option_pnl for d in r.days) for r in runs])
    assert hedged < unhedged / 2


def test_explain_adds_up_and_leaves_little_unexplained():
    days = run(BOOK, seed=1, settings=HedgeSettings(cost_per_lot=0)).days[1:]
    for d in days:
        assert sum(d.explain.values()) == pytest.approx(d.option_pnl)
    total = lambda k: sum(abs(d.explain[k]) for d in days)
    moved = sum(abs(d.option_pnl) for d in days)
    assert total("unexplained") < 0.02 * moved             # Taylor covers 98% of the moves
    assert total("vega") == 0.0                          # implied vol does not move here
