# civic-dashboard-kit

[![Test](https://github.com/cardelljo/civic-dashboard-kit/actions/workflows/test.yml/badge.svg)](https://github.com/cardelljo/civic-dashboard-kit/actions/workflows/test.yml)
[![License: Apache 2.0](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](LICENSE)

Data-acquisition clients, a source-provenance contract, and an append-only
observations store for building **honest, sourced civic data dashboards** —
the kind where every number a user sees can be traced back to exactly where
it came from and when.

It grew out of three real, shipped Memphis/Shelby County civic dashboards
([901justice](https://901justice.bluffcitytech.com), 901education, 901economy)
that each needed the same handful of things — pull Census/BEA/FRED/ArcGIS
data, extract numbers from PDF reports without fabricating anything, track
where every published figure came from, and never let sample or unreviewed
data pass as live — and kept re-solving them separately until a shared
package made more sense than a third copy-paste.

## Why this exists

Most dashboard tooling optimizes for showing a number. This one optimizes
for **never showing a number you can't back up.** Concretely:

- **Every dataset carries a provenance contract** (`snapshot.py`): source,
  fetch timestamp, script, and an explicit `isSample`/`status` flag. A
  dashboard built on this can't accidentally present placeholder or
  unreviewed data as if it were real — the contract makes that a validation
  failure, not a judgment call left to whoever wrote the last commit.
- **Storage is append-only** (`observations.py` / `postgres_store.py`): a
  revised value is a new row from a new run, never an overwrite. A metric a
  source stops publishing keeps its history. Nothing is ever silently lost
  or quietly corrected.
- **AI-assisted extraction gets a human gate, not a rubber stamp**
  (`postgres_store.py`'s `record_run(status="pending_review")` /
  `approve_run` / `reject_run`): a value an LLM pulled from a PDF cannot
  reach a dashboard until a person has actually reviewed it against the
  source. This isn't a hypothetical safeguard — an earlier build of one of
  the three dashboards this toolkit powers merged a batch of fabricated
  placeholder values mislabeled as live data; the review gate exists
  specifically so that failure mode is structurally harder to repeat, not
  just a code-review habit to remember.
- **Regex before AI.** Deterministic parsing is auditable and free; an LLM
  is the fallback for layout drift a regex can't handle, never the first
  resort (`pdf_report.py`).
- **Aggregate-first, no person-level data.** Prefer server-side aggregation
  and published aggregate files; this toolkit is not built for, and should
  not be used for, storing individual-level records.

If your dashboard doesn't care about any of that, plenty of lighter tools
will serve you better. If it does, that's what this is for.

## Installing

```
pip install "civic-dashboard-kit @ git+https://github.com/cardelljo/civic-dashboard-kit.git@main"
```

Optional extras keep heavier dependencies out of projects that don't need them:

```
pip install "civic-dashboard-kit[ai] @ git+https://github.com/cardelljo/civic-dashboard-kit.git@main"        # pymupdf, anthropic, openai, google-generativeai, langextract
pip install "civic-dashboard-kit[postgres] @ git+https://github.com/cardelljo/civic-dashboard-kit.git@main"  # psycopg2-binary
```

The base install has neither extra — just `requests`.

**The distribution name is `civic-dashboard-kit`; the importable module is
`toolkit`** — i.e. `from toolkit.census import AcsClient`, not
`from civic_dashboard_kit.census import ...`. This is a deliberate,
PyYAML-style divergence (ships as `PyYAML`, imports as `yaml`): the code
originally lived inside one dashboard's local `toolkit/` directory, and
keeping the import path stable meant every existing consumer needed zero
code changes when this package moved to its own repo.

A pinned version tag is safer than tracking `@main` once you depend on this
from a production pipeline — see [Versioning](#versioning).

## Quickstart

**Census ACS** (detail + subject tables, county/tract/MSA/place cuts):

```python
from toolkit.census import AcsClient

acs = AcsClient(year=2023)
acs.county("B19013_001E", state="47", county="157")       # {'B19013_001E': '54476', 'NAME': 'Shelby County, Tennessee'}
acs.msa("B19013_001E", cbsa="32820")                        # Memphis MSA cut
acs.place("B19013_001E", place="48000", state="47")         # Memphis city cut
acs.pct("S1701_C03_001E", "S1701_C01_001E")                 # convenience: numerator/denominator*100
```

**FRED** (series observations, monthly/annual economic series):

```python
from toolkit.fred import FredClient

fred = FredClient(api_key="...")
fred.series_observations("MPHNA", start="2020-01-01")
# -> [{"date": "2020-01-01", "value": 654200.0}, ...] -- FRED's "." missing-value
#    sentinel is dropped, never parsed as 0
```

**BEA Regional** (GDP by area — nominal, chained, by-industry):

```python
from toolkit.bea import BeaClient

bea = BeaClient(api_key="...")
bea.regional_gdp(table_name="CAGDP1", geo_fips="28700", year="2023")
# -> [{"geo_fips": "28700", "geo_name": "Memphis, TN-MS-AR (Metropolitan Statistical Area)",
#      "period": "2023", "value": 102900.0}]
```

**ArcGIS Feature Service** (server-side aggregation, not raw record dumps):

```python
from toolkit.arcgis import FeatureService, date_where

svc = FeatureService("https://services.arcgis.com/.../FeatureServer/0")
svc.count_by("category")                                    # server-side groupBy/outStatistics
date_where("incident_date", start, end)                      # a WHERE clause helper
```

**The source-provenance contract** — every dataset your pipeline produces
should carry this:

```python
from toolkit.snapshot import build_meta, validate_meta

meta = build_meta(
    source_key="acs-median-income", source_name="Census ACS 5-year",
    script="pipeline/fetch_acs.py", record_grain="county-year",
    how_to_update="Run: python3 pipeline/fetch_acs.py",
    notes="Median household income, Shelby County.",
    is_sample=False, status="live", tier="T1",
)
data = {"_meta": meta, "rows": [...]}
validate_meta("data/income.json", data, "acs-median-income", "county-year")  # raises on contract violations
```

**Storing what you fetch** — pick one of two stores based on scale (see
[Choosing a store](#choosing-a-store-observationspy-vs-postgres_storepy)):

```python
# Low/moderate volume -- NDJSON ledger materialized into an in-memory SQLite:
from toolkit.observations import Observation, record_run, append, load, latest

run_id = record_run(root, source_key="acs-median-income", source_name="Census ACS",
                     script="pipeline/fetch_acs.py", fetched_at="2026-01-01T00:00:00")
append(root, "acs-median-income", run_id,
       [Observation(metric_id="median-hh-income", geography_id="47157",
                     period="2023", value=54476.0)])
latest(load(root), "median-hh-income", geography_id="47157")

# Higher volume, many geographies/cadences, needs a human-review gate -- Postgres:
from toolkit.postgres_store import Observation, record_run, append, latest, approve_run

run_id = record_run(conn, source_key="acs-median-income")
append(conn, "acs-median-income", run_id, tier="T1",
       observations=[Observation(indicator_id="median-hh-income", geography_id="shelby-county",
                                  period="2023", value=54476.0, vintage="ACS 2023 5-year")])
latest(conn, "median-hh-income", geography_id="shelby-county")
```

**AI-assisted PDF extraction** (regex-first, AI-fallback, never the reverse):

```python
from toolkit.pdf_report import download_pdf, extract_text, extract_metrics

pdf = download_pdf(url, cache_dir)
text = extract_text(pdf)
values = extract_metrics(
    text,
    schema={"totalSeats": "Total funded pre-K seats countywide"},
    regex_extractors={"totalSeats": r"Total\s+Seats\D*([\d,]+)"},
    context="Shelby County Pre-K annual report",
)
# extract_metrics() tries each regex_extractor first; toolkit.ai_extract
# (Anthropic/OpenAI/Google, auto-detected from whichever API key is set)
# only fills in fields the regex patterns didn't find.
```

## Module reference

| Module | What it does |
|---|---|
| `census.py` | Census ACS (detail + subject tables; county/tract/MSA/place) and BLS time series. No API key required at moderate volumes. |
| `fred.py` | FRED (Federal Reserve Economic Data) series-observations client. Drops FRED's `.` missing-value sentinel rather than parsing it as zero. Free API key. |
| `bea.py` | BEA Regional API client — GDP-by-area tables (nominal, chained/real, by-industry). Free API key. |
| `arcgis.py` | ArcGIS Feature Service queries with server-side aggregation (`outStatistics`/`groupBy`) — aggregate-first, not raw record dumps. |
| `ai_extract.py` | Multi-provider (Anthropic/OpenAI/Google) structured extraction from unstructured text. Provider auto-detected from whichever API key is set. |
| `pdf_report.py` | Recurring-PDF pipeline: download → text extraction → regex-first parsing, AI-fallback only for what regex can't find. |
| `geo.py` | Dependency-free shapefile → GeoJSON conversion, including a TN State Plane → WGS84 transform and ring simplification. No GDAL/geopandas. |
| `snapshot.py` | The source-provenance contract: `build_meta()` (writer) and `validate_meta()`/`validate_unique_ids()` (validators). |
| `observations.py` | Append-only store: `Observation` dataclass + an NDJSON ledger materialized into an in-memory SQLite `observations_current` view. No server needed. |
| `metrics.py` | A metric-ID registry pattern (label/unit/good-direction/description per metric) — pairs with `observations.py`. |
| `postgres_store.py` | Same `Observation`/append-only design as `observations.py`, against a live Postgres connection — for higher data volume. Also implements the human-review gate for AI-extracted data (`pending_review` → `approve_run`/`reject_run`), with no external ticketing system required. |

## Choosing a store: `observations.py` vs. `postgres_store.py`

These share a design, not an implementation, and the choice is about scale,
not preference:

- **`observations.py`** (NDJSON ledger → in-memory SQLite): right for a
  single-geography, low/annual-cadence dashboard — realistically, low
  thousands of rows even over many years of history. Zero infrastructure:
  the ledger is just files, committed to git alongside your code.
- **`postgres_store.py`**: right once you're pulling many sources across
  many geographies and cadences (weekly/monthly pulls × a peer-set of
  cities, say) — a git-committed ledger's commit size and diff-reviewability
  degrade past a point a real database doesn't. It's also the one with the
  human-review gate built in (`pending_review`/`approve_run`/`reject_run`),
  which only makes sense once you have an AI-extraction step producing
  values that need sign-off before publication.

Don't reach for Postgres by default — it's genuinely more moving parts to
run. Start with `observations.py`; move to `postgres_store.py` when the
NDJSON ledger's commit sizes or review burden actually become a problem, not
before.

Once you are on Postgres, how the instance is laid out across dashboards — one
instance, one schema each, plus a shared PostGIS `geo` schema holding the
boundary polygons they all plot — is recorded in
[`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md).

## Design principles

- **Toolkit modules are generic.** No dashboard-specific source URLs, field
  names, or narrative belongs here — that's what your own pipeline scripts
  are for. This package answers "how do I talk to the Census API," never
  "what does Shelby County's poverty rate mean."
- **Aggregate-first, always.** Prefer server-side aggregation and published
  aggregate files. This is not designed for, and should not be used for,
  person-level or record-level data.
- **Regex before AI.** Deterministic extraction is auditable and free; AI
  extraction is the fallback for layout drift, never the first resort.
- **Every output carries provenance.** Use `snapshot.build_meta()` so
  whatever renders your data can tell users exactly what they're looking at
  — and so a validation step can catch it if that stops being true.

## Versioning

Tagged releases (`v0.1.0`, ...) are the stable install target for anything
beyond local development — pin to a tag, not `@main`, once a real pipeline
depends on this:

```
pip install "civic-dashboard-kit @ git+https://github.com/cardelljo/civic-dashboard-kit.git@v0.1.0"
```

See [CHANGELOG.md](CHANGELOG.md).

## Used by

- [901justice](https://901justice.bluffcitytech.com) — the original source
  of most of these patterns, extracted here after two more dashboards needed
  the same code.
- 901education — added the append-only observations store and the
  provenance contract's `tier` field.
- 901economy — added `fred.py`, `bea.py`, MSA/place ACS cuts, and
  `postgres_store.py` (including the human-review gate).

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md).

## License

Apache 2.0 — see [LICENSE](LICENSE).
