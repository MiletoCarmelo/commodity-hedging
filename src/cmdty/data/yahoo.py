"""Yahoo Finance client (chart API v8): daily futures history and last prices."""

from __future__ import annotations

import logging
import warnings
from datetime import date, datetime, timezone

import pandas as pd
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from ..market.futures import contract_symbol

logger = logging.getLogger(__name__)

DateLike = str | date | datetime

# =============================================================================
# 1. Helpers
# =============================================================================


class YahooFinanceError(RuntimeError):
    """Raised when Yahoo Finance returns no usable data."""


def _to_unix(d: DateLike) -> int:
    """Date, datetime or 'YYYY-MM-DD' to a Unix timestamp (UTC)."""
    if isinstance(d, str):
        d = datetime.strptime(d, "%Y-%m-%d")
    if isinstance(d, date) and not isinstance(d, datetime):
        d = datetime(d.year, d.month, d.day)
    return int(d.replace(tzinfo=d.tzinfo or timezone.utc).timestamp())


# =============================================================================
# 2. Yahoo client
# =============================================================================


class YahooFinanceClient:
    """Thin client with retries and explicit errors (adapted from the QuanTa project)."""

    BASE_URL = "https://query1.finance.yahoo.com/v8/finance/chart"
    USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"

    def __init__(
        self, timeout: float = 10.0, retries: int = 3, session: requests.Session | None = None
    ) -> None:
        """HTTP session that retries on rate limits (429) and server errors (5xx)."""
        self.timeout = timeout
        self.session = session or requests.Session()
        self.session.headers.update({"User-Agent": self.USER_AGENT})
        retry = Retry(
            total=retries,
            backoff_factor=0.5,
            status_forcelist=(429, 500, 502, 503, 504),
            allowed_methods=("GET",),
        )
        self.session.mount("https://", HTTPAdapter(max_retries=retry))

    def _chart(self, symbol: str, params: dict) -> dict:
        """Raw chart payload of one ticker; raises YahooFinanceError if empty."""
        url = f"{self.BASE_URL}/{symbol}"
        logger.debug("GET %s %s", url, params)
        try:
            response = self.session.get(url, params=params, timeout=self.timeout)
            response.raise_for_status()
        except requests.RequestException as exc:
            raise YahooFinanceError(f"{symbol}: request failed ({exc})") from exc
        payload = response.json().get("chart", {})
        if payload.get("error") or not payload.get("result"):
            raise YahooFinanceError(f"{symbol}: {payload.get('error') or 'empty result'}")
        return payload["result"][0]

    # --- prices ---
    def history(
        self, symbol: str, start: DateLike, end: DateLike | None = None, interval: str = "1d"
    ) -> pd.DataFrame:
        """OHLCV history indexed by date (UTC), rows without a close removed."""
        params = {
            "interval": interval,
            "period1": _to_unix(start),
            "period2": _to_unix(end or datetime.now(timezone.utc)),
        }
        result = self._chart(symbol, params)
        timestamps = result.get("timestamp") or []
        quote = (result.get("indicators", {}).get("quote") or [{}])[0]
        if not timestamps:
            raise YahooFinanceError(f"{symbol}: no data between {start} and {end}")
        df = pd.DataFrame(
            {k: quote.get(k) for k in ("open", "high", "low", "close", "volume")},
            index=pd.to_datetime(timestamps, unit="s", utc=True).normalize(),
        )
        df.index.name = "date"
        df = df.dropna(subset=["close"])
        df = df[~df.index.duplicated(keep="last")]
        logger.info("%s: %d rows %s -> %s", symbol, len(df), df.index[0].date(), df.index[-1].date())
        return df

    def closes(
        self,
        symbols: dict[str, str],
        start: DateLike,
        end: DateLike | None = None,
        multipliers: dict[str, float] | None = None,
    ) -> pd.DataFrame:
        """Closes of several tickers on common dates, e.g. {"HO": "HO=F"}, {"HO": 42.0}."""
        multipliers = multipliers or {}
        series = {
            name: self.history(ticker, start, end)["close"] * multipliers.get(name, 1.0)
            for name, ticker in symbols.items()
        }
        return pd.concat(series, axis=1, join="inner").sort_index()

    def last_price(self, symbol: str) -> float:
        """Latest price of one ticker."""
        meta = self._chart(symbol, {"range": "1d", "interval": "1d"}).get("meta", {})
        price = meta.get("regularMarketPrice")
        if price is None:
            raise YahooFinanceError(f"{symbol}: no regularMarketPrice")
        return float(price)

    # --- futures contracts ---
    @staticmethod
    def futures_ticker(root: str, year: int, month: int, exchange: str = "NYM") -> str:
        """Yahoo ticker of a dated contract, e.g. ('HO', 2027, 4) -> 'HOJ27.NYM'."""
        return f"{contract_symbol(root, year, month)}.{exchange}"

    def futures_price(
        self, root: str, year: int, month: int, exchange: str = "NYM"
    ) -> tuple[float, str]:
        """(price, ticker used) of a dated contract, front month if Yahoo lacks it."""
        ticker = self.futures_ticker(root, year, month, exchange)
        try:
            return self.last_price(ticker), ticker
        except YahooFinanceError:
            fallback = f"{root}=F"
            warnings.warn(f"{ticker} not available on Yahoo, using front month {fallback}")
            return self.last_price(fallback), fallback
