import numpy as np
import pytest
import QuantLib as ql

from cmdty import MarketData, Portfolio, Quote, load_portfolio
from cmdty.hedging import (HedgeSettings, HedgingBot, daily_report, ladder, load_hedge_settings,
                           target_lots, trade_reasons)
from cmdty.market import contract_label, expiry_date, front_contract
from cmdty.risk import book_risk, contract_weights
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
    by_contract = {("HO", "2027-07"): -12580.0, ("BRENT", "2027-08"): 2543.0}
    assert target_lots(by_contract, {"HO": 1000, "BRENT": 1000}) == {
        ("HO", "2027-07"): 13, ("BRENT", "2027-08"): -3}


def test_short_crack_is_hedged_long_ho_short_brent():
    risk = book_risk(CRACK, Pricer(market=start_market()))
    assert risk.pv < 0                                    # we sold the option
    assert risk.deltas["HO"] < 0 < risk.deltas["BRENT"]
    first = run().days[0]
    assert first.lots("HO") > 0 > first.lots("BRENT")
    assert set(first.position) == {("HO", "2027-07"), ("BRENT", "2027-08")}  # June fixings


def test_brent_is_netted_across_the_book():
    pricer = Pricer(market=start_market())
    per_trade = [book_risk(Portfolio(name=t.id, trades=[t]), pricer).deltas.get("BRENT", 0.0)
                 for t in BOOK]
    net = book_risk(BOOK, pricer).deltas["BRENT"]
    assert net == pytest.approx(sum(per_trade))
    assert abs(net) < sum(abs(d) for d in per_trade) / 4  # most of the Brent risk cancels
    first = run(BOOK, settings=FREE).days[0]
    assert first.position == {k: n for k, n in target_lots(
        book_risk(BOOK, pricer).deltas_by_contract, 1000).items() if n}


def test_pnl_bookkeeping():
    days = run(BOOK, settings=HedgeSettings(explain=False)).days
    lot = 1000
    for prev, day in zip(days, days[1:]):
        expected = sum(n * lot * (day.forwards[u] - prev.forwards[u])
                       for (u, _), n in prev.position.items())
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


# ---------------- contract months ----------------

def test_front_contract_follows_the_expiry_rules():
    assert expiry_date("BRENT", 2027, 3) == ql.Date(29, 1, 2027)    # last bd of M-2
    assert expiry_date("HO", 2027, 7) == ql.Date(30, 6, 2027)       # last bd of M-1
    assert expiry_date("WTI", 2027, 5) == ql.Date(20, 4, 2027)      # 3 bd before the 25th
    assert contract_label("WTI", *front_contract("WTI", ql.Date(20, 4, 2027))) == "CLK27"
    assert contract_label("WTI", *front_contract("WTI", ql.Date(21, 4, 2027))) == "CLM27"


def test_wti_april_average_splits_over_two_contracts():
    weights = contract_weights(BOOK.trade("APO-002"), Pricer(market=start_market()))
    may, june = weights[("WTI", "2027-05")], weights[("WTI", "2027-06")]
    assert may + june == pytest.approx(1.0) and may > june > 0
    assert weights[("BRENT", "2027-06")] == pytest.approx(1.0)


def test_deltas_by_contract_add_up_to_the_underlying_delta():
    risk = book_risk(BOOK, Pricer(market=start_market()))
    for u, d in risk.deltas.items():
        assert sum(v for (x, _), v in risk.deltas_by_contract.items() if x == u) == pytest.approx(d)


def test_hedge_in_an_expired_contract_is_never_held():
    for day in run(BOOK, settings=FREE).days:
        for (u, month) in day.position:
            y, m = (int(x) for x in month.split("-"))
            assert expiry_date(u, y, m) >= day.date


def test_trade_reasons():
    before = {("WTI", "2027-05"): -2, ("WTI", "2027-06"): -3}
    after = {("WTI", "2027-06"): -4, ("BRENT", "2027-06"): 1}
    assert trade_reasons(before, after) == {
        ("WTI", "2027-05"): "close", ("WTI", "2027-06"): "adjust", ("BRENT", "2027-06"): "open"}


def test_settings_file_and_unhedgeable_book():
    settings = load_hedge_settings("config/hedging.yaml")
    assert settings.cost("HO") == 5.0 and settings.lot("BRENT") == 1000
    only_brent = settings.model_copy(update={"instruments": {"BRENT": settings.instruments["BRENT"]}})
    with pytest.raises(ValueError, match="no hedge instrument"):
        HedgingBot(BOOK, SimulatedSource(start_market(), END, CAL), only_brent)


def test_daily_report_reads_like_a_desk_screen():
    r = run(BOOK, settings=FREE)
    table = ladder(r.days[0])
    assert {"options bbl", "futures bbl", "net bbl", "reason"} <= set(table.columns)
    assert (table["net bbl"].abs() <= 500).all()          # each contract hedged to the lot
    text = daily_report(r, r.days[0].date)
    assert "Exposure by contract" in text and "Trades today" in text
