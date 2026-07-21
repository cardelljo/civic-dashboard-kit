# Civic Data Toolkit

Shared data-acquisition clients for Bluff City Tech community dashboards.
Extracted from [901justice](https://github.com/cardelljo/901justice)'s ETL
scripts so each retrieval pattern is implemented once and reused across
dashboards. As of 901economy (the third dashboard), this directory is a real
installable package — see "Installing" below — not just a vendored copy.

| Module | Pattern | Origin |
|---|---|---|
| `arcgis.py` | ArcGIS Feature Service queries with server-side aggregation (`outStatistics`/`groupBy`) | 901justice's `fetch_crime_data.py`, `fetch_traffic_stops.py`, `fetch_traffic_citations.py` (3 duplicated helpers, now one) |
| `census.py` | Census ACS (detail + subject tables, county/tract/**MSA/place**) and BLS time series | 901justice's `fetch_community_data.py`; MSA/place cuts added for 901economy |
| `fred.py` | FRED (Federal Reserve Economic Data) series-observations client | New for 901economy — no sibling had a FRED client (BLS was pulled directly) |
| `bea.py` | BEA Regional API client (GDP-by-area tables: CAGDP1 nominal, CAGDP9 real/chained, CAGDP2 by industry) | New for 901economy |
| `ai_extract.py` | Multi-provider (Anthropic/OpenAI/Google) structured extraction from unstructured text | 901justice's `ai_extract.py` (moved unchanged) |
| `pdf_report.py` | Recurring-PDF pipeline: download → pymupdf text → regex-first, AI-fallback | 901justice's `parse_jail_pdf.py` |
| `snapshot.py` | `_meta` data-provenance contract: writer + validators (now with an optional `tier` field) | 901justice's `parse_jail_pdf.py` conventions + `validate_snapshots.py` |
| `geo.py` | Dependency-free shapefile → GeoJSON (with TN StatePlane transform + ring simplification) | 901justice's `convert_boundary_shapefiles.py` |
| `observations.py` | Append-only observations store: `Observation` dataclass, NDJSON ledger, materialized into an in-memory SQLite `observations_current` view | Built for 901education's Phase 1.5 retrofit — the right store for single-district, annual-cadence, low-volume dashboards |
| `metrics.py` | `metric_id` registry (label/unit/good-direction/description per metric) | Built alongside `observations.py` |
| `postgres_store.py` | Same design as `observations.py` (`Observation`, append-only, "newest row wins"), re-implemented against a live Postgres connection instead of NDJSON+SQLite — for 901economy's much higher data volume (weekly/monthly pulls × a peer-set × top-50 metros). Also owns the T3 human-review gate (`record_run(status='pending_review')` → `approve_run`/`reject_run`, no GitHub PR involved) | New for 901economy |

**Two stores, deliberately, not one generalized store:** `observations.py` and
`postgres_store.py` share a design (the `Observation` concept, append-only,
never overwrite) but not an implementation. Which one a dashboard uses is a
scale decision, not a preference — see `901economy/PLAN.md` §0.3/§9 for the
full reasoning on when Postgres earns its keep over NDJSON+SQLite.

## Installing

This directory is a real pip-installable package (`civic-toolkit`) via pip's
git-subdirectory syntax — no separate repo:

```
pip install "civic-toolkit @ git+https://github.com/cardelljo/901education.git@main#subdirectory=toolkit"
```

Optional extras keep heavier dependencies out of dashboards that don't need
them: `civic-toolkit[ai]` pulls in `pymupdf`/`anthropic`/`openai`/
`google-generativeai`/`langextract` (`ai_extract.py`/`pdf_report.py`);
`civic-toolkit[postgres]` pulls in `psycopg2-binary` (`postgres_store.py`
only). The base install has neither — just `requests`.

Import path stays `toolkit.*` regardless of how it's installed (e.g.
`from toolkit.census import AcsClient`), matching how 901justice/901education
already import it locally, so there's zero migration cost for existing code.

## Design rules

- **Toolkit modules are generic.** No dashboard-specific source URLs, field
  names, or narrative. Domain recipes live in each dashboard's own
  `scripts/`/`pipeline/` directory and call in.
- **Aggregate-first.** Prefer server-side aggregation and published aggregate
  files; never persist person-level records (see `DATA_SNAPSHOT_CONTRACT.md`).
- **Regex before AI.** Deterministic extraction is auditable and free; AI
  extraction is the fallback for layout drift, never the first resort.
- **Every output carries `_meta`.** Use `snapshot.build_meta()` so the
  frontend's data-status machinery can tell users exactly what they're seeing.

## On extending this package

901economy's `pipeline/` code imports this package rather than vendoring it,
so its toolkit-level additions (new clients, new store backends) land as PRs
*here*, not in the `cardelljo/901economy` repo — see that repo's `PLAN.md`
§2.2 for why. If that cross-repo friction ever grows annoying, promoting this
directory to its own repo is a small, mechanical move: the `pyproject.toml`
moves with it, and only the install URL each dashboard uses changes.
