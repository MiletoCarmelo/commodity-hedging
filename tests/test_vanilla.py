"""Vanilla options (Black-76 with QuantLib) and options strategies."""

import QuantLib as ql
import pytest

from cmdty import MarketData, Pricer, Quote, VanillaOption
from cmdty.models.black76 import analytic_greeks
from cmdty.portfolio import _portfolio_from_dict
from cmdty.risk import book_risk
from cmdty.strategies import butterfly, option, position_greeks, straddle

TODAY = ql.Date(25, 11, 2026)
EXPIRY = "2027-02-25"


@pytest.fixture
def pricer():
    market = MarketData(today=TODAY, rate=0.04, quotes={"BRENT": Quote(75.0, 0.32)})
    return Pricer(model="kirk", market=market)


def vanilla(k=75.0, kind="call", qty=1.0):
    return VanillaOption(underlying="BRENT", contract="2027-03", expiry=EXPIRY, strike=k,
                         option_type=kind, quantity=qty)


def test_price_matches_quantlib_black_formula(pricer):
    opt = vanilla(80.0)
    t = ql.Actual365Fixed().yearFraction(TODAY, ql.Date(25, 2, 2027))
    expected = ql.blackFormula(ql.Option.Call, 80.0, 75.0, 0.32 * t**0.5)
    assert pricer.expected_payoff(opt) == pytest.approx(expected)


def test_put_call_parity(pricer):
    c, p = pricer.expected_payoff(vanilla(70.0)), pricer.expected_payoff(vanilla(70.0, "put"))
    assert c - p == pytest.approx(75.0 - 70.0)


def test_bump_greeks_match_analytic(pricer):
    opt = vanilla(78.0)
    calc, a = pricer.risk(opt), analytic_greeks(opt, pricer.market)
    df = pricer.discount_factor(opt)
    assert calc.delta("BRENT") == pytest.approx(df * a.delta, rel=1e-4)
    assert calc.gamma("BRENT") == pytest.approx(df * a.gamma, rel=1e-3)
    assert calc.vega("BRENT") == pytest.approx(df * a.vega, rel=1e-3)


@pytest.mark.parametrize("kind, qty, signs", [
    ("call", +1, (+1, +1, +1, -1)),  # long call: long delta, long gamma, long vega, pays theta
    ("put", +1, (-1, +1, +1, -1)),
    ("call", -1, (-1, -1, -1, +1)),
    ("put", -1, (+1, -1, -1, +1)),
])
def test_greek_signs_of_the_building_blocks(pricer, kind, qty, signs):
    g = position_greeks([option("x", "BRENT", "2027-03", EXPIRY, 75.0, kind, qty)],
                        pricer, "BRENT")
    assert tuple(1 if x > 0 else -1 for x in (g.delta, g.gamma, g.vega, g.theta)) == signs


def test_long_straddle_is_long_gamma_without_direction(pricer):
    g = position_greeks(straddle("BRENT", "2027-03", EXPIRY, 75.0, 1.0), pricer, "BRENT")
    assert abs(g.delta) < 0.1 and g.gamma > 0 and g.vega > 0 and g.theta < 0


def test_butterfly_bought_is_short_gamma_at_the_middle(pricer):
    g = position_greeks(butterfly("BRENT", "2027-03", EXPIRY, 65.0, 75.0, 85.0, 1.0),
                        pricer, "BRENT")
    assert g.gamma < 0 and g.vega < 0 and g.theta > 0


def test_expired_option_is_worth_nothing(pricer):
    later = pricer.with_market(pricer.market.roll_to(ql.Date(1, 3, 2027)))
    assert later.pv(vanilla()) == 0.0


def test_vanilla_from_yaml_hedges_its_own_contract(pricer):
    book = _portfolio_from_dict({"portfolio": "b", "trades": [
        {"id": "C1", "type": "vanilla", "underlying": "BRENT", "contract": "2027-03",
         "expiry": EXPIRY, "strike": 75.0, "option_type": "call", "quantity": 1000}]})
    risk = book_risk(book, pricer)
    assert list(risk.deltas_by_contract) == [("BRENT", "2027-03")]
    assert risk.deltas["BRENT"] == pytest.approx(risk.deltas_by_contract[("BRENT", "2027-03")])
