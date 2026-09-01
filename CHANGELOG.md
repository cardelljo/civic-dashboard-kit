# Changelog

Entries name **which half** changed — Python (pip, `toolkit.*`) or TypeScript
(npm, `ui/`) — because one tag covers both and a consumer of one half should be
able to tell at a glance whether a release concerns it.

## [Unreleased]

### Added — Python half

- `postgres_store.Observation` gained four optional, nullable fields — `subject`,
  `grade`, `unit`, `row_key` — so one store module can serve a dashboard whose
  observation grain is finer than 901economy's. 901education needs them: all
  56,274 rows of its NDJSON ledger set `row_key`, and its `build_data_files.py`
  queries the column directly.
  - `append()` names a column only when some observation in the batch sets it,
    so a batch setting none of them emits exactly the statement it always did.
    901economy's live `indicators` table, which has none of these columns, keeps
    working with no `ALTER TABLE` and no change at its call sites.
  - Setting one against a table that lacks the column raises `UndefinedColumn`
    rather than silently dropping the value.
  - Note for anyone adding these columns to an existing database: `indicators_current`
    is `SELECT DISTINCT ON (...) i.*`, and a view fixes its column list at
    CREATE time — an `ALTER TABLE` alone will not surface them, the view has to
    be recreated. Found while writing the tests.

- `postgres_store.record_run()` gained six optional run-level provenance arguments —
  `script`, `source_name`, `source_url`, `source_vintage`, `fetched_at`,
  `content_hash` — mirroring what `observations.record_run()` records per run.
  Same contract as above: a column is named only when its argument is supplied,
  so a `source_runs` table without them is untouched.
  - `fetched_at` is deliberately separate from `started_at` (which defaults to
    `now()`). A backfilled historical run keeps the provider's real date instead
    of the migration's; conflating the two would silently restamp history.
  - The dedup *policy* built on `content_hash` stays in 901education
    (`scripts/observations_utils.py`) — that is one dashboard's rule about when
    an unchanged re-fetch should skip its append, not toolkit behaviour.

- `eligibility.py`: publication eligibility gate (`is_publishable()`, `load_meta()`,
  `source_line()`, `audit_all()`), promoted from 901justice's
  `scripts/publication/eligibility.py`. Unlike the original, the file-loading
  functions take the caller's `data/` directory as an explicit parameter instead
  of deriving it from `__file__` — the toolkit doesn't assume where it lives
  relative to a consuming repo.

### Added — shared infrastructure

- `db/bootstrap.sql` — the one-time, idempotent bootstrap for the shared Postgres
  instance: all four schemas (`economy`, `education`, `justice`, `geo`), four
  roles, grants, per-role `search_path`, and `geo.boundaries` from
  ARCHITECTURE §4. One script for all three dashboards, because a single database
  means the roles interlock and separate files would impose an unenforced run
  order. Recorded as §3.1.
  - Namespaces come from a per-role `search_path`, not table-name prefixes —
    which is what lets `postgres_store`'s unqualified SQL serve every dashboard.
  - `geo` is owned by a dedicated `geo_loader`; the app roles get `SELECT` only,
    so a shared schema is not controlled by one dashboard.
  - No passwords in the file (public repo): roles get `LOGIN` with none, and
    cannot authenticate until `\password <role>` is run.
  - Verified on real Postgres 18 + PostGIS 3.6 — idempotent across two runs, and
    901economy's `schema.sql` applied as `economy_app` lands its 6 tables in
    `economy`, with `geo` writes correctly refused.

### Fixed — Python half

- **`bea.py` documented a call that cannot work.** Its module docstring and the
  README quickstart both showed `geo_fips="28700"` returning a "Memphis,
  TN-MS-AR (Metropolitan Statistical Area)" row. Checked against the live API:
  the CAGDP tables are county/state/BEA-region only. `GetParameterValuesFiltered`
  for CAGDP1's GeoFips returns 3,187 values with **zero** metro entries,
  `GeoFips=MSA` is rejected, and no `MAGDP*` table exists in the Regional
  dataset. A CBSA code **raises** (APIErrorCode 101) rather than returning empty,
  so this mattered: it taught a call that fails. Both now use a county FIPS with
  a verified figure, and `regional_gdp`'s docstring says what `geo_fips` accepts.

### Added — developer tooling

- `scripts/dev-postgres.sh` — a local Postgres 18 + PostGIS 3.6 cluster matching
  the deployed instance, installed from PGDG (Ubuntu 24.04 ships only 16). Takes
  `pytest` from *31 passed / 8 skipped* to **39 passed / 0 skipped**, so
  `postgres_store` changes are verifiable without CI. Port 5433 to leave a system
  `postgresql-16` alone; `initdb --locale=C` for the reason in ARCHITECTURE §3.
- The `civic-dashboard-dev` skill now records which credentials a Claude cloud
  session actually has, which are verified working, and that `DATABASE_URL`
  names an unreachable private host — so sessions stop speculating where one
  live call would settle it.

### Changed — CI

- The Python job's Postgres service is `postgis/postgis:18-3.6-alpine`, matching
  the image the Coolify host actually runs rather than the `16-3.4` this repo
  guessed at in 0.3.0. Major version included: the point of the service container
  is to be evidence about the database `postgres_store` will really write to.
  Nothing in the store is version-sensitive — no `ON CONFLICT`, `MERGE`, window
  function, or `LATERAL`, and its types all predate 16 — so this is a
  verification fix, not a compatibility one. docs/ARCHITECTURE.md §3 records the
  image, and the collation choice the alpine variant forces at `initdb`.

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
- `ui/SourceLine.tsx` — the standard attribution line,
  `Source: {source}↗ · {vintage} · {geography}` plus a separate `caveat` slot.
  **Not a lift.** Nothing shared existed: an inventory of ten `Source:` call
  sites found three different kinds of thing sharing a prefix — structured
  attribution (4), attribution fused to a methodology caveat (4), and prose that
  merely opens with the word (2). This owns the first and gives the caveat its own
  value instead of a string literal. `source` is optional because 901economy has
  no per-row publisher name; vintage is promoted when it is absent. Rationale and
  the inventory are in docs/ARCHITECTURE.md §7.1.
  - Unlike the two data-status components, **adopting this changes rendered
    output** — that is what standardizing means here. Review it on the page.
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
- A `typescript` CI job: `tsc --noEmit` and `vitest run` (28 tests over the three
  components and `resolveStatus`). `SourceLine`'s tests assert the rendered text
  including separator placement, since the fixed form is the thing being
  standardized.
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
