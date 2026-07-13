# Civic Data Toolkit

Shared data-acquisition clients for Bluff City Tech community dashboards.
Extracted from [901justice](https://github.com/cardelljo/901justice)'s ETL
scripts so each retrieval pattern is implemented once and reused across
dashboards (901education today; economic development next).

| Module | Pattern | Extracted from (901justice) |
|---|---|---|
| `arcgis.py` | ArcGIS Feature Service queries with server-side aggregation (`outStatistics`/`groupBy`) | `fetch_crime_data.py`, `fetch_traffic_stops.py`, `fetch_traffic_citations.py` (3 duplicated helpers, now one) |
| `census.py` | Census ACS 5-year (detail + subject tables) and BLS time series | `fetch_community_data.py` |
| `ai_extract.py` | Multi-provider (Anthropic/OpenAI/Google) structured extraction from unstructured text | `ai_extract.py` (moved unchanged) |
| `pdf_report.py` | Recurring-PDF pipeline: download → pymupdf text → regex-first, AI-fallback | `parse_jail_pdf.py` |
| `snapshot.py` | `_meta` data-provenance contract: writer + validators | `parse_jail_pdf.py` conventions + `validate_snapshots.py` |
| `geo.py` | Dependency-free shapefile → GeoJSON (with TN StatePlane transform + ring simplification) | `convert_boundary_shapefiles.py` |

## Design rules

- **Toolkit modules are generic.** No dashboard-specific source URLs, field
  names, or narrative. Domain recipes live in `scripts/fetch_*.py` and call in.
- **Aggregate-first.** Prefer server-side aggregation and published aggregate
  files; never persist person-level records (see `DATA_SNAPSHOT_CONTRACT.md`).
- **Regex before AI.** Deterministic extraction is auditable and free; AI
  extraction is the fallback for layout drift, never the first resort.
- **Every output carries `_meta`.** Use `snapshot.build_meta()` so the
  frontend's data-status machinery can tell users exactly what they're seeing.

## Future

When a third dashboard starts (the "rule of three"), promote this directory to
its own pip-installable repository and have 901justice, 901education, and the
new dashboard consume it as a dependency. Until then it is vendored here;
improvements made in this repo should be treated as the canonical version.
