"""Whose shopping the index is actually measuring.

The CPI is a weighted average, and the weights are the whole argument. BLS
surveys what households spend and sets each category's share accordingly, so
the headline number describes the spending of a statistical composite: a
household that allocates 45% of its budget to housing, 17% to transport, 8% to
medical care, and so on, all at once.

Almost nobody spends like that. A twenty-three-year-old renting a room and
taking the bus, and a retired couple who own their house outright and see a
doctor monthly, face the same prices and completely different inflation rates.
Both are inside the average. Neither is described by it.

The baskets below re-weight the same eight official indices. Nothing about the
underlying price data changes — only the question of whose budget is being
weighted. That is the point: the divergence is not a different measurement, it
is the same measurement asked on behalf of somebody else.

**These are illustrative, not official.** The official weights are sourced and
exact. The household variants are my own, built by shifting shares in the
directions the Consumer Expenditure Survey documents for each group, and they
are stated as assumptions rather than dressed up as statistics. Anyone who
disagrees with a weight can edit it and re-run; that is why they live in one
readable table rather than buried in a formula.
"""

from __future__ import annotations

from dataclasses import dataclass

#: The eight CPI major groups, as BLS series IDs, with readable names.
GROUPS: dict[str, str] = {
    "CUUR0000SAF": "Food and beverages",
    "CUUR0000SAH": "Housing",
    "CUUR0000SAA": "Apparel",
    "CUUR0000SAT": "Transportation",
    "CUUR0000SAM": "Medical care",
    "CUUR0000SAR": "Recreation",
    "CUUR0000SAE": "Education and communication",
    "CUUR0000SAG": "Other goods and services",
}

#: The all-items index. What the news reports.
ALL_ITEMS = "CUUR0000SA0"


@dataclass(frozen=True)
class Basket:
    """A set of weights over the eight groups, and who they describe."""

    name: str
    #: Why this basket looks the way it does. Shown in output, because a
    #: weight without a reason is just a number somebody chose.
    rationale: str
    weights: dict[str, float]
    #: True only for the official BLS relative importances.
    official: bool = False

    def __post_init__(self) -> None:
        missing = set(GROUPS) - set(self.weights)
        if missing:
            raise ValueError(
                f"{self.name}: no weight for {sorted(missing)}"
            )
        unknown = set(self.weights) - set(GROUPS)
        if unknown:
            raise ValueError(f"{self.name}: unknown groups {sorted(unknown)}")
        if any(w < 0 for w in self.weights.values()):
            raise ValueError(f"{self.name}: negative weight")
        if self.total <= 0:
            raise ValueError(f"{self.name}: weights sum to nothing")

    @property
    def total(self) -> float:
        return sum(self.weights.values())

    def share(self, group: str) -> float:
        """Normalised weight, so baskets that do not sum to 100 still work."""
        return self.weights[group] / self.total

    def biggest(self) -> tuple[str, float]:
        group = max(self.weights, key=lambda g: self.weights[g])
        return group, self.share(group)

    def differences_from(self, other: Basket) -> list[tuple[str, float]]:
        """Percentage-point differences in share, largest gap first."""
        deltas = [
            (group, (self.share(group) - other.share(group)) * 100)
            for group in GROUPS
        ]
        deltas.sort(key=lambda pair: -abs(pair[1]))
        return deltas


#: BLS relative importance of the eight major groups, CPI-U, US city average,
#: December 2023. Published in the CPI news release's relative importance
#: table. These are the real weights behind the real number.
OFFICIAL = Basket(
    name="official CPI-U",
    rationale="BLS relative importance, December 2023. The published number.",
    official=True,
    weights={
        "CUUR0000SAF": 14.263,
        "CUUR0000SAH": 44.998,
        "CUUR0000SAA": 2.512,
        "CUUR0000SAT": 16.686,
        "CUUR0000SAM": 8.058,
        "CUUR0000SAR": 5.294,
        "CUUR0000SAE": 5.759,
        "CUUR0000SAG": 2.430,
    },
)

RENTER = Basket(
    name="renter, early career",
    rationale=(
        "Rent takes a larger bite than the average because there is no "
        "mortgage fixed years ago, and no house whose imputed rent counts as "
        "housing without being paid. Little spent on medical care; more of "
        "what is left goes on food."
    ),
    weights={
        "CUUR0000SAF": 17.5,
        "CUUR0000SAH": 52.0,
        "CUUR0000SAA": 3.0,
        "CUUR0000SAT": 14.0,
        "CUUR0000SAM": 3.5,
        "CUUR0000SAR": 5.0,
        "CUUR0000SAE": 3.5,
        "CUUR0000SAG": 1.5,
    },
)

RETIRED = Basket(
    name="retired, owns outright",
    rationale=(
        "The mortgage is gone, so housing falls sharply as a share of "
        "spending. Medical care rises to roughly double the average, which is "
        "the pattern BLS's experimental elderly index is built to capture."
    ),
    weights={
        "CUUR0000SAF": 15.0,
        "CUUR0000SAH": 36.0,
        "CUUR0000SAA": 2.0,
        "CUUR0000SAT": 13.0,
        "CUUR0000SAM": 17.0,
        "CUUR0000SAR": 6.5,
        "CUUR0000SAE": 4.0,
        "CUUR0000SAG": 6.5,
    },
)

COMMUTER = Basket(
    name="car-dependent commuter",
    rationale=(
        "Two cars, a long drive, and fuel bought weekly. Transport takes "
        "close to a third of the budget, which makes this basket a "
        "leveraged bet on the oil price whether or not the household "
        "thinks of it that way."
    ),
    weights={
        "CUUR0000SAF": 14.0,
        "CUUR0000SAH": 36.0,
        "CUUR0000SAA": 2.5,
        "CUUR0000SAT": 30.0,
        "CUUR0000SAM": 7.0,
        "CUUR0000SAR": 5.0,
        "CUUR0000SAE": 4.0,
        "CUUR0000SAG": 1.5,
    },
)

STUDENT = Basket(
    name="student",
    rationale=(
        "Tuition and a phone contract dominate a category the average "
        "household barely notices. Shared housing, almost no car, and "
        "medical care that is somebody else's problem for now."
    ),
    weights={
        "CUUR0000SAF": 18.0,
        "CUUR0000SAH": 42.0,
        "CUUR0000SAA": 4.0,
        "CUUR0000SAT": 10.0,
        "CUUR0000SAM": 2.5,
        "CUUR0000SAR": 7.0,
        "CUUR0000SAE": 14.0,
        "CUUR0000SAG": 2.5,
    },
)

HOUSEHOLDS: tuple[Basket, ...] = (RENTER, RETIRED, COMMUTER, STUDENT)
ALL_BASKETS: tuple[Basket, ...] = (OFFICIAL, *HOUSEHOLDS)


def by_name(name: str) -> Basket:
    for basket in ALL_BASKETS:
        if basket.name == name:
            return basket
    available = ", ".join(repr(b.name) for b in ALL_BASKETS)
    raise KeyError(f"unknown basket {name!r}; available: {available}")
