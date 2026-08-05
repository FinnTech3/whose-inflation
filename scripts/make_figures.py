"""Generates the figures in docs/figures from the committed CPI data.

Every number is computed here rather than typed in, so a chart cannot drift
away from the analysis. CI regenerates these and fails on any difference.

    python3 scripts/make_figures.py
"""

from __future__ import annotations

import statistics
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from whoseinflation.baskets import ALL_BASKETS, OFFICIAL, by_name  # noqa: E402
from whoseinflation.index import basket_history  # noqa: E402
from whoseinflation.series import load  # noqa: E402

OUT = ROOT / "docs" / "figures"
DATA = ROOT / "src" / "whoseinflation" / "data" / "cpi_u_groups_2017_2026.json"
CALM, HOT = 0.03, 0.05


@dataclass(frozen=True)
class Theme:
    name: str
    surface: str
    text_primary: str
    text_secondary: str
    muted: str
    gridline: str
    baseline: str
    high: str
    low: str
    band: str
    ramp: tuple[str, str, str]


LIGHT = Theme("light", "#fcfcfb", "#0b0b0b", "#52514e", "#898781",
              "#e1e0d9", "#c3c2b7", "#eb6834", "#2a78d6", "#898781",
              ("#86b6ef", "#3987e5", "#1c5cab"))
DARK = Theme("dark", "#1a1a19", "#ffffff", "#c3c2b7", "#898781",
             "#2c2c2a", "#383835", "#d95926", "#3987e5", "#898781",
             ("#86b6ef", "#3987e5", "#1c5cab"))

FONT = "system-ui,-apple-system,'Segoe UI',sans-serif"


def esc(t: str) -> str:
    return t.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def band_chart(months, official, high, low, theme: Theme) -> str:
    """The spread between the extreme households, as a filled band.

    The band is the argument. A reader does not need to trace two lines and
    subtract them; the shaded area between them widens visibly in 2021 and
    2022 and closes again, which is the entire finding in one shape.
    """
    width, height = 820, 400
    left, right, top, bottom = 58, 208, 78, 56
    plot_w, plot_h = width - left - right, height - top - bottom

    every = list(high.values()) + list(low.values()) + list(official.values())
    lo_v, hi_v = min(every), max(every)
    pad = (hi_v - lo_v) * 0.12
    lo_v, hi_v = lo_v - pad, hi_v + pad

    def y(v: float) -> float:
        return top + plot_h - (v - lo_v) / (hi_v - lo_v) * plot_h

    def x(i: int) -> float:
        return left + i / max(len(months) - 1, 1) * plot_w

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" '
        f'height="{height}" viewBox="0 0 {width} {height}" '
        f'font-family="{FONT}" role="img" '
        f'aria-label="Year-on-year inflation for a car-dependent commuter and '
        f'a student, with the published CPI between them. The gap between the '
        f'two households widens sharply during 2021 and 2022.">',
        f'<rect width="{width}" height="{height}" fill="{theme.surface}"/>',
        f'<text x="{left}" y="32" font-size="15" font-weight="600" '
        f'fill="{theme.text_primary}">One headline, two households</text>',
        f'<text x="{left}" y="52" font-size="12" fill="{theme.text_secondary}">'
        f'The shaded band is the disagreement. It opens when inflation '
        f'rises.</text>',
    ]

    for pct in range(0, 13, 2):
        v = pct / 100
        if not (lo_v <= v <= hi_v):
            continue
        gy = y(v)
        parts.append(
            f'<line x1="{left}" y1="{gy:.1f}" x2="{left + plot_w}" '
            f'y2="{gy:.1f}" stroke="{theme.gridline}" stroke-width="1"/>'
        )
        parts.append(
            f'<text x="{left - 10}" y="{gy + 4:.1f}" font-size="11" '
            f'fill="{theme.muted}" text-anchor="end">{pct}%</text>'
        )

    upper = " ".join(f"{x(i):.1f},{y(high[m]):.1f}" for i, m in enumerate(months))
    lower = " ".join(
        f"{x(i):.1f},{y(low[m]):.1f}" for i, m in reversed(list(enumerate(months)))
    )
    parts.append(
        f'<polygon points="{upper} {lower}" fill="{theme.high}" opacity="0.16"/>'
    )

    for values, colour in ((high, theme.high), (low, theme.low)):
        points = " ".join(f"{x(i):.1f},{y(values[m]):.1f}" for i, m in enumerate(months))
        parts.append(
            f'<polyline fill="none" stroke="{colour}" stroke-width="2" '
            f'stroke-linejoin="round" points="{points}"/>'
        )
        parts.append(
            f'<circle cx="{x(len(months) - 1):.1f}" '
            f'cy="{y(values[months[-1]]):.1f}" r="4" fill="{colour}" '
            f'stroke="{theme.surface}" stroke-width="1.5"/>'
        )

    published = " ".join(
        f"{x(i):.1f},{y(official[m]):.1f}" for i, m in enumerate(months)
    )
    parts.append(
        f'<polyline fill="none" stroke="{theme.text_primary}" stroke-width="1.5" '
        f'stroke-dasharray="5 3" points="{published}"/>'
    )

    # Direct labels, pushed apart so they cannot overlap. The three series end
    # within a point of each other in a calm month, which put three labels on
    # top of one another the first time this was drawn.
    labels = [
        (y(high[months[-1]]), "car-dependent commuter", theme.text_secondary, False),
        (y(official[months[-1]]), "published CPI", theme.text_primary, True),
        (y(low[months[-1]]), "student", theme.text_secondary, False),
    ]
    labels.sort(key=lambda item: item[0])
    minimum_gap = 17.0
    placed: list[float] = []
    for anchor, _, _, _ in labels:
        target = anchor
        if placed and target - placed[-1] < minimum_gap:
            target = placed[-1] + minimum_gap
        placed.append(target)
    # Recentre the stack on the anchors so it does not drift downward.
    shift = (sum(a for a, _, _, _ in labels) - sum(placed)) / len(placed)
    placed = [p + shift for p in placed]

    for (anchor, text, colour, bold), ty in zip(labels, placed):
        weight = ' font-weight="600"' if bold else ""
        parts.append(
            f'<line x1="{left + plot_w + 5:.1f}" y1="{anchor:.1f}" '
            f'x2="{left + plot_w + 12:.1f}" y2="{ty - 4:.1f}" '
            f'stroke="{theme.gridline}" stroke-width="1"/>'
        )
        parts.append(
            f'<text x="{left + plot_w + 15:.1f}" y="{ty:.1f}" font-size="11.5"'
            f'{weight} fill="{colour}">{esc(text)}</text>'
        )

    # Year ticks, so the 2021-22 episode can be located.
    seen = set()
    for i, m in enumerate(months):
        if m.year in seen or m.month != 1:
            continue
        seen.add(m.year)
        parts.append(
            f'<text x="{x(i):.1f}" y="{top + plot_h + 20:.1f}" font-size="11" '
            f'fill="{theme.muted}" text-anchor="middle">{m.year}</text>'
        )

    parts.append(
        f'<line x1="{left}" y1="{top + plot_h}" x2="{left + plot_w}" '
        f'y2="{top + plot_h}" stroke="{theme.baseline}" stroke-width="1"/>'
    )
    parts.append("</svg>")
    return "\n".join(parts)


def regime_chart(rows, theme: Theme) -> str:
    """Mean spread in each inflation regime."""
    width, row_h, top, bottom = 660, 52, 82, 60
    label_w, right_pad = 190, 92
    height = top + len(rows) * row_h + bottom
    plot_w = width - label_w - right_pad
    hi = max(v for _, v, _ in rows) * 1.18

    def x(v: float) -> float:
        return label_w + v / hi * plot_w

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" '
        f'height="{height}" viewBox="0 0 {width} {height}" '
        f'font-family="{FONT}" role="img" '
        f'aria-label="Mean spread between household inflation rates, grouped '
        f'by the level of headline inflation.">',
        f'<rect width="{width}" height="{height}" fill="{theme.surface}"/>',
        f'<text x="24" y="32" font-size="15" font-weight="600" '
        f'fill="{theme.text_primary}">The headline describes people worst when '
        f'it matters most</text>',
        f'<text x="24" y="54" font-size="12" fill="{theme.text_secondary}">'
        f'Average gap between the highest and lowest household, by headline '
        f'inflation</text>',
    ]

    bar_h = 22
    for i, (label, value, count) in enumerate(rows):
        centre = top + i * row_h + row_h / 2 - bar_h / 2
        # Ordinal, not categorical: the three buckets are ordered, so one
        # hue stepping darker carries that. Separate hues would imply
        # they are unrelated categories.
        shade = theme.ramp[i]
        opacity = 1.0
        parts.append(
            f'<text x="{label_w - 14}" y="{centre + bar_h / 2 + 4:.1f}" '
            f'font-size="12.5" fill="{theme.text_primary}" text-anchor="end">'
            f'{esc(label)}</text>'
        )
        parts.append(
            f'<rect x="{label_w}" y="{centre:.1f}" '
            f'width="{max(x(value) - label_w, 2):.1f}" height="{bar_h}" '
            f'rx="4" fill="{shade}" opacity="{opacity}"/>'
        )
        parts.append(
            f'<rect x="{label_w}" y="{centre:.1f}" width="4" '
            f'height="{bar_h}" fill="{shade}" opacity="{opacity}"/>'
        )
        parts.append(
            f'<text x="{x(value) + 10:.1f}" y="{centre + bar_h / 2 + 4:.1f}" '
            f'font-size="12.5" font-weight="600" fill="{theme.text_primary}">'
            f'{value:.2f}pp</text>'
        )
        parts.append(
            f'<text x="{x(value) + 10:.1f}" y="{centre + bar_h / 2 + 19:.1f}" '
            f'font-size="10.5" fill="{theme.muted}">{count} months</text>'
        )

    parts.append(
        f'<line x1="{label_w}" y1="{top - 10}" x2="{label_w}" '
        f'y2="{top + len(rows) * row_h}" stroke="{theme.baseline}" '
        f'stroke-width="2"/>'
    )
    ratio = rows[-1][1] / rows[0][1]
    parts.append(
        f'<text x="24" y="{height - 24}" font-size="12" '
        f'fill="{theme.text_secondary}">In a shock the households disagree '
        f'{ratio:.1f} times as much as they do at target.</text>'
    )
    parts.append("</svg>")
    return "\n".join(parts)


def main() -> int:
    data = load(DATA)
    histories = {
        b.name: {r.month: r.rate for r in basket_history(data, b)}
        for b in ALL_BASKETS
    }
    official = histories[OFFICIAL.name]
    months = sorted(official)

    high = histories[by_name("car-dependent commuter").name]
    low = histories[by_name("student").name]
    months = [m for m in months if m in high and m in low]

    calm, middle, hot = [], [], []
    for m in months:
        values = [h[m] for h in histories.values() if m in h]
        if len(values) < len(ALL_BASKETS):
            continue
        spread = (max(values) - min(values)) * 100
        headline = official[m]
        (calm if headline < CALM else middle if headline < HOT else hot).append(spread)

    rows = [
        ("headline below 3%", statistics.mean(calm), len(calm)),
        ("headline 3% to 5%", statistics.mean(middle), len(middle)),
        ("headline 5% and above", statistics.mean(hot), len(hot)),
    ]

    OUT.mkdir(parents=True, exist_ok=True)
    for theme in (LIGHT, DARK):
        (OUT / f"band-{theme.name}.svg").write_text(
            band_chart(months, official, high, low, theme)
        )
        (OUT / f"regimes-{theme.name}.svg").write_text(regime_chart(rows, theme))

    print(f"wrote 4 figures to {OUT.relative_to(ROOT)}")
    for label, value, count in rows:
        print(f"  {label:<24}{value:>6.2f}pp  ({count} months)")
    print(f"  ratio hot/calm          {rows[-1][1] / rows[0][1]:>6.1f}x")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
