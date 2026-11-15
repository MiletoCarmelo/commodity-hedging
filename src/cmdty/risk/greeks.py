"""Sensitivities by central finite differences: bump the market, never the trade."""

from dataclasses import asdict, dataclass
from typing import TYPE_CHECKING

from ..models.bachelier import spread_normal_vol

if TYPE_CHECKING:  # avoid a circular import, only for type hints
    from ..market.market_data import MarketData
    from ..pricer import Pricer

# =============================================================================
# 1. Results
# =============================================================================


@dataclass(frozen=True)
class Greeks:
    """All sensitivities of a two-leg spread, per unit ($/bbl)."""

    pv: float
    delta_leg1: float  # per +1 $ on leg 1
    delta_leg2: float  # per +1 $ on leg 2
    delta_crack: float  # per +1 $ on the crack (leg 1 +0.5, leg 2 -0.5)
    delta_outright: float  # per +1 $ on both legs together
    gamma_leg1: float  # change of delta per $
    gamma_leg2: float
    gamma_crack: float
    vega_leg1: float  # per +1 vol point
    vega_leg2: float
    corr_sens: float  # per +0.01 correlation
    theta: float  # one calendar day passing, same market
    rho: float  # per +1 bp on the discount rate

    def to_dict(self) -> dict:
        return asdict(self)


# =============================================================================
# 2. Generic calculator: any instrument, greeks per underlying
# =============================================================================


class GreekCalculator:
    """Bump-and-reprice greeks per underlying, for any instrument the pricer handles."""

    def __init__(self, pricer: "Pricer", instrument, h: float = 0.5) -> None:
        """h: forward bump in $ used for gammas."""
        self.pricer = pricer
        self.instrument = instrument
        self.h = h
        self.market = pricer.market
        self.forward_pricer = pricer  # pricer used when forwards move (hook for subclasses)

    # --- repricing ---
    def pv(self, market: "MarketData | None" = None, pricer: "Pricer | None" = None) -> float:
        """PV of the instrument on a (bumped) market snapshot."""
        pricer = pricer or self.pricer
        return pricer.with_market(market or self.market).pv(self.instrument)

    def _first(self, up: "MarketData", down: "MarketData", step: float, pricer=None) -> float:
        """Central first derivative."""
        return (self.pv(up, pricer) - self.pv(down, pricer)) / (2 * step)

    def _second(self, up: "MarketData", down: "MarketData", step: float) -> float:
        """Central second derivative, forwards moved."""
        p = self.forward_pricer
        return (self.pv(up, p) - 2 * self.pv(pricer=p) + self.pv(down, p)) / step**2

    # --- delta ---
    def deltas(self, h: float = 0.01) -> dict[str, float]:
        """Delta of every leg, by underlying. What the hedging bot nets."""
        return {u: self.delta(u, h) for u in self.instrument.underlyings}

    def delta(self, underlying: str, h: float = 0.01) -> float:
        """dPV/dF of one underlying, per +1 $."""
        m = self.market
        up, down = m.bump_forward(underlying, h), m.bump_forward(underlying, -h)
        return self._first(up, down, h, self.forward_pricer)

    # --- gamma ---
    def gamma(self, underlying: str) -> float:
        """Change of the delta of one underlying per $."""
        m, h = self.market, self.h
        return self._second(m.bump_forward(underlying, h), m.bump_forward(underlying, -h), h)

    def cross_gamma(self, a: str, b: str) -> float:
        """d2PV / dFa dFb: how the delta of a moves when b moves. Equals gamma(a) when a == b."""
        if a == b:
            return self.gamma(a)
        m, h, p = self.market, self.h, self.forward_pricer

        def pv(ha: float, hb: float) -> float:
            return self.pv(m.bump_forward(a, ha).bump_forward(b, hb), p)

        return (pv(h, h) - pv(h, -h) - pv(-h, h) + pv(-h, -h)) / (4 * h**2)

    # --- vega ---
    def vega(self, underlying: str, bump: float = 0.01) -> float:
        """PV change per +1 vol point on one underlying."""
        m = self.market
        return (self.pv(m.bump_vol(underlying, bump)) - self.pv(m.bump_vol(underlying, -bump))) / 2

    # --- theta ---
    def theta(self, days: int = 1) -> float:
        """PV change when `days` calendar days pass, same quotes."""
        return self.pv(self.market.roll_to(self.market.today + days)) - self.pv()

    # --- rho ---
    def rho(self, bump: float = 0.0001) -> float:
        """PV change per +1 bp on the discount rate."""
        m = self.market
        return (self.pv(m.bump_rate(bump)) - self.pv(m.bump_rate(-bump))) / 2


# =============================================================================
# 3. Spread calculator: adds crack, outright and correlation greeks
# =============================================================================


class SpreadGreekCalculator(GreekCalculator):
    """Greeks of a two-leg spread: everything above, plus spread-only sensitivities."""

    def __init__(self, pricer: "Pricer", apo, h: float = 0.5) -> None:
        if len(apo.legs) != 2:
            raise ValueError(f"spread greeks need 2 legs, got {len(apo.legs)}")
        super().__init__(pricer, apo, h)
        self.u1, self.u2 = apo.underlyings
        # Bachelier: keep the $ normal vol fixed when forwards move (symmetric deltas)
        if pricer.model == "bachelier" and "normal_vol" not in pricer.model_kwargs:
            normal_vol = spread_normal_vol(apo, self.market)
            self.forward_pricer = pricer.with_model_kwargs(normal_vol=normal_vol)

    def _legs_bump(self, h1: float, h2: float) -> "MarketData":
        """Market with leg 1 moved by h1 and leg 2 by h2."""
        return self.market.bump_forward(self.u1, h1).bump_forward(self.u2, h2)

    # --- per leg (generic greeks, both legs) ---
    def delta_legs(self, h: float = 0.01) -> tuple[float, float]:
        return self.delta(self.u1, h), self.delta(self.u2, h)

    def gamma_legs(self) -> tuple[float, float]:
        return self.gamma(self.u1), self.gamma(self.u2)

    def vega_legs(self, bump: float = 0.01) -> tuple[float, float]:
        return self.vega(self.u1, bump), self.vega(self.u2, bump)

    # --- spread only ---
    def delta_crack(self, h: float = 0.01) -> float:
        """Per +1 $ on the crack: leg 1 up half, leg 2 down half."""
        up, down = self._legs_bump(h / 2, -h / 2), self._legs_bump(-h / 2, h / 2)
        return self._first(up, down, h, self.forward_pricer)

    def delta_outright(self, h: float = 0.01) -> float:
        """Per +1 $ on both legs together: flat price risk left after the crack hedge."""
        return self._first(self._legs_bump(h, h), self._legs_bump(-h, -h), h, self.forward_pricer)

    def gamma_crack(self) -> float:
        """Change of the crack delta per $ of crack."""
        h = self.h
        return self._second(self._legs_bump(h / 2, -h / 2), self._legs_bump(-h / 2, h / 2), h)

    def corr_sens(self, bump: float = 0.01) -> float:
        """PV change per +0.01 correlation between the legs."""
        m = self.market
        up, down = m.bump_corr(self.u1, self.u2, bump), m.bump_corr(self.u1, self.u2, -bump)
        return (self.pv(up) - self.pv(down)) / 2

    # --- all ---
    def all(self) -> Greeks:
        """Every sensitivity in one object."""
        h = self.h
        d1, d2 = self.delta_legs(h)
        g1, g2 = self.gamma_legs()
        v1, v2 = self.vega_legs()
        return Greeks(
            pv=self.pv(),
            delta_leg1=d1, delta_leg2=d2,
            delta_crack=self.delta_crack(h), delta_outright=self.delta_outright(h),
            gamma_leg1=g1, gamma_leg2=g2, gamma_crack=self.gamma_crack(),
            vega_leg1=v1, vega_leg2=v2,
            corr_sens=self.corr_sens(), theta=self.theta(), rho=self.rho(),
        )
