import numpy as np
import pytest
import QuantLib as ql

from cmdty import MarketData, Pricer, Quote, load_portfolio
from cmdty.market import SimulatedSource, any_exchange_calendar

TODAY = ql.Date(10, 11, 2026)
CAL = any_exchange_calendar(["NYMEX", "ICE-EU"])  # every settlement day of either exchange


def start_market(rho=0.95):
    return MarketData(today=TODAY, rate=0.04,
                      quotes={"HO": Quote(105.0, 0.30), "BRENT": Quote(75.0, 0.32),
                              "WTI": Quote(71.0, 0.33)},
                      correlations={("HO", "BRENT"): rho, ("WTI", "BRENT"): 0.97,
                                    ("HO", "WTI"): 0.93})


def source(end=ql.Date(15, 7, 2027), **kwargs):
    return SimulatedSource(start_market(), end, CAL, **kwargs)


def log_returns(src, u):
    prices = np.array([src.snapshot(d).forward(u) for d in src.dates()])
    return np.diff(np.log(prices))


def test_dates_are_business_days_from_start():
    dates = source().dates()
    assert dates[0] == TODAY and dates[-1] <= ql.Date(15, 7, 2027)
    assert all(CAL.isBusinessDay(d) for d in dates[1:])
    assert ql.Date(26, 3, 2027) not in dates            # Good Friday: both closed
    assert ql.Date(18, 6, 2027) in dates                # Juneteenth: ICE open, NYMEX closed


def test_same_seed_same_path():
    a, b, c = source(seed=1), source(seed=1), source(seed=2)
    d = a.dates()[-1]
    assert a.snapshot(d).forward("HO") == b.snapshot(d).forward("HO")
    assert a.snapshot(d).forward("HO") != c.snapshot(d).forward("HO")


def test_snapshot_is_end_of_day():
    src = source()
    yesterday, today = src.dates()[10], src.dates()[11]
    m = src.snapshot(today)
    assert m.today == today and m.vol("HO") == 0.30         # implied vol unchanged
    assert m.fixing("HO", today) == m.forward("HO")         # today's settlement is published
    assert m.fixing("HO", yesterday) == src.snapshot(yesterday).forward("HO")
    with pytest.raises(KeyError):
        m.fixing("HO", src.dates()[12])                     # tomorrow is not


def test_no_drift():
    end = ql.Date(10, 2, 2027)
    finals = [source(end, seed=s).snapshot(end).forward("BRENT") for s in range(400)]
    assert np.mean(finals) == pytest.approx(75.0, rel=0.02)


def test_realized_vol_and_corr_are_separate_from_implied():
    src = SimulatedSource(start_market(), ql.Date(10, 11, 2030), CAL,
                          realized_vol={"HO": 0.20}, realized_corr=0.5, seed=3)
    r_ho, r_br = log_returns(src, "HO"), log_returns(src, "BRENT")
    assert np.std(r_ho) * np.sqrt(252) == pytest.approx(0.20, rel=0.1)
    assert np.std(r_br) * np.sqrt(252) == pytest.approx(0.32, rel=0.1)   # default: implied
    assert np.corrcoef(r_ho, r_br)[0, 1] == pytest.approx(0.5, abs=0.07)
    assert src.snapshot(src.dates()[-1]).vol("HO") == 0.30               # pricer still sees implied


def test_portfolio_prices_through_the_whole_path():
    apo = load_portfolio("portfolios/example_book.yaml").trade("APO-003").instrument
    src = source()
    pvs = [Pricer(market=src.snapshot(d)).pv(apo) for d in src.dates()]
    assert pvs[-1] == 0.0 and all(np.isfinite(pvs))
    # just after the month: PV is the known payoff, discounted
    after = src.snapshot(ql.Date(1, 7, 2027))
    avg = np.mean([apo.combine({u: after.fixing(u, d) for u in apo.underlyings})
                   for d in apo.schedule.fixing_dates()])
    payoff = max(avg - apo.strike, 0.0)
    assert Pricer(market=after).pv(apo) == pytest.approx(
        after.discount_factor(apo.schedule.pay_date, apo.schedule.day_counter) * payoff)
