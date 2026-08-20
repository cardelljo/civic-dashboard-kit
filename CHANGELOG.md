# Changelog

## [Unreleased]

### Added
- `eligibility.py`: publication eligibility gate (`is_publishable()`, `load_meta()`,
  `source_line()`, `audit_all()`), promoted from 901justice's
  `scripts/publication/eligibility.py`. Unlike the original, the file-loading
  functions take the caller's `data/` directory as an explicit parameter instead
  of deriving it from `__file__` — the toolkit doesn't assume where it lives
  relative to a consuming repo.

## [0.2.0] — 2026-08-03

Cut so consumers can pin a version instead of tracking `main`. Both dashboards
depended on `@main`, which meant a change here could break their CI with no
commit in their repos — and this release contains exactly such a change (see
the test-double note below). 901economy's tests survived it only because they
were updated in the same batch; 901education's survived only because it happens
to import nothing from `census.py`. Neither is protection, hence the tag.

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

### Fixed
- `postgres_store`'s ImportError pointed at a dead install path. It told anyone
  missing the `postgres` extra to install
  `civic-toolkit[postgres] @ ...901education.git@main#subdirectory=toolkit` —
  the pre-extraction repo path *and* the pre-rename distribution name. That is
  the message a user sees when the import actually fails, so it sent them
  somewhere that no longer resolves.

### Docs
- New [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md): the home for decisions
  about infrastructure no single dashboard owns — the shared Postgres instance,
  schema-per-dashboard layout, PostGIS, and the shared `geo.boundaries` store.
  Those had been recorded in one dashboard's `PLAN.md` despite binding all
  three. States the tiering: code this package ships → `README.md`; shared
  infrastructure → that file; single-dashboard concerns → that repo's own docs.

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
