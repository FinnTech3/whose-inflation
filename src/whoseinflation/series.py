"""CPI index levels, and the small print that comes with them.

A price index is not a price. It is a number that starts at 100 in some
reference period and moves with the cost of a fixed basket, so the level alone
means nothing and only ratios between two dates mean anything at all. That is
why everything here works in ratios and never subtracts one index from another.

Two things about the BLS feed worth knowing before trusting it:

**Some values are the string ``"-"``.** Not null, not zero, a hyphen, sitting
in a field the schema says is a number. Nine of them in the ten years loaded
here. Coerce blindly and you crash; coerce with a bare ``float(v) or 0`` and
you have silently inserted a zero index level, which reads as prices falling
100% and then recovering.

**Not every period is a month.** Annual averages arrive alongside monthly
observations, tagged ``M13``, and they look exactly like data. Average them in
with the months and every year is quietly counted thirteen times.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

#: BLS marks an unavailable observation with this, inside a numeric field.
UNAVAILABLE = "-"

#: The period code for an annual average. It is not a thirteenth month.
ANNUAL_AVERAGE = "M13"


@dataclass(frozen=True, slots=True)
class Month:
    """A year and month, ordered and hashable."""

    year: int
    month: int

    def __post_init__(self) -> None:
        if not 1 <= self.month <= 12:
            raise ValueError(f"month {self.month} is not a month")

    def a_year_earlier(self) -> Month:
        return Month(self.year - 1, self.month)

    def __lt__(self, other: Month) -> bool:
        return (self.year, self.month) < (other.year, other.month)

    def __str__(self) -> str:
        return f"{self.year}-{self.month:02d}"


@dataclass(frozen=True)
class Series:
    """One CPI series: a name and a monthly index level."""

    series_id: str
    levels: dict[Month, float]
    #: Observations skipped because the value was not a number.
    unavailable: int = 0
    #: Annual-average rows discarded. Kept as a count so the parser can prove
    #: it saw them and dropped them on purpose.
    annual_rows_dropped: int = 0

    @property
    def months(self) -> list[Month]:
        return sorted(self.levels)

    def level(self, month: Month) -> float | None:
        return self.levels.get(month)

    def year_on_year(self, month: Month) -> float | None:
        """Change against the same month a year earlier.

        Same month, deliberately. Month-on-month comparisons of an unadjusted
        index mostly measure the seasons, heating in January, airfares in
        July, rather than inflation.
        """
        now = self.levels.get(month)
        then = self.levels.get(month.a_year_earlier())
        if now is None or then is None or then == 0:
            return None
        return now / then - 1.0

    def __len__(self) -> int:
        return len(self.levels)


def parse_bls(payload: dict) -> dict[str, Series]:
    """Read a BLS timeseries response into series keyed by series ID."""
    status = payload.get("status")
    if status != "REQUEST_SUCCEEDED":
        messages = payload.get("message") or []
        raise ValueError(f"BLS request failed: {status} {messages}")

    out: dict[str, Series] = {}
    for block in payload.get("Results", {}).get("series", []):
        levels: dict[Month, float] = {}
        unavailable = 0
        annual = 0
        for row in block.get("data", []):
            period = row.get("period", "")
            if period == ANNUAL_AVERAGE:
                annual += 1
                continue
            if not period.startswith("M"):
                continue
            raw = row.get("value")
            try:
                value = float(raw)
            except (TypeError, ValueError):
                unavailable += 1
                continue
            levels[Month(int(row["year"]), int(period[1:]))] = value
        out[block["seriesID"]] = Series(
            series_id=block["seriesID"],
            levels=levels,
            unavailable=unavailable,
            annual_rows_dropped=annual,
        )
    return out


def load(path: Path | str) -> dict[str, Series]:
    return parse_bls(json.loads(Path(path).read_text()))
