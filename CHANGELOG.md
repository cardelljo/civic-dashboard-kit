# Changelog

## [Unreleased]

## [0.1.0] — 2026-07-27

First release of this repo. Extracted (with history — see `git log`) from
`cardelljo/901education`'s `toolkit/` directory, where this code had already
gone through several rounds of real use across two dashboards
(`cardelljo/901justice`, `cardelljo/901education`) and one in progress
(`cardelljo/901economy`). Nothing about the code changed in the extraction
beyond packaging (src-layout, distribution renamed from `civic-toolkit` to
`civic-dashboard-kit`, import path unchanged at `toolkit.*`).

Modules at this release: `arcgis.py`, `census.py`, `fred.py`, `bea.py`,
`ai_extract.py`, `pdf_report.py`, `geo.py`, `snapshot.py`, `observations.py`,
`metrics.py`, `postgres_store.py`. See `README.md`'s module reference table.
