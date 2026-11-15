"""Types shared by instruments."""

from enum import Enum

import QuantLib as ql


class OptionType(str, Enum):
    """Call or put. Pydantic rejects any other value."""

    CALL = "call"
    PUT = "put"

    @property
    def ql(self) -> int:
        """QuantLib constant, for ql formulas and payoffs."""
        return ql.Option.Call if self is OptionType.CALL else ql.Option.Put

    @property
    def sign(self) -> float:
        """+1 for a call, -1 for a put: payoff = max(sign * (A - K), 0)."""
        return 1.0 if self is OptionType.CALL else -1.0
