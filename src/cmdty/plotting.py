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
# 4. Option curves: one panel per greek, against the future price
# =============================================================================

_GREEKS = {  # name: (colour, y label, subtitle)
    "delta": (SERIES[1], "delta", "slope of the value: an S from 0 to 1 (call)"),
    "gamma": (SERIES[2], "gamma", "slope of the delta: a bell, largest near the strike"),
    "vega": (SERIES[3], "vega, $ per vol point", "a bell, largest near the strike"),
    "theta": (SERIES[0], "theta, $ per day", "a bell upside down for a bought option"),
}


def option_value(ax, F, value, *, f0: float, payoff=None, tangent=None,
                 tangent_label: str = "delta approximation") -> None:
    """Option value today, with optional payoff at expiry and tangent at f0."""
    if payoff is not None:
        ax.plot(F, payoff, color=MUTED, linewidth=1.3, linestyle=(0, (4, 3)), label="at expiry")
    ax.plot(F, value, color=SERIES[0], linewidth=2, label="today")
    if tangent is not None:
        ax.plot(F, tangent, color=SERIES[1], linewidth=1.2, label=tangent_label)
    ax.set(ylabel="value, $/bbl", xlabel="future price, $/bbl",
           ylim=(min(value) - 2, max(value) * 1.1))
    ax.set_axisbelow(True)
    ax.axvline(f0, color=MUTED, linewidth=1, linestyle=(0, (4, 3)))
    ax.legend(frameon=False, loc="upper left")
    titles(ax, "Value", "flat on one side, slope 1 on the other, a curve in between")


def greek_curve(ax, F, y, greek: str, *, f0: float) -> None:
    """One greek ('delta', 'gamma', 'vega' or 'theta') against the future price."""
    color, ylabel, subtitle = _GREEKS[greek]
    ax.plot(F, y, color=color, linewidth=2)
    ax.axhline(0, color=MUTED, linewidth=1)
    ax.axvline(f0, color=MUTED, linewidth=1, linestyle=(0, (4, 3)))
    ax.set(ylabel=ylabel, xlabel="future price, $/bbl")
    ax.set_axisbelow(True)
    titles(ax, greek.capitalize(), subtitle)


def option_curves(F, value, greeks: dict, *, f0: float, payoff=None, tangent=None,
                  tangent_label: str = "delta approximation"):
    """Value on top, then one panel per greek in `greeks` ({'delta': array, ...})."""
    n = 1 + len(greeks)
    fig, axes = plt.subplots(n, 1, figsize=(8, 3.2 * n), sharex=True)
    option_value(axes[0], F, value, f0=f0, payoff=payoff, tangent=tangent,
                 tangent_label=tangent_label)
    for ax, (name, y) in zip(axes[1:], greeks.items()):
        greek_curve(ax, F, y, name, f0=f0)
    for ax in axes[:-1]:
        ax.set_xlabel("")
    fig.tight_layout(h_pad=2)
    return fig, axes
