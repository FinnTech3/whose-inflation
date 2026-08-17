# Sources

- **Kind:** research
- **Started:** 2026-08-05

## Data

US Bureau of Labor Statistics, Consumer Price Index for All Urban Consumers
(CPI-U), US city average, **not seasonally adjusted**, monthly, 2017-01 to
2026-06. Retrieved from the public API v1, which needs no registration key.

Series used: the all-items index and the eight major groups.

| Series | Group |
| --- | --- |
| `CUUR0000SA0` | All items |
| `CUUR0000SAF` | Food and beverages |
| `CUUR0000SAH` | Housing |
| `CUUR0000SAA` | Apparel |
| `CUUR0000SAT` | Transportation |
| `CUUR0000SAM` | Medical care |
| `CUUR0000SAR` | Recreation |
| `CUUR0000SAE` | Education and communication |
| `CUUR0000SAG` | Other goods and services |

Not seasonally adjusted on purpose: every comparison here is year-on-year, so
seasonal patterns cancel, and the unadjusted series is the one the relative
importance weights are published against.

The response is committed at `src/whoseinflation/data/`. The keyless API tier
is rate-limited to a small number of requests per day, I hit the cap during
development, so fetching at runtime would make results unreproducible and the
tool unusable on a bad day.

## Weights

Relative importance of the eight major groups, CPI-U, US city average,
December 2023, from the BLS CPI news release relative importance table. These
are reproduced exactly in `baskets.OFFICIAL` and are what the reconstruction
check validates against.

The four household baskets are **my own**, not official statistics. They are
built by shifting group shares in the directions the BLS Consumer Expenditure
Survey documents for each group, renters, older households, car-dependent
households, students, and each carries a written rationale in the code. They
are labelled as illustrative wherever they appear.

## Studied

No code was copied. The method, decomposing a price index into weighted
components and re-weighting for alternative populations, is standard index
number theory. BLS's own experimental CPI-E for the elderly is the same idea
applied officially, and was the prompt for asking what other populations would
look like.

## What did not work

The ONS timeseries API was the first choice, since UK data would have been more
personal. It was decommissioned in November 2024 and now returns a plain-text
notice with a 404. Recorded here so the next person checks before planning
around it.

## License obligations

None. US government data is not subject to copyright. Original work.
