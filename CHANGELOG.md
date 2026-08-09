# Changelog

Entries name **which half** changed — Python (pip, `toolkit.*`) or TypeScript
(npm, `ui/`) — because one tag covers both and a consumer of one half should be
able to tell at a glance whether a release concerns it.

## [Unreleased]

## [0.3.0] — not yet tagged

**Both halves.** This is the release that makes the repo dual-published
(docs/ARCHITECTURE.md §7).

### Added — TypeScript half (new)

- `package.json` beside `pyproject.toml`, and a `ui/` directory outside `src/`.
  Install with `npm install github:cardelljo/civic-dashboard-kit#<sha>`; pin a
  commit, not `#main`, exactly as the Python side does.
- `ui/types.ts` — the canonical `DataStatus` union, plus `resolveStatus()`, the
  `status ?? (isSample ? 'sample' : 'live')` fallback for snapshots written
  before `status` existed. Both components route through it instead of carrying
  their own copy of the rule, which is what the three dashboards did.
- `ui/SampleBadge.tsx` and `ui/DataStatusPanel.tsx`, lifted from 901economy
  `bd3f1bb1`. The three dashboards' copies were byte-identical apart from
  whether `DataStatus` was declared locally or imported, so the props are
  unchanged and adoption is a swap of import paths.
- Ships raw `.tsx`, no build step. Consumers add `transpilePackages` and — this
  one fails silently — add the package to their Tailwind `content` globs, or the
  components render unstyled. See the README's "Adopting the TypeScript half".

### Changed — Python half

- **`snapshot.DATA_STATUSES` enumerates the six valid `_meta.status` values, and
  `build_meta()` now raises `SnapshotError` on anything else.** `status` was an
  unconstrained `str`, so `status="livee"` produced a valid-looking snapshot that
  renders as sample data in the frontend's fallback path. Potentially breaking
  for a caller passing a status outside the union — every committed
  `_meta.status` across all three dashboards was checked first and all are on the
  union, so no existing data file or pipeline is affected.
- `validate_meta()` checks `_meta.status` for membership, not just presence. Only
  reachable on the `allow_sample=True` path; the default path already required
  exactly `"live"`.

### Added — CI and tests

- `tests/test_data_status_union.py` fails if `snapshot.DATA_STATUSES` and the
  `ui/types.ts` union stop matching. It runs in the **Python** job, so a JS-only
  change adding a status cannot land without the Python side. §7 justified one
  repo on this coupling; before this test the coupling was an intention.
- `tests/test_ci_guards.py` fails the build when `TOOLKIT_TEST_DATABASE_URL` is
  unset in CI. `pytest` exits 0 when every Postgres test skips, so a dropped
  `env:` block read as a passing build. It lives in its own module because
  `test_postgres_store.py`'s module-level `pytestmark` would skip the guard in
  exactly the case it detects.
- A `typescript` CI job: `tsc --noEmit` and `vitest run` (16 tests over the two
  components and `resolveStatus`).
- The Python job's Postgres service is now `postgis/postgis:16-3.4` rather than
  `postgres:16`, matching the image the shared instance is provisioned from
  (§3), so a future test needing PostGIS does not need a CI change first.

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
