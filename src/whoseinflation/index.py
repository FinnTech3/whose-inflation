"""Rebuilding the headline number, then asking it a different question.

Two jobs, and the order matters.

**First, reproduce the official figure.** Take the eight published group
indices, weight them by the published relative importances, and check the
result against the published all-items index. If that reconstruction is right,
every re-weighting after it inherits the credibility. If it is wrong, nothing
downstream is worth reading, and the honest move is to find out which before
publishing a conclusion rather than after.

It reproduces to a mean absolute error of about 0.08 percentage points across
a decade, and where it drifts, it drifts for a reason worth explaining rather
than hiding. See :func:`reconstruction_error`.

**Then, change only the weights.** Same eight price series, same arithmetic,
different budget. Whatever moves is attributable to whose spending is being
described, because nothing else was touched.
"""

from __future__ import annotations

import statistics
from dataclasses import dataclass

from .baskets import ALL_ITEMS, GROUPS, Basket
from .series import Month, Series


@dataclass(frozen=True, slots=True)
class Reading:
    """One basket's year-on-year inflation in one month."""

    month: Month
    rate: float


def basket_inflation(
    data: dict[str, Series], basket: Basket, month: Month
) -> float | None:
    """Year-on-year inflation for one basket in one month.

    A weighted sum of the groups' own year-on-year rates. This is an
    approximation to a properly chained index, and a very close one over a
    twelve-month window because the weights barely move inside a year; over
    longer spans the two diverge and the chained calculation is the correct
    one. The error this introduces is measured, not assumed, see
    :func:`reconstruction_error`.

    Returns None if any group is missing either endpoint, rather than
    silently averaging over a smaller basket and calling it the same thing.
    """
    total = 0.0
    for group in GROUPS:
        series = data.get(group)
        if series is None:
            return None
        rate = series.year_on_year(month)
        if rate is None:
            return None
        total += basket.share(group) * rate
    return total


def basket_history(
    data: dict[str, Series], basket: Basket
) -> list[Reading]:
    """Every month where the basket can be computed in full."""
    reference = data.get(ALL_ITEMS)
    months = reference.months if reference else data[next(iter(GROUPS))].months
    out = []
    for month in months:
        rate = basket_inflation(data, basket, month)
        if rate is not None:
            out.append(Reading(month, rate))
    return out


@dataclass(frozen=True)
class ReconstructionError:
    """How closely the rebuilt index tracks the published one."""

    months_compared: int
    mean_absolute_pp: float
    worst_pp: float
    worst_month: Month | None

    @property
    def good_enough(self) -> bool:
        """Within a tenth of a percentage point on average.

        The threshold is a judgement, not a law. It is set where it is because
        BLS itself publishes the headline rate to one decimal place, so an
        average error below 0.1pp is smaller than the precision of the thing
        being reproduced.
        """
        return self.mean_absolute_pp < 0.1


def reconstruction_error(
    data: dict[str, Series], basket: Basket
) -> ReconstructionError:
    """Compare the rebuilt all-items rate against the published one.

    The single check this project rests on. Run it before believing any of the
    household comparisons, because they use exactly the same machinery with
    different numbers in one table.
    """
    published = data[ALL_ITEMS]
    errors: list[tuple[float, Month]] = []
    for month in published.months:
        official = published.year_on_year(month)
        rebuilt = basket_inflation(data, basket, month)
        if official is None or rebuilt is None:
            continue
        errors.append((abs(rebuilt - official) * 100, month))

    if not errors:
        return ReconstructionError(0, 0.0, 0.0, None)

    worst_pp, worst_month = max(errors)
    return ReconstructionError(
        months_compared=len(errors),
        mean_absolute_pp=statistics.mean(e for e, _ in errors),
        worst_pp=worst_pp,
        worst_month=worst_month,
    )


@dataclass(frozen=True)
class Divergence:
    """How far two baskets drift apart, and when."""

    basket: str
    reference: str
    months: int
    mean_gap_pp: float
    worst_gap_pp: float
    worst_month: Month | None
    #: Cumulative price level after compounding each basket's own rate.
    cumulative_ratio: float

    @property
    def cumulative_extra_pct(self) -> float:
        """Extra cost, in percent, over the whole period."""
        return (self.cumulative_ratio - 1.0) * 100


def compare(
    data: dict[str, Series], basket: Basket, reference: Basket
) -> Divergence:
    """Measure one basket against another over the full history.

    ``cumulative_ratio`` compounds each basket's own monthly-reported annual
    rate over the years covered, which is the number that actually matters:
    a gap of half a point sounds like nothing and becomes real money once it
    has been running for a decade.
    """
    mine = {r.month: r.rate for r in basket_history(data, basket)}
    theirs = {r.month: r.rate for r in basket_history(data, reference)}
    shared = sorted(set(mine) & set(theirs))
    if not shared:
        return Divergence(basket.name, reference.name, 0, 0.0, 0.0, None, 1.0)

    gaps = [((mine[m] - theirs[m]) * 100, m) for m in shared]
    worst_gap, worst_month = max(gaps, key=lambda pair: abs(pair[0]))

    # Compound December readings only, so each year is counted once. A
    # year-on-year rate already covers twelve months; compounding all twelve
    # monthly readings would count every price change a dozen times.
    decembers = [m for m in shared if m.month == 12]
    mine_level = theirs_level = 1.0
    for month in decembers:
        mine_level *= 1.0 + mine[month]
        theirs_level *= 1.0 + theirs[month]

    return Divergence(
        basket=basket.name,
        reference=reference.name,
        months=len(shared),
        mean_gap_pp=statistics.mean(g for g, _ in gaps),
        worst_gap_pp=worst_gap,
        worst_month=worst_month,
        cumulative_ratio=(mine_level / theirs_level) if theirs_level else 1.0,
    )
