import copy
from pathlib import Path

import pytest
import QuantLib as ql
import yaml

from cmdty import APO, MarketData, Pricer, Quote, load_portfolio
from cmdty.portfolio import _portfolio_from_dict

EXAMPLE = Path(__file__).parents[1] / "portfolios" / "example_book.yaml"
DATA = yaml.safe_load(EXAMPLE.read_text())


def edited(**changes):
    """Copy of the example with the first trade changed."""
    data = copy.deepcopy(DATA)
    data["trades"][0].update(changes)
    return data


def test_example_portfolio_loads_and_prices():
    book = load_portfolio(EXAMPLE)
    assert book.name == "example-book" and len(book) == 3
    outright, spread, crack = (book.trade(i).instrument for i in ("APO-001", "APO-002", "APO-003"))
    assert all(isinstance(a, APO) for a in (outright, spread, crack))
    assert outright.underlyings == ["BRENT"] and outright.quantity == 20_000
    assert spread.strike == -4.0 and spread.premium_style == "futures_style"
    assert crack.quantity == -25_000 and crack.underlyings == ["HO", "BRENT"]
    assert len(crack.schedule.fixing_dates()) == 21        # NYMEX closed on 18 June (Juneteenth)
    assert ql.Date(18, 6, 2027) not in crack.schedule.fixing_dates()
    market = MarketData(today=ql.Date(10, 11, 2026), rate=0.04,
                        quotes={"HO": Quote(105.0, 0.30), "BRENT": Quote(75.0, 0.32),
                                "WTI": Quote(71.0, 0.33)},
                        correlations={("HO", "BRENT"): 0.95, ("WTI", "BRENT"): 0.97,
                                      ("HO", "WTI"): 0.93})
    for trade in book:
        assert Pricer(market=market).pv(trade.instrument) > 0


def test_mic_and_name_give_the_same_calendar():
    data = copy.deepcopy(DATA)
    data["trades"][2]["schedule"]["calendar"] = ["XNYM", "IFEU"]
    dates = _portfolio_from_dict(data).trade("APO-003").instrument.schedule.fixing_dates()
    assert dates == load_portfolio(EXAMPLE).trade("APO-003").instrument.schedule.fixing_dates()


@pytest.mark.parametrize("calendar", [["NYMEX", "NYMEX"], ["NYMEX", "XNYM"], ["MOON"], []])
def test_rejects_bad_calendars(calendar):
    data = copy.deepcopy(DATA)
    data["trades"][0]["schedule"]["calendar"] = calendar
    with pytest.raises(ValueError, match="APO-001"):
        _portfolio_from_dict(data)


def test_rejects_unknown_type_typo_and_duplicate_ids():
    with pytest.raises(ValueError, match="unknown type"):
        _portfolio_from_dict(edited(type="swaption"))
    with pytest.raises(ValueError, match="APO-001"):
        _portfolio_from_dict(edited(strik=28.0))             # typo in a field name
    data = copy.deepcopy(DATA)
    data["trades"].append(copy.deepcopy(data["trades"][0]))
    with pytest.raises(ValueError, match="duplicate trade ids"):
        _portfolio_from_dict(data)
