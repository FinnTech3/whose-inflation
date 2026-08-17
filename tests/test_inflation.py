"""Tests for the CPI reconstruction and the basket comparison.

All offline, against the BLS response committed inside the package, the same
file the CLI ships, so the suite exercises what a user actually gets.
"""

from __future__ import annotations

import json
import statistics
from importlib import resources

import pytest

from whoseinflation.baskets import (
    ALL_BASKETS,
    ALL_ITEMS,
    GROUPS,
    HOUSEHOLDS,
    OFFICIAL,
    Basket,
    by_name,
)
from whoseinflation.index import (
    basket_history,
    basket_inflation,
    compare,
    reconstruction_error,
)
from whoseinflation.series import Month, Series, load, parse_bls

DATA = resources.files("whoseinflation") / "data" / "cpi_u_groups_2017_2026.json"


@pytest.fixture(scope="session")
def data() -> dict[str, Series]:
    return load(DATA)


# ---- the check everything rests on --------------------------------------


def test_the_rebuilt_index_matches_the_published_one(data):
    """The load-bearing test.

    Every household comparison is this same calculation with different
    weights. If the official weights do not reproduce the official index,
    nothing downstream means anything, so this failing should be treated as
    the whole project being wrong rather than one test being red.
    """
    error = reconstruction_error(data, OFFICIAL)
    assert error.months_compared > 90, "should span most of a decade"
    assert error.mean_absolute_pp < 0.1, (
        f"rebuild drifts {error.mean_absolute_pp:.3f}pp from the published "
        f"index; the weights or the arithmetic are wrong"
    )
    assert error.good_enough


def test_reconstruction_is_worst_when_weights_moved_most(data):
    """The residual error has a cause, not just a size.

    One year's weights are used across a decade, so the rebuild drifts most
    where real spending patterns shifted most, the pandemic and its
    aftermath. A worst month outside that window would mean the error is
    something else and worth chasing.
    """
    error = reconstruction_error(data, OFFICIAL)
    assert error.worst_month is not None
    assert 2020 <= error.worst_month.year <= 2022


def test_a_wrong_basket_fails_the_reconstruction(data):
    """The check has teeth: it rejects weights that are not the real ones."""
    nonsense = Basket(
        name="everything is housing",
        rationale="deliberately wrong, to prove the check discriminates",
        weights={g: (90.0 if g == "CUUR0000SAH" else 1.0) for g in GROUPS},
    )
    error = reconstruction_error(data, nonsense)
    assert not error.good_enough
    assert error.mean_absolute_pp > 0.2


# ---- the finding --------------------------------------------------------


def test_households_disagree_more_when_inflation_is_high(data):
    """The headline claim, guarded.

    Every other test would pass if the baskets became identical, at which
    point the project would say nothing. This asserts the spread between
    households genuinely widens with the inflation rate.
    """
    histories = {
        b.name: {r.month: r.rate for r in basket_history(data, b)}
        for b in ALL_BASKETS
    }
    official = histories[OFFICIAL.name]

    calm, hot = [], []
    for month, headline in official.items():
        values = [h[month] for h in histories.values() if month in h]
        if len(values) < len(ALL_BASKETS):
            continue
        spread = (max(values) - min(values)) * 100
        if headline < 0.03:
            calm.append(spread)
        elif headline >= 0.05:
            hot.append(spread)

    assert calm and hot, "need both regimes in the sample"
    assert statistics.mean(hot) > 2 * statistics.mean(calm), (
        "the spread should widen sharply in a shock; if it does not, the "
        "central finding no longer holds"
    )


def test_the_commuter_is_the_one_hurt_by_the_energy_spike(data):
    """Transport-heavy baskets should peak with fuel, not at random."""
    commuter = by_name("car-dependent commuter")
    divergence = compare(data, commuter, OFFICIAL)
    assert divergence.worst_month is not None
    assert 2021 <= divergence.worst_month.year <= 2022
    assert divergence.worst_gap_pp > 1.5


def test_every_household_differs_from_the_official_basket():
    for basket in HOUSEHOLDS:
        deltas = basket.differences_from(OFFICIAL)
        assert abs(deltas[0][1]) > 1.0, f"{basket.name} is barely different"


# ---- series parsing -----------------------------------------------------


def test_hyphens_are_skipped_not_coerced():
    """BLS puts "-" in a numeric field. Coercing it to zero reads as a 100%
    price collapse followed by a full recovery."""
    payload = {
        "status": "REQUEST_SUCCEEDED",
        "Results": {"series": [{"seriesID": "X", "data": [
            {"year": "2024", "period": "M01", "value": "100.0"},
            {"year": "2024", "period": "M02", "value": "-"},
            {"year": "2024", "period": "M03", "value": "102.0"},
        ]}]},
    }
    series = parse_bls(payload)["X"]
    assert series.unavailable == 1
    assert len(series) == 2
    assert Month(2024, 2) not in series.levels
    assert 0.0 not in series.levels.values()


def test_annual_averages_are_not_a_thirteenth_month():
    """M13 is the year's average and looks exactly like data."""
    payload = {
        "status": "REQUEST_SUCCEEDED",
        "Results": {"series": [{"seriesID": "X", "data": [
            {"year": "2024", "period": "M01", "value": "100.0"},
            {"year": "2024", "period": "M13", "value": "101.0"},
        ]}]},
    }
    series = parse_bls(payload)["X"]
    assert series.annual_rows_dropped == 1
    assert len(series) == 1


def test_a_failed_request_raises_rather_than_returning_nothing():
    with pytest.raises(ValueError, match="threshold"):
        parse_bls({
            "status": "REQUEST_NOT_PROCESSED",
            "message": ["daily threshold reached"],
        })


def test_real_data_has_the_quirks_this_guards_against(data):
    """Not hypothetical: the committed response contains them."""
    assert sum(s.unavailable for s in data.values()) > 0


def test_year_on_year_compares_the_same_month():
    series = Series("X", {
        Month(2023, 6): 100.0,
        Month(2024, 5): 150.0,   # a decoy: adjacent, wrong month
        Month(2024, 6): 110.0,
    })
    assert series.year_on_year(Month(2024, 6)) == pytest.approx(0.10)


def test_year_on_year_needs_both_ends():
    series = Series("X", {Month(2024, 6): 110.0})
    assert series.year_on_year(Month(2024, 6)) is None


def test_month_rejects_impossible_values():
    with pytest.raises(ValueError, match="not a month"):
        Month(2024, 13)
    with pytest.raises(ValueError, match="not a month"):
        Month(2024, 0)


def test_months_order_across_a_year_boundary():
    assert Month(2023, 12) < Month(2024, 1)
    assert sorted([Month(2024, 3), Month(2023, 11)])[0] == Month(2023, 11)


# ---- baskets ------------------------------------------------------------


def test_official_weights_sum_to_one_hundred():
    assert OFFICIAL.total == pytest.approx(100.0, abs=0.01)


def test_shares_normalise_regardless_of_total():
    doubled = Basket(
        name="doubled",
        rationale="same shape, twice the numbers",
        weights={g: w * 2 for g, w in OFFICIAL.weights.items()},
    )
    for group in GROUPS:
        assert doubled.share(group) == pytest.approx(OFFICIAL.share(group))


def test_a_basket_missing_a_group_is_rejected():
    weights = dict(OFFICIAL.weights)
    weights.pop("CUUR0000SAF")
    with pytest.raises(ValueError, match="no weight for"):
        Basket(name="incomplete", rationale="", weights=weights)


def test_a_basket_with_an_unknown_group_is_rejected():
    weights = dict(OFFICIAL.weights)
    weights["CUUR0000NONSENSE"] = 1.0
    with pytest.raises(ValueError, match="unknown groups"):
        Basket(name="bogus", rationale="", weights=weights)


def test_negative_weights_are_rejected():
    weights = dict(OFFICIAL.weights)
    weights["CUUR0000SAA"] = -1.0
    with pytest.raises(ValueError, match="negative weight"):
        Basket(name="negative", rationale="", weights=weights)


def test_every_basket_carries_a_rationale():
    """A weight without a stated reason is a number somebody made up."""
    for basket in ALL_BASKETS:
        assert len(basket.rationale) > 40, f"{basket.name} needs a reason"


def test_only_the_official_basket_claims_to_be_official():
    assert OFFICIAL.official
    assert all(not b.official for b in HOUSEHOLDS)


def test_by_name_round_trips():
    for basket in ALL_BASKETS:
        assert by_name(basket.name).name == basket.name


def test_by_name_rejects_unknown():
    with pytest.raises(KeyError, match="unknown basket"):
        by_name("nobody")


# ---- comparison ---------------------------------------------------------


def test_a_basket_compared_with_itself_shows_no_gap(data):
    same = compare(data, OFFICIAL, OFFICIAL)
    assert same.mean_gap_pp == pytest.approx(0.0, abs=1e-9)
    assert same.cumulative_ratio == pytest.approx(1.0, abs=1e-9)


def test_missing_groups_give_no_reading_rather_than_a_partial_one(data):
    """Averaging over whatever happens to be present is not the same basket."""
    incomplete = {k: v for k, v in data.items() if k != "CUUR0000SAM"}
    month = sorted(data[ALL_ITEMS].levels)[-1]
    assert basket_inflation(incomplete, OFFICIAL, month) is None


def test_history_covers_most_of_the_decade(data):
    history = basket_history(data, OFFICIAL)
    assert len(history) > 90
    assert history[0].month < history[-1].month
