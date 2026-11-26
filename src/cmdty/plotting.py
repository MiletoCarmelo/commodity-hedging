"""Dark, terminal-like chart style for the notebooks (matplotlib only)."""

import matplotlib.pyplot as plt
from cycler import cycler

# =============================================================================
# 1. Palette (dark-mode steps, validated for colour-blind separation)
# =============================================================================

SURFACE = "#1a1a19"
TEXT = "#f0efec"
MUTED = "#c3c2b7"
GRID = "#2f2f2c"
SERIES = ["#3987e5", "#d95926", "#199e70", "#c98500"]  # blue, orange, aqua, yellow

# =============================================================================
# 2. Style
# =============================================================================


def use_style() -> None:
    """Apply the dark style to every chart that follows."""
    plt.rcParams.update({
        "figure.facecolor": SURFACE,
        "axes.facecolor": SURFACE,
        "savefig.facecolor": SURFACE,
        "figure.dpi": 110,
        "font.size": 10,
        "text.color": TEXT,
        "axes.labelcolor": MUTED,
        "axes.edgecolor": GRID,
        "axes.prop_cycle": cycler(color=SERIES),
        "axes.spines.top": False,
        "axes.spines.right": False,
        "axes.spines.left": False,
        "axes.grid": True,
        "axes.grid.axis": "y",
        "grid.color": GRID,
        "grid.linewidth": 0.8,
        "xtick.color": MUTED,
        "ytick.color": MUTED,
        "xtick.major.size": 0,
        "ytick.major.size": 0,
        "lines.linewidth": 2,
        "legend.frameon": False,
        "legend.labelcolor": MUTED,
    })


# =============================================================================
# 3. Chart helpers
# =============================================================================


def titles(ax, title: str, subtitle: str | None = None) -> None:
    """Bold title on the left, optional muted subtitle under it."""
    ax.set_title(title, loc="left", fontsize=13, fontweight="bold", color=TEXT,
                 pad=24 if subtitle else 10)
    if subtitle:
        ax.text(0, 1.03, subtitle, transform=ax.transAxes, color=MUTED, fontsize=9)


def price_axis_right(ax) -> None:
    """Values on the right, as on trading screens."""
    ax.yaxis.tick_right()
    ax.yaxis.set_label_position("right")


def area_line(ax, x, y, color: str = SERIES[0], label: str | None = None, base=None) -> None:
    """Line with a light fill down to `base` (default: lowest value)."""
    ax.plot(x, y, color=color, label=label)
    ax.fill_between(x, y, min(y) if base is None else base, color=color, alpha=0.15, linewidth=0)


def last_value(ax, x, y, color: str = SERIES[0], fmt: str = "{:.2f}") -> None:
    """Dot on the last point and its value in a coloured tag."""
    left, right = ax.get_xlim()
    ax.set_xlim(left, right + 0.08 * (right - left))  # room for the tag before the axis
    ax.scatter([x], [y], color=color, s=28, zorder=5, edgecolors=SURFACE, linewidths=1.5)
    ax.annotate(fmt.format(y), xy=(x, y), xytext=(10, 0), textcoords="offset points",
                va="center", fontsize=9, fontweight="bold", color=SURFACE,
                bbox=dict(boxstyle="round,pad=0.3", fc=color, ec="none"))


def ref_line(ax, y: float, label: str, color: str = MUTED) -> None:
    """Dashed horizontal reference with its label at the left edge."""
    ax.axhline(y, color=color, linewidth=1, linestyle=(0, (4, 3)), zorder=1)
    ax.annotate(label, xy=(0, y), xycoords=("axes fraction", "data"), xytext=(4, 0),
                textcoords="offset points", va="center", color=color, fontsize=9, zorder=6,
                bbox=dict(boxstyle="round,pad=0.25", fc=SURFACE, ec="none"))


def ref_vline(ax, x: float, label: str, color: str = MUTED) -> None:
    """Dashed vertical reference with its label at the top."""
    ax.axvline(x, color=color, linewidth=1, linestyle=(0, (4, 3)), zorder=1)
    ax.annotate(label, xy=(x, 1), xycoords=("data", "axes fraction"), xytext=(4, -12),
                textcoords="offset points", color=color, fontsize=9)


# =============================================================================
# 4. Option curves: value and greeks, against the future price or the maturity
# =============================================================================


def plot_curves(x, curves, *, title: str, subtitle: str | None = None, ylabel: str = "",
                f0: float | None = None, payoff=None, color: str | None = None,
                marker: str | None = None, xlabel: str = "future price, $/bbl", ax=None):
    """One or several curves.

    `curves` is an array, or a dict {label: array} for several lines with a legend. `payoff`
    is drawn dashed (value at expiry); `f0`, if given, is marked by a dashed vertical line.
    """
    if ax is None:
        _, ax = plt.subplots(figsize=(8, 4))
    if not isinstance(curves, dict):
        curves = {None: curves}
    if payoff is not None:
        ax.plot(x, payoff, color=MUTED, linewidth=1.3, linestyle=(0, (4, 3)), label="at expiry")
    colors = [color] if color and len(curves) == 1 else SERIES
    for c, (label, y) in zip(colors, curves.items()):
        ax.plot(x, y, color=c, linewidth=2, marker=marker, label=label)
    ax.set_axisbelow(True)
    ax.axhline(0, color=MUTED, linewidth=1)
    if f0 is not None:
        ax.axvline(f0, color=MUTED, linewidth=1, linestyle=(0, (4, 3)))
    ax.set(xlabel=xlabel, ylabel=ylabel)
    if payoff is not None or len(curves) > 1:
        ax.legend(frameon=False, loc="upper left")
    titles(ax, title, subtitle)
    return ax


def plot_value(x, curves, *, title="Value", **kw):
    """Option value, $/bbl. Same arguments as plot_curves."""
    return plot_curves(x, curves, title=title, ylabel="value, $/bbl", **kw)


def plot_delta(x, curves, *, title="Delta", **kw):
    """Delta: change in value per 1 $ on the future."""
    return plot_curves(x, curves, title=title, ylabel="delta", color=SERIES[1], **kw)


def plot_gamma(x, curves, *, title="Gamma", **kw):
    """Gamma: change in delta per 1 $ on the future."""
    return plot_curves(x, curves, title=title, ylabel="gamma", color=SERIES[2], **kw)


def plot_vega(x, curves, *, title="Vega", **kw):
    """Vega: change in value per vol point, $/bbl."""
    return plot_curves(x, curves, title=title, ylabel="vega, $ per vol point",
                       color=SERIES[3], **kw)


def plot_theta(x, curves, *, title="Theta", **kw):
    """Theta: change in value per day, $/bbl."""
    return plot_curves(x, curves, title=title, ylabel="theta, $ per day", color=SERIES[0], **kw)
