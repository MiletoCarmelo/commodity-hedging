import numpy as np
import pandas as pd
import pytest

from cmdty.data import YahooFinanceClient, YahooFinanceError, estimate_market_params, flag_jumps


def synthetic_prices(rho=0.9, vols=(0.30, 0.32), n=750, seed=0, jump_at=None):
    rng = np.random.default_rng(seed)
    z1 = rng.standard_normal(n)
    z2 = rho * z1 + np.sqrt(1 - rho**2) * rng.standard_normal(n)
    r = np.column_stack([z1 * vols[0], z2 * vols[1]]) / np.sqrt(252)
    if jump_at is not None:
        r[jump_at, 0] += 0.12          # contract roll on leg 1
    idx = pd.bdate_range("2024-01-01", periods=n + 1, tz="UTC")
    prices = np.vstack([[100.0, 75.0], np.array([100.0, 75.0]) * np.exp(np.cumsum(r, axis=0))])
    return pd.DataFrame(prices, index=idx, columns=["HO", "BRENT"])


def test_estimation_recovers_parameters():
    p = estimate_market_params(synthetic_prices())
    assert p.rho == pytest.approx(0.9, abs=0.03)
    assert p.vols["HO"] == pytest.approx(0.30, abs=0.03)
    assert p.vols["BRENT"] == pytest.approx(0.32, abs=0.03)


def test_roll_jump_is_flagged_and_removed():
    prices = synthetic_prices(jump_at=400)
    raw = estimate_market_params(prices, jump_threshold=None)
    clean = estimate_market_params(prices)
    assert len(clean.flagged_dates) == 1
    assert clean.flagged_dates[0] == prices.index[401]
    assert raw.vols["HO"] > clean.vols["HO"]          # the jump inflates vol
    assert clean.rho > raw.rho                         # ... and dilutes correlation


def test_flag_jumps_quiet_on_clean_data():
    rets = np.log(synthetic_prices()).diff().dropna()
    assert flag_jumps(rets).sum() == 0


class FakeResponse:
    def __init__(self, payload): self.payload = payload
    def raise_for_status(self): pass
    def json(self): return self.payload


class FakeSession:
    def __init__(self, payload): self.payload, self.headers = payload, {}
    def mount(self, *_): pass
    def get(self, url, params=None, timeout=None): return FakeResponse(self.payload)


def chart(closes, ts):
    return {"chart": {"error": None, "result": [{
        "timestamp": ts, "meta": {"regularMarketPrice": closes[-1]},
        "indicators": {"quote": [{"open": closes, "high": closes, "low": closes,
                                  "close": closes, "volume": [1] * len(closes)}]}}]}}


def test_client_parses_history_and_drops_missing_closes():
    ts = [1735689600, 1735776000, 1735862400]            # 1-3 Jan 2025
    client = YahooFinanceClient(session=FakeSession(chart([74.0, None, 75.5], ts)))
    df = client.history("BZ=F", "2025-01-01", "2025-01-04")
    assert list(df["close"]) == [74.0, 75.5]
    assert client.last_price("BZ=F") == 75.5


def test_client_raises_on_error_payload():
    client = YahooFinanceClient(session=FakeSession({"chart": {"error": "Not Found", "result": None}}))
    with pytest.raises(YahooFinanceError):
        client.history("XXX=F", "2025-01-01")


# ---------------- futures contracts ----------------

def test_month_codes_and_symbols():
    from cmdty.market import contract_symbol, month_code, nearby_contract
    assert month_code(4) == "J" and month_code(5) == "K" and month_code(12) == "Z"
    assert contract_symbol("HO", 2027, 4) == "HOJ27"
    assert nearby_contract(2027, 3, 1) == (2027, 4)     # HO first nearby during Mar-27
    assert nearby_contract(2027, 3, 2) == (2027, 5)     # Brent first line during Mar-27
    assert nearby_contract(2026, 12, 2) == (2027, 2)    # year rollover
    assert YahooFinanceClient.futures_ticker("BZ", 2027, 5) == "BZK27.NYM"


class RoutingSession(FakeSession):
    """Empty result for dated contracts, data for the front month."""
    def __init__(self, front_payload):
        super().__init__(front_payload)

    def get(self, url, params=None, timeout=None):
        if url.endswith("=F"):
            return FakeResponse(self.payload)
        return FakeResponse({"chart": {"error": "Not Found", "result": None}})


def test_futures_price_uses_dated_contract_when_available():
    client = YahooFinanceClient(session=FakeSession(chart([2.61], [1735689600])))
    assert client.futures_price("HO", 2027, 4) == (2.61, "HOJ27.NYM")


def test_futures_price_falls_back_to_front_month():
    client = YahooFinanceClient(session=RoutingSession(chart([2.40], [1735689600])))
    with pytest.warns(UserWarning, match="HOJ27.NYM"):
        price, ticker = client.futures_price("HO", 2027, 4)
    assert (price, ticker) == (2.40, "HO=F")
