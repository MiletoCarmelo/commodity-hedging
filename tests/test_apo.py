import math

import numpy as np
import pytest
import QuantLib as ql
from pydantic import ValidationError

from cmdty import (AveragingSchedule, DateRange, Leg, business_days, MarketData, Pricer, Quote, APO, cme_calendar,
                       ice_futures_europe_calendar, implied_vol_black76, joint_calendar,
                       nymex_calendar)
from cmdty.market import implied_vol_normal, spread_vol
from cmdty.models.averaging import averaging_state
from cmdty.models.montecarlo import cholesky_factor, correlated_brownians

TODAY = ql.Date(10, 11, 2026)


CALENDAR = joint_calendar(nymex_calendar(), ice_futures_europe_calendar())


def make_schedule(**kwargs):
    kwargs.setdefault("pay_lag", 6)  # 6 business days after 31 Mar -> 8 Apr 2027
    kwargs.setdefault("pricing_period", "2027-03")
    return AveragingSchedule(calendar=CALENDAR, **kwargs)


CRACK = [Leg("HO", 1), Leg("BRENT", -1)]


def make_apo(option_type="call", legs=CRACK, **kwargs):
    kwargs.setdefault("strike", 28.0)
    return APO(legs=legs, schedule=make_schedule(), option_type=option_type, **kwargs)


def make_market(rho=0.95):
    return MarketData(
        today=TODAY, rate=0.04,
        quotes={"HO": Quote(105.0, 0.30), "BRENT": Quote(75.0, 0.32)},
        correlations={("HO", "BRENT"): rho})


def make_pricer(model="kirk", **kwargs):
    return Pricer(model=model, market=make_market(), **kwargs)


# ---------------- calendars ----------------

def test_fixings_march_2027_exclude_good_friday():
    dates = make_schedule().fixing_dates()
    assert len(dates) == 22
    assert ql.Date(26, 3, 2027) not in dates      # Good Friday
    assert ql.Date(29, 3, 2027) in dates          # Easter Monday: ICE Brent trades


def test_cme_trading_vs_nymex_settlement_calendar():
    mlk_2027 = ql.Date(18, 1, 2027)
    assert cme_calendar().isBusinessDay(mlk_2027)          # Globex trades on MLK day
    assert not nymex_calendar().isBusinessDay(mlk_2027)    # ...but no regular settlement
    assert not cme_calendar().isBusinessDay(ql.Date(26, 3, 2027))


# ---------------- volatilities ----------------

def test_implied_vol_roundtrip():
    f, t, vol = 75.0, 0.386, 0.32
    price = ql.blackFormula(ql.Option.Call, f, f, vol * math.sqrt(t), 1.0)
    assert implied_vol_black76(price, f, f, t) == pytest.approx(vol, abs=1e-6)


def test_implied_vol_normal_roundtrip():
    f, k, t, normal_vol = 30.0, 28.0, 0.33, 11.48
    price = ql.bachelierBlackFormula(ql.Option.Call, k, f, normal_vol * math.sqrt(t), 1.0)
    assert implied_vol_normal(price, f, k, t) == pytest.approx(normal_vol, abs=1e-6)


def test_spread_vol_matches_doc():
    assert spread_vol(31.5, 24.0, 0.95) == pytest.approx(11.48, abs=0.01)


# ---------------- pricing ----------------

def test_bachelier_put_call_parity():
    pricer = make_pricer("bachelier")
    call, put = make_apo("call"), make_apo("put")
    lhs = pricer.pv(call) - pricer.pv(put)
    assert lhs == pytest.approx(pricer.discount_factor(call) * (105.0 - 75.0 - 28.0), abs=1e-10)


def test_kirk_matches_monte_carlo():
    apo = make_apo()
    assert make_pricer("kirk").pv(apo) == pytest.approx(make_pricer("mc").pv(apo), abs=0.05)


def test_futures_style_is_not_discounted():
    pricer = make_pricer()
    upfront, margined = make_apo(), make_apo(premium_style="futures_style")
    assert pricer.discount_factor(margined) == 1.0
    assert pricer.pv(margined) == pytest.approx(pricer.expected_payoff(upfront))
    assert pricer.pv(upfront) < pricer.pv(margined)


def test_with_model_keeps_market():
    pricer = make_pricer("kirk")
    assert pricer.with_model("mc").market is pricer.market


# ---------------- deltas ----------------

def test_kirk_deltas_are_asymmetric():
    d1, d2 = make_pricer("kirk").deltas(make_apo()).values()
    assert d1 > 0 > d2
    assert d1 + d2 > 0          # residual outright exposure, unlike the normal model


def test_bachelier_deltas_are_symmetric():
    d1, d2 = make_pricer("bachelier").deltas(make_apo()).values()
    assert d1 + d2 == pytest.approx(0.0, abs=1e-8)


# ---------------- validation ----------------

def test_accepts_python_dates():
    import datetime as dt
    period = DateRange(start=dt.date(2027, 3, 1), end="2027-03-31")
    assert make_schedule(pricing_period=period).fixing_dates() == make_schedule().fixing_dates()


def test_rejects_invalid_quotes():
    with pytest.raises(ValidationError):
        Quote(-1.0, 0.30)              # negative futures price
    with pytest.raises(ValidationError):
        Quote(105.0, 0.0)              # zero vol


def test_pay_date_follows_pay_lag():
    assert make_schedule().pay_date == ql.Date(8, 4, 2027)          # pay_lag=6
    assert make_schedule(pay_lag=5).pay_date == ql.Date(7, 4, 2027)
    with pytest.raises(ValidationError):
        make_schedule(pay_lag=-1)


def test_rejects_unknown_premium_style():
    with pytest.raises(ValidationError):
        make_apo(premium_style="deferred")


def test_rejects_bad_model_and_correlation():
    with pytest.raises(ValidationError):
        Pricer(model="heston", market=make_market())
    with pytest.raises(ValidationError):
        make_market(rho=1.5)


# ---------------- market data ----------------

def test_market_lookups():
    market = make_market()
    assert market.corr("HO", "BRENT") == market.corr("BRENT", "HO") == 0.95
    assert market.corr("HO", "HO") == 1.0
    with pytest.raises(KeyError, match="WTI"):
        market.forward("WTI")


def test_bump_moves_market_not_trade():
    market = make_market()
    bumped = market.bump_forward("HO", 1.0)
    assert bumped.forward("HO") == 106.0
    assert market.forward("HO") == 105.0          # original snapshot untouched
    assert bumped.forward("BRENT") == 75.0


# ---------------- Monte Carlo helpers ----------------

def test_cholesky_factor_reproduces_correlation():
    corr = np.array([[1.0, 0.95, 0.5], [0.95, 1.0, 0.6], [0.5, 0.6, 1.0]])
    L = cholesky_factor(corr)
    assert np.allclose(L @ L.T, corr)


def test_cholesky_factor_repairs_invalid_matrix():
    bad = np.array([[1.0, 0.9, 0.9], [0.9, 1.0, -0.9], [0.9, -0.9, 1.0]])  # not PD
    with pytest.warns(UserWarning):
        L = cholesky_factor(bad)
    fixed = L @ L.T
    assert np.allclose(np.diag(fixed), 1.0)
    assert np.all(np.linalg.eigvalsh(fixed) > -1e-10)  # nearest valid matrix: semi-definite
    assert fixed[1, 2] == pytest.approx(-0.5, abs=1e-3)  # Higham's nearest correlation


def test_correlated_brownians_have_target_correlation():
    w = correlated_brownians(np.array([0.5, 1.0]), np.array([[1, 0.7], [0.7, 1]]), 100_000, 1)
    assert np.corrcoef(w[:, -1, 0], w[:, -1, 1])[0, 1] == pytest.approx(0.7, abs=0.01)


# ---------------- dates ----------------

def test_date_range_month_and_order():
    mar = DateRange.month(2027, 3)
    assert (mar.start, mar.end) == (ql.Date(1, 3, 2027), ql.Date(31, 3, 2027))
    assert ql.Date(15, 3, 2027) in mar and ql.Date(1, 4, 2027) not in mar
    assert DateRange.month(2028, 2).end == ql.Date(29, 2, 2028)   # leap year
    with pytest.raises(ValidationError):
        DateRange(start="2027-03-31", end="2027-03-01")


def test_is_month():
    assert DateRange.month(2027, 3).is_month()
    assert not DateRange(start="2027-03-01", end="2027-03-15").is_month()
    assert not DateRange(start="2027-03-01", end="2027-04-30").is_month()


def test_pricing_period_must_be_one_month():
    with pytest.raises(ValidationError, match="one whole calendar month"):
        make_schedule(pricing_period=DateRange(start="2027-03-10", end="2027-03-31"))


def test_month_code():
    mar = DateRange.model_validate("2027-03")
    assert mar == DateRange.month(2027, 3)
    assert str(mar) == "2027-03"
    assert str(DateRange.model_validate("2027-12")) == "2027-12"
    assert make_schedule().pricing_period == mar      # schedule accepts "2027-03"
    for bad in ("2027-3", "2027-13", "03-2027", "2027/03"):
        with pytest.raises(ValidationError):
            DateRange.model_validate(bad)


def test_option_type_is_validated_by_its_type():
    from cmdty import OptionType
    assert make_apo("put").option_type is OptionType.PUT
    assert OptionType.PUT.sign == -1.0 and OptionType.CALL.ql == ql.Option.Call
    with pytest.raises(ValidationError):
        make_apo("straddle")


# ---------------- greeks ----------------

def test_greeks_signs_and_consistency():
    g = make_pricer("kirk").greeks(make_apo())
    assert g.delta_crack == pytest.approx((g.delta_leg1 - g.delta_leg2) / 2, abs=1e-3)
    assert g.delta_outright == pytest.approx(g.delta_leg1 + g.delta_leg2, abs=1e-3)
    assert g.gamma_crack > 0 and g.vega_leg1 > 0
    assert g.vega_leg2 < 0           # high rho: more Brent vol, less crack vol
    assert g.corr_sens < 0           # legs cancel more, cheaper option
    assert g.theta < 0 and g.rho < 0


def test_bachelier_greeks_have_no_outright_risk():
    g = make_pricer("bachelier").greeks(make_apo())
    assert g.delta_outright == pytest.approx(0.0, abs=1e-8)
    assert g.gamma_leg1 == pytest.approx(g.gamma_crack, abs=1e-6)


def test_market_bumps():
    m = make_market()
    assert m.bump_vol("HO", 0.01).vol("HO") == pytest.approx(0.31)
    assert m.bump_corr("BRENT", "HO", -0.05).corr("HO", "BRENT") == pytest.approx(0.90)
    assert m.bump_rate(0.0001).rate == pytest.approx(0.0401)
    assert m.roll_to(TODAY + 1).today == TODAY + 1


def test_greek_calculator_one_greek_at_a_time():
    calc = make_pricer("kirk").risk(make_apo())
    g = calc.all()
    assert calc.vega_legs() == pytest.approx((g.vega_leg1, g.vega_leg2))
    assert calc.theta() == pytest.approx(g.theta)
    assert calc.delta_crack() == pytest.approx(g.delta_crack, abs=1e-3)


def test_spread_calculator_inherits_generic_greeks():
    from cmdty import GreekCalculator, SpreadGreekCalculator
    calc = make_pricer("kirk").risk(make_apo())
    assert isinstance(calc, SpreadGreekCalculator) and isinstance(calc, GreekCalculator)
    assert calc.delta("HO") == pytest.approx(calc.delta_legs()[0])     # generic, by name
    assert calc.delta_outright() == pytest.approx(calc.delta("HO") + calc.delta("BRENT"), abs=1e-3)


# ---------------- during the averaging month ----------------

def market_on(today, crack=31.0, fixed_crack=31.0):
    """Forwards give `crack`, every fixing before today gives `fixed_crack` (start of day)."""
    from cmdty.market import to_ql_date
    fix = [d for d in make_schedule().fixing_dates() if d < to_ql_date(today)]
    return MarketData(
        today=today, rate=0.04,
        quotes={"HO": Quote(75.0 + crack, 0.30), "BRENT": Quote(75.0, 0.32)},
        correlations={("HO", "BRENT"): 0.95},
        fixings={"HO": {d: 75.0 + fixed_crack for d in fix}, "BRENT": {d: 75.0 for d in fix}})


def test_past_and_future_fixings_split():
    s = make_schedule()
    today = ql.Date(16, 3, 2027)
    assert len(s.past_fixings(today)) + len(s.future_fixings(today)) == 22
    assert all(d < today for d in s.past_fixings(today))
    assert s.t_eff(ql.Date(1, 4, 2027)) == 0.0


def test_adjusted_strike_formula():
    from cmdty.models.averaging import AveragingState
    state = AveragingState(n=22, m=11, known_average=31.0)
    assert state.weight == 0.5
    assert state.adjusted_strike(28.0) == pytest.approx((22 * 28 - 11 * 31) / 11)


def test_models_agree_mid_month():
    apo = make_apo()
    m = market_on("2027-03-16", crack=29.0, fixed_crack=27.0)
    pvs = [Pricer(model=k, market=m).pv(apo) for k in ("bachelier", "kirk", "mc")]
    assert max(pvs) - min(pvs) < 0.05


def test_delta_decays_through_the_month():
    apo = make_apo()
    d = [Pricer(model="kirk", market=market_on(t)).deltas(apo)["HO"]
         for t in ("2027-03-01", "2027-03-16", "2027-03-31", "2027-04-01")]
    assert d[0] > d[1] > d[2] > d[3] == 0.0


def test_settled_and_paid():
    apo = make_apo()
    m = market_on("2027-04-01", fixed_crack=31.0)          # all 22 fixings known
    pricer = Pricer(model="kirk", market=m)
    assert pricer.expected_payoff(apo) == pytest.approx(3.0)
    assert pricer.with_market(market_on("2027-04-09")).pv(apo) == 0.0   # paid on 8 Apr


def test_missing_fixing_is_an_error():
    apo = make_apo()
    m = market_on("2027-03-16").model_copy(update={"fixings": {}})
    with pytest.raises(KeyError, match="no fixing"):
        Pricer(model="kirk", market=m).pv(apo)


def test_kirk_falls_back_when_deep_in_the_money():
    apo = make_apo()
    m = market_on("2027-03-25", crack=120.0, fixed_crack=120.0)
    with pytest.warns(UserWarning, match="Bachelier"):
        kirk = Pricer(model="kirk", market=m).pv(apo)
    assert kirk == pytest.approx(Pricer(model="bachelier", market=m).pv(apo))


def test_roll_to_fills_skipped_fixings_with_forwards():
    m = market_on("2027-03-16").model_copy(update={"fixings": {}})
    rolled = m.roll_to(ql.Date(18, 3, 2027))
    assert rolled.fixing("HO", ql.Date(16, 3, 2027)) == m.forward("HO")
    assert rolled.fixing("BRENT", ql.Date(17, 3, 2027)) == m.forward("BRENT")


def test_settled_payoff_refuses_partial_average():
    from cmdty.models.averaging import AveragingState, settled_payoff
    with pytest.raises(ValueError, match="11/22"):
        settled_payoff(make_apo(), AveragingState(n=22, m=11, known_average=31.0))
    assert settled_payoff(make_apo(), AveragingState(n=22, m=22, known_average=31.0)) == 3.0


def test_calendars_by_exchange_code():
    from cmdty.market import available_calendars, joint_exchange_calendar
    assert {"NYMEX", "XNYM", "ICE-EU", "IFEU"} <= set(available_calendars())
    by_name = joint_exchange_calendar(["NYMEX", "ICE-EU"])
    by_mic = joint_exchange_calendar(["XNYM", "IFEU"])
    march = (ql.Date(1, 3, 2027), ql.Date(31, 3, 2027))
    assert business_days(by_name, *march) == business_days(by_mic, *march) == make_schedule().fixing_dates()
    with pytest.raises(KeyError, match="ICE"):
        joint_exchange_calendar(["ICE"])          # ambiguous, not in the table


def test_every_calendar_in_the_yaml_resolves():
    from cmdty.market import EXCHANGES, exchange_calendar
    for name, entry in EXCHANGES.items():
        assert {"mic", "function", "days"} <= set(entry), name
        assert isinstance(exchange_calendar(name), ql.Calendar)


# ---------------- legs ----------------

def test_rejects_bad_legs():
    with pytest.raises(ValidationError):
        make_apo(legs=[])                                   # no leg
    with pytest.raises(ValidationError):
        make_apo(legs=[Leg("HO"), Leg("HO", -1)])           # same underlying twice
    with pytest.raises(ValidationError):
        Leg("HO", 0)                                        # zero weight
    with pytest.raises(ValidationError):
        make_apo(quantity=0)


def test_negative_quantity_means_sold():
    assert make_apo(quantity=-10_000).quantity == -10_000


def test_combine_is_the_weighted_sum():
    apo = make_apo(legs=[Leg("HO", 1), Leg("BRENT", -1.1)])
    assert apo.combine({"HO": 105.0, "BRENT": 75.0}) == pytest.approx(105.0 - 82.5)


def test_leg_order_does_not_matter():
    flipped = make_apo(legs=[Leg("BRENT", -1), Leg("HO", 1)])
    for model in ("bachelier", "kirk"):
        assert make_pricer(model).pv(flipped) == pytest.approx(make_pricer(model).pv(make_apo()))
    # MC: same model, other random draws per leg, so only equal up to noise
    assert make_pricer("mc").pv(flipped) == pytest.approx(make_pricer("mc").pv(make_apo()), abs=0.05)


def test_outright_apo_models_agree():
    apo = make_apo(legs=[Leg("BRENT")], strike=75.0)
    pvs = [make_pricer(m).pv(apo) for m in ("bachelier", "mc")]
    assert pvs[0] == pytest.approx(pvs[1], rel=0.03)
    assert set(make_pricer("mc").deltas(apo)) == {"BRENT"}


def test_three_leg_crack():
    market = MarketData(
        today=TODAY, rate=0.04,
        quotes={"RBOB": Quote(95.0, 0.33), "HO": Quote(105.0, 0.30), "WTI": Quote(71.0, 0.32)},
        correlations={("RBOB", "HO"): 0.85, ("RBOB", "WTI"): 0.9, ("HO", "WTI"): 0.9})
    legs = [Leg("RBOB", 2 / 3), Leg("HO", 1 / 3), Leg("WTI", -1)]   # 3-2-1, per bbl of crude
    apo = make_apo(legs=legs, strike=27.0)
    bach, mc = (Pricer(model=m, market=market).pv(apo) for m in ("bachelier", "mc"))
    assert bach == pytest.approx(mc, abs=0.1)
    with pytest.raises(ValueError, match="2 legs"):
        Pricer(model="kirk", market=market).pv(apo)
    assert set(Pricer(model="mc", market=market).deltas(apo)) == {"RBOB", "HO", "WTI"}


def test_today_counts_as_fixed_once_its_settlement_is_published():
    apo, today = make_apo(), ql.Date(16, 3, 2027)
    start_of_day = market_on(today)
    end_of_day = start_of_day.with_fixings("HO", {today: 106.0}).with_fixings("BRENT", {today: 75.0})
    s0 = averaging_state(apo, start_of_day)
    s1 = averaging_state(apo, end_of_day)
    assert (s1.m, s1.today_fixed) == (s0.m + 1, True)
    # same price (fixing = forward), but less delta: today's fixing can no longer move
    p0, p1 = Pricer(market=start_of_day), Pricer(market=end_of_day)
    assert p1.pv(apo) == pytest.approx(p0.pv(apo), abs=1e-3)
    assert p1.deltas(apo)["HO"] < p0.deltas(apo)["HO"]


def test_kirk_prices_an_outright_like_black_on_the_average():
    apo = make_apo(legs=[Leg("BRENT")], strike=72.0, option_type="put")
    kirk, mc = make_pricer("kirk").pv(apo), make_pricer("mc").pv(apo)
    assert kirk == pytest.approx(mc, rel=0.02)
    with pytest.raises(ValueError, match="positive weight"):
        make_pricer("kirk").pv(make_apo(legs=[Leg("BRENT", -1)]))
