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

> **Scope: this package has two halves, published from this one repo.** A
> Python distribution installed with pip (`pyproject.toml`, imports as
> `toolkit.*`) and a small TypeScript package installed with npm
> (`package.json`, `ui/`) — the canonical `DataStatus` union and the data-status
> UI that renders it. Everything below describes the Python half except
> [Adopting the TypeScript half](#adopting-the-typescript-half); the two share a
> repo so the status vocabulary cannot drift, and
> [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) §7 records why, with the cost.

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
bea.regional_gdp(table_name="CAGDP1", geo_fips="47157", year="2023", line_code="3")
# -> [{"geo_fips": "47157", "geo_name": "Shelby", "period": "2023", "value": 85672928.0}]
#    thousands of dollars
```

**County, state, and BEA region only — the Regional dataset has no metro-area
GDP**, and a CBSA code raises rather than returning empty. Verified against the
live API; see `bea.py`'s module docstring for the evidence and what to do
instead.

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

## Adopting the TypeScript half

One import path, no build step:

```tsx
import {
  DataStatusPanel, SampleBadge, SourceLine, resolveStatus,
  type DataSource, type DataStatus, type SourceLineProps,
} from 'civic-dashboard-kit';
```

`DataStatus` is the same six values `snapshot.build_meta()` writes and
`validate_meta()` now enforces — `live`, `mixed`, `sample`, `gap`, `manual`,
`report-backed`. `resolveStatus({ isSample, status })` is the
`status ?? (isSample ? 'sample' : 'live')` fallback for snapshots written before
`status` existed; use it rather than re-deriving the rule, so your own components
agree with these two.

All three components are presentational. They take already-imported JSON as props
and fetch nothing, because every dashboard in this series is a static export.

### `SourceLine` — the standard attribution line

Every figure is supposed to carry source and vintage. This fixes *how*:

```tsx
<SourceLine
  source="BEA Regional GDP"          // optional — vintage is promoted if absent
  vintage="2023"                     // optional — but not both
  sourceUrl="https://apps.bea.gov/…" // optional; wraps the source name
  geography="Memphis MSA"            // optional trailing context
  caveat="Revised quarterly."        // optional; accepts markup
/>
// → Source: BEA Regional GDP↗ · 2023 · Memphis MSA Revised quarterly.
```

Separators are `·` so an absent field leaves no stray punctuation. The form is
deliberately not configurable — a standard each dashboard restyles isn't one.
What *is* local: `className` defaults to `data-note`, which every dashboard
already defines with its own muted color, so the line picks up local theming
without importing a palette. Pass `className` to place it in a different slot
(justice's section subheaders, say).

**Attribution and caveats are separate values.** Today most caveats are fused
into the attribution string — `note="Source: TDOE TCAP Assessment Files. 2019-20
canceled and 2020-21 disrupted by COVID; treat those years with caution."` — which
makes them unsearchable and inconsistent. Split them:

```tsx
<SourceLine
  source="TDOE TCAP Assessment Files"
  vintage="2023-24"
  caveat="2019-20 canceled and 2020-21 disrupted by COVID; treat those years with caution."
/>
```

Not every `Source:` in your code is attribution. Some are genuine prose
paragraphs that happen to open with the word — those stay prose. Convert the
lines that are really *name + vintage + link*; see `docs/ARCHITECTURE.md` §7.1
for the inventory that drew the line.

### Install

```
npm install github:cardelljo/civic-dashboard-kit#351a0bbd     # pin a commit, not #main
```

Pin the same way the Python side does. `#main` means a push here can break your
build with no commit in your repo — [CHANGELOG.md](CHANGELOG.md) names which
half each release touched, so a JS consumer can tell which releases concern it.

### Four steps in the consuming app

Peer dependencies are `react` (18 or 19) and `lucide-react` (≥0.400.0); the
components import `useState` and six lucide icons and nothing else.

1. **`next.config.js`** — this package ships raw `.tsx`, so Next has to compile
   it:

   ```js
   const nextConfig = { transpilePackages: ['civic-dashboard-kit'] };
   ```

2. **`tailwind.config.ts`** — add the package to `content`, or **the components
   render unstyled.** Tailwind generates only classes it finds in `content`
   globs and does not scan `node_modules`. This fails silently: the markup mounts
   fine and simply has no styling.

   ```ts
   content: [
     './pages/**/*.{js,ts,jsx,tsx,mdx}',
     './components/**/*.{js,ts,jsx,tsx,mdx}',
     './app/**/*.{js,ts,jsx,tsx,mdx}',
     './node_modules/civic-dashboard-kit/ui/**/*.{js,ts,jsx,tsx}',
   ],
   ```

3. **Define `brand.blue`** in your Tailwind theme. `DataStatusPanel` uses
   `text-brand-blue` for its two "verify" links. Without the token those links
   inherit body color — legible, but not obviously links.

4. **Re-point your own `DataStatus`.** If your `lib/types.ts` declares the union,
   re-export it from here instead of keeping a second copy:

   ```ts
   export type { DataStatus } from 'civic-dashboard-kit';
   ```

Then delete `components/data-status/SampleBadge.tsx` and
`DataStatusPanel.tsx` and update their import sites. The component props are
unchanged (`<SampleBadge isSample={…} status={…} />`,
`<DataStatusPanel sources={…} />`), so nothing else moves.

### Verifying the swap

`npm run build` passing is not sufficient evidence in a repo with
`typescript.ignoreBuildErrors: true` — it will build straight through a type
error. Run `npx tsc --noEmit` explicitly, and look at the rendered panel: the
Tailwind step above is the one that fails without erroring.

Two different kinds of change here, worth reviewing differently:

- **`SampleBadge` / `DataStatusPanel` are a like-for-like lift.** Props are
  unchanged and the markup is identical to what your repo already had, so a clean
  type-check plus a rendered page is enough.
- **`SourceLine` changes what visitors see.** It standardizes a line the three
  dashboards render three ways, so adopting it *should* alter your output —
  `Source:` may move, punctuation changes, caveats separate from attribution.
  Read the diff on the page, not just the build log.

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
