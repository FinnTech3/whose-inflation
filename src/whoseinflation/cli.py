"""Command line entry point."""

from __future__ import annotations

import argparse
import statistics
import sys
from importlib import resources

from .baskets import ALL_BASKETS, GROUPS, HOUSEHOLDS, OFFICIAL, Basket
from .index import basket_history, compare, reconstruction_error
from .series import Series, load

#: Data ships inside the package so the tool works from a plain install and
#: never needs the network. BLS rate-limits the keyless tier hard enough that
#: depending on it at runtime would make the results unreproducible.
DATA = resources.files("whoseinflation") / "data" / "cpi_u_groups_2017_2026.json"

#: Above this, an economy is in an inflation shock rather than at target.
HOT = 0.05
#: Below this, roughly at target.
CALM = 0.03


def _load() -> dict[str, Series]:
    return load(DATA)


def cmd_verify(args) -> int:
    """Check the rebuilt index against the published one.

    Everything else in this tool is this calculation with different weights,
    so if this does not hold nothing else is worth reading.
    """
    data = _load()
    error = reconstruction_error(data, OFFICIAL)

    print("Rebuilding the published CPI from its eight components\n")
    print(f"  months compared      {error.months_compared}")
    print(f"  mean absolute error  {error.mean_absolute_pp:.3f} pp")
    print(f"  worst month          {error.worst_pp:.2f} pp ({error.worst_month})")

    all_items = data[list(data)[0]]
    skipped = sum(s.unavailable for s in data.values())
    annual = sum(s.annual_rows_dropped for s in data.values())
    print(f"\n  observations skipped as non-numeric   {skipped}")
    print(f"  annual-average rows discarded         {annual}")

    if error.good_enough:
        print(
            f"\nWithin a tenth of a point on average, against a headline BLS "
            f"itself\npublishes to one decimal place. The weights and the "
            f"arithmetic are right,\nso re-weighting them is a fair thing to do."
        )
    else:
        print("\nThe reconstruction does not hold. Do not trust anything below it.")
        return 1

    print(
        f"\nThe worst month is {error.worst_month}, and the reason is worth "
        f"knowing: this\nuses one year's weights across a decade. Real weights "
        f"are re-estimated\nannually, and they moved most when spending "
        f"patterns did — which is exactly\nwhen the error peaks."
    )
    return 0


def cmd_weights(args) -> int:
    """Show what each basket assumes, and why."""
    data = _load()
    baskets = ALL_BASKETS

    header = f"{'group':<30}" + "".join(f"{b.name.split(',')[0][:11]:>12}" for b in baskets)
    print(header)
    print("-" * len(header))
    for group, label in GROUPS.items():
        row = f"{label[:29]:<30}"
        for basket in baskets:
            row += f"{basket.share(group) * 100:>11.1f}%"
        print(row)
    print("-" * len(header))

    print("\nWhy each basket looks the way it does:\n")
    for basket in baskets:
        marker = "  (official)" if basket.official else ""
        print(f"  {basket.name}{marker}")
        for line in _wrap(basket.rationale, 68):
            print(f"    {line}")
        print()
    return 0


def cmd_households(args) -> int:
    """Compare each household against the published figure."""
    data = _load()

    print("Each household's inflation against the published CPI\n")
    print(f"{'basket':<26}{'mean gap':>11}{'worst gap':>12}{'when':>10}"
          f"{'cumulative':>13}")
    print("-" * 72)
    for basket in HOUSEHOLDS:
        d = compare(data, basket, OFFICIAL)
        print(f"{basket.name:<26}{d.mean_gap_pp:>+10.2f}{d.worst_gap_pp:>+11.2f}"
              f"{str(d.worst_month):>10}{d.cumulative_extra_pct:>+12.1f}%")

    print(
        "\nOver a decade the averages are small, which is the first honest "
        "thing to\nsay about this: most of the time the headline is a "
        "reasonable summary of\nmost people. The interesting part is that "
        "this stops being true exactly\nwhen it matters — see `regimes`."
    )
    return 0


def cmd_regimes(args) -> int:
    """The finding: disagreement scales with the inflation rate itself."""
    data = _load()
    histories = {b.name: {r.month: r.rate for r in basket_history(data, b)}
                 for b in ALL_BASKETS}
    official = histories[OFFICIAL.name]

    rows = []
    for month in sorted(official):
        values = {n: h[month] for n, h in histories.items() if month in h}
        if len(values) < len(ALL_BASKETS):
            continue
        spread = (max(values.values()) - min(values.values())) * 100
        rows.append((month, official[month], spread, values))

    calm = [s for _, o, s, _ in rows if o < CALM]
    middle = [s for _, o, s, _ in rows if CALM <= o < HOT]
    hot = [s for _, o, s, _ in rows if o >= HOT]

    print("How far households disagree, by how high inflation is\n")
    print(f"{'headline inflation':<26}{'months':>8}{'mean spread':>14}")
    print("-" * 48)
    for label, bucket in (
        (f"below {CALM:.0%}", calm),
        (f"{CALM:.0%} to {HOT:.0%}", middle),
        (f"{HOT:.0%} and above", hot),
    ):
        if bucket:
            print(f"{label:<26}{len(bucket):>8}{statistics.mean(bucket):>13.2f}pp")

    if calm and hot:
        ratio = statistics.mean(hot) / statistics.mean(calm)
        print(
            f"\nThe gap between the household living the highest inflation and "
            f"the one\nliving the lowest is {ratio:.1f} times wider in a shock "
            f"than at target."
        )

    print("\nThe months where households disagreed most:\n")
    rows.sort(key=lambda r: -r[2])
    for month, head, spread, values in rows[: args.top]:
        high = max(values, key=values.get)
        low = min(values, key=values.get)
        print(f"  {month}  headline {head:>5.1%}   spread {spread:>4.2f}pp")
        print(f"           {high:<26} {values[high]:>5.1%}")
        print(f"           {low:<26} {values[low]:>5.1%}")

    print(
        "\nThis is the part worth taking away. At target, one number describes "
        "nearly\neveryone well enough. In a shock it describes nobody: the "
        "spread widens\nfaster than the average rises, so the figure is least "
        "representative at the\nexact moment people most need it to mean "
        "something."
    )
    return 0


def _wrap(text: str, width: int) -> list[str]:
    words, lines, current = text.split(), [], ""
    for word in words:
        if len(current) + len(word) + 1 > width:
            lines.append(current)
            current = word
        else:
            current = f"{current} {word}".strip()
    if current:
        lines.append(current)
    return lines


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="whoseinflation",
        description="Rebuild the CPI from its parts, then ask whose basket it "
                    "describes.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    verify = sub.add_parser("verify", help="check the rebuild against the published index")
    verify.set_defaults(func=cmd_verify)

    weights = sub.add_parser("weights", help="what each basket assumes, and why")
    weights.set_defaults(func=cmd_weights)

    households = sub.add_parser("households", help="each household against the headline")
    households.set_defaults(func=cmd_households)

    regimes = sub.add_parser("regimes", help="how disagreement scales with inflation")
    regimes.add_argument("--top", type=int, default=3)
    regimes.set_defaults(func=cmd_regimes)

    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    sys.exit(main())
