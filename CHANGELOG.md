# Changelog

## [Unreleased]

### Added
- `census.AcsClient` accepts an optional `api_key`. The Census data endpoints
  now require a free key; the variable *catalog* endpoints still do not, which
  is why the parameter is optional rather than required.
- `AcsClient` raises a message naming a missing or invalid key when Census
  answers with a non-JSON body. A keyless request is not an error status — it
  redirects to an HTML page served as **HTTP 200**, so `raise_for_status()`
  passes and the only symptom was an opaque JSON decode error.

### Changed
- `AcsClient` builds its query from a parameter dict instead of formatting
  values into the URL. Geography values that need escaping (`for=metropolitan
  statistical area/micropolitan statistical area:32820`) are now escaped by
  construction, and the key is an ordinary parameter, so tract queries can no
  longer omit it via a second hand-rolled code path.
  - The dict is encoded with `urlencode(..., quote_via=quote)` rather than
    handed to requests' `params=`, because requests encodes with `quote_plus`
    and would render those spaces as `+`. Census's published examples use
    `%20`; this keeps the wire format matching them.
  - Multi-level geographies use the repeated form Census also documents
    (`in=state:47&in=county:157`), which contains no space at all.

  **Breaking for test doubles only.** Any `monkeypatch` of
  `toolkit.census.requests.get` must now take `(url, params, timeout)`, and
  `params` is an encoded query string — assert via `urllib.parse.parse_qs`.
  No behavior change for callers of the public methods.

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
