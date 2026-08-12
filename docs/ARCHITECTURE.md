# Shared Infrastructure Decisions

**Status:** Adopted · **Scope:** every dashboard in the series —
[901justice](https://github.com/cardelljo/901justice),
[901education](https://github.com/cardelljo/901education),
[901economy](https://github.com/cardelljo/901Economy)

## What belongs in this file

Decisions about infrastructure **no single dashboard owns**: the database
instance they share, the schemas inside it, and the geographic data they all
plot. These bind more than one repo, so recording them inside any one
dashboard's `PLAN.md` guarantees the others never learn about them.

Three tiers, by who is bound:

| Tier | Home | Examples |
|---|---|---|
| Code this package ships | [`README.md`](../README.md) | `observations.py` vs. `postgres_store.py`; client behavior |
| **Shared infrastructure** | **this file** | the Postgres instance, schema layout, PostGIS, `geo.boundaries` |
| One dashboard only | that repo's `PLAN.md` / `docs/` | indicator lists, section layout, refresh cadence |

This repo is public. Architecture only — no hostnames, credentials, or
connection strings.

Fork-per-dashboard and the toolkit-extraction history are recorded separately in
[`901education/docs/ARCHITECTURE.md`](https://github.com/cardelljo/901education/blob/main/docs/ARCHITECTURE.md).

---

## 1. Every dashboard's store is Postgres

**Superseded, 2026-08:** this section previously said the store choice was per
dashboard and that the NDJSON-vs-Postgres split was "not drift" but a legitimate
scale judgment. That reasoning was sound on scale and incomplete on the thing
that actually mattered.

**All three dashboards store their data in the shared Postgres instance.** The
git-committed NDJSON ledger is a transitional state for 901education, not a
destination.

### Why the earlier reasoning was incomplete

It weighed only volume — a single-district annual dashboard against a ~30-source
multi-cadence one — and on volume it was right. What it never weighed is
**GitHub as operational infrastructure**. A git-committed ledger makes the data
layer depend on a hosting account, its availability, its rate limits, its
auth, and a commit step in every write path. That is a maintenance burden and a
single point of failure the series does not want, and it does not get better with
more dashboards.

The original reason it looked fine: 901justice began as an experiment in whether a
dashboard could be assembled at all, so static files in git were the cheapest
possible substrate. The series has outgrown the assumption rather than
disproved it.

`toolkit.observations` stays in the package — it is a working NDJSON store and
useful to anyone with a genuinely file-shaped problem. It is simply no longer
where these three dashboards are heading.

### What this does NOT change

**The delivery mechanism is a separate question, still open.** §3 already draws
this line: Postgres moves the *source of truth*, not how a page gets its bytes.
Whether each site remains a static export or becomes dynamic is being decided on
its own evidence — see §1.1. Do not read "the store is Postgres" as "the frontend
queries Postgres."

Also unchanged: the append-only discipline, the `_meta` provenance contract, and
the human-review gate. Those are store-independent by design.

### Migration is real work, and not yet planned

Two dashboards have to get there, and they are not the same job:

| | Today | What the move requires |
|---|---|---|
| 901economy | Postgres | done — it is the reference implementation |
| 901education | NDJSON ledger, ~4 pipelines writing it | a `schema.sql`, per-source `fetch_*.py` rewrites onto `postgres_store`, **and a decision on the existing ledger's history** |
| 901justice | static JSON, no store module | net-new: schema, store adoption, and its daily cron re-pointed |

**The open question on education is history, not code.** Its ledger holds real
observations. Backfilling them into Postgres preserves the series; starting fresh
from cutover loses it. That is a data-integrity call, and given the append-only
promise this project makes to its readers, losing history silently would break it
— so it needs an explicit answer either way, not a default.

Tasks for both are not written yet. A planning prompt for that work is in
[`docs/prompts/store-migration-planning.md`](prompts/store-migration-planning.md);
its output belongs in each dashboard's own `PLAN.md`, not here.

## 1.1 Open: static export or dynamic app?

**Not decided. Recorded so it stops being an undercurrent.**

§1 moved the source of truth to Postgres. It did not answer how a page gets its
bytes, and the two are genuinely separable — §3 says so explicitly.

The question surfaced from real pressure, not preference: 901justice began as an
experiment in whether a dashboard could be assembled at all, so static files in
git were the cheapest substrate. The series now wants functionality that a
pre-baked artifact serves poorly.

**What a dynamic app buys:**

- No build-and-commit step between a pipeline run and a visible number — the same
  GitHub-as-infrastructure dependency §1 removed from the write path, removed from
  the publish path too.
- Queries that cannot be pre-baked. Nine counties × ~24 years × N indicators ×
  filters is combinatorial; pre-generating every view stops scaling.
- The T3 admin review queue **must** be dynamic — it writes `approvals`. A
  dynamic surface is coming regardless.
- One container per dashboard rather than two.

**What the static export currently buys, which is easy to undervalue:**

- **A published figure is a reviewable artifact.** Committed JSON has a diff and a
  history: a bad pipeline run shows up as a change someone can see before it ships.
  A live query shows whatever the database says right now. The `pending_review`
  gate still holds — `indicators_current` filters on `status = 'success'` — but
  gate and diff catch different failures.
- **Availability.** nginx serving files stays up when the database does not. A
  civic dashboard going dark because of a database issue is a real regression.
- Cost and simplicity: no query per page load, no connection pool, no caching tier.

**A middle option that may get most of the benefit:** keep the static export but
**generate it in the container onto a volume nginx serves, instead of committing it
to git**. That removes GitHub from the publish path — the actual complaint — while
keeping the fixed-artifact and availability properties. Then go dynamic only for
what genuinely cannot be pre-baked: the admin queue, and arbitrary user filtering.

Deciding this needs a list of the specific features being asked for, so the
"cannot be pre-baked" set is real rather than assumed. Until then, **assume static
export** — it is what all three repos ship today (`output: 'export'`).

## 2. One Postgres instance, one schema per dashboard, plus a shared `geo`

```
economy.indicators, economy.geographies, economy.source_runs, …
education.…            (only if education outgrows the NDJSON ledger — no forced migration)
justice.…              (only if/when justice adopts Postgres — deliberately left a judgment call)
geo.boundaries         ← shared: municipalities, zips, tracts, council/commission districts
```

Standard practice, and it settles the duplication problem directly: without a
shared `geo`, three dashboards each carry their own copy of the same Shelby
County polygons — the exact duplication that justified extracting this package.

**The honest cost is coupling.** One instance means one outage surface and one
migration surface. At three small dashboards on a single host that trades well
against one backup job and one thing to patch. Schemas are already separate, so
splitting later is mechanical rather than a rewrite.

**Adoption is opt-in.** A dashboard on the NDJSON ledger is not required to
migrate. It may still read `geo.boundaries` at build time without moving its
own indicator storage.

## 3. PostGIS: enable it

Not because boundaries need a database to be *stored* — committed GeoJSON does
that fine — but because there are real spatial operations that are painful
without it:

- point-in-polygon (attributing located records to council districts)
- district ↔ tract overlays (joining "which districts got X" to "which carry Y")
- the zip ↔ tract crosswalk needed whenever two sources publish at different
  geographic grains
- `ST_Simplify` for display, which beats `toolkit.geo`'s hand-rolled
  Douglas-Peucker

**What PostGIS does not change, stated plainly so nobody expects otherwise: the
frontend still cannot query it.** Every dashboard stays a static export. Each
pipeline exports the boundary subsets it needs to `data/boundaries/*.json`, and
the site imports those committed files at build time with no network call.
PostGIS moves the *source of truth*, not the delivery mechanism.

**Provision from a PostGIS-capable image even before the extension is needed.**
`CREATE EXTENSION postgis;` is trivial on an image that supports it; swapping
the image under a running database later is not.

**The image is `postgis/postgis:18-3.6-alpine`** — what the Coolify host actually
runs, so CI in this repo matches it rather than an aspiration. This supersedes an
earlier `postgis/postgis:16-*` recommendation written when `postgres_store` had
only been exercised against Postgres 16. Nothing in `db/schema.sql` or
`postgres_store` is version-sensitive: between them they use `TEXT`,
`TIMESTAMPTZ`, `BOOLEAN`, `BIGSERIAL`, `JSONB`, `NUMERIC` and one `DISTINCT ON`,
with no `ON CONFLICT`, `MERGE`, window function, or `LATERAL` anywhere. All of
that predates 16.

**One initdb-time choice the alpine variant forces: collation.** Collation is
fixed at `initdb` — changing it later means a reindex or a dump-and-reload, the
same class of irreversibility as the image swap above.

The failure mode is worse than "you get C collation," and this is **observed, not
predicted** — from this repo's own CI running the same image
([run 31507379253](https://github.com/cardelljo/civic-dashboard-kit/actions/runs/31507379253)):

```
sh: locale: not found
The database cluster will be initialized with locale "en_US.utf8".
WARNING:  no usable system locales were found
```

`initdb` **accepts** `en_US.utf8` and carries on. So `pg_database.datcollate`
will report `en_US.utf8` while musl provides no such locale and text actually
orders by byte value. The catalog does not match the behavior, which is the kind
of discrepancy that gets diagnosed as a data bug years later.

So choose explicitly at `initdb` rather than taking the default: either
`--locale-provider=icu` with a named ICU locale, or `--locale=C` so the catalog
tells the truth. Plain C is fine for this data — `period` is `YYYY` / `YYYY-MM` /
`YYYY-QN` and sorts correctly as bytes, `indicator_id` / `geo_key` /
`source_key` are ASCII, and `indicators_current` breaks ties on a timestamp. It
surfaces only in locale-aware ordering of display names.

**Also check the data directory actually persists.** Postgres 18 images put
`PGDATA` at `/var/lib/postgresql/18/docker`, not the `/var/lib/postgresql/data`
of earlier majors — visible in the same run (`pg_ctl -D
/var/lib/postgresql/18/docker`). A volume mount written for the old path would
leave the cluster on ephemeral container storage, where everything works until
the first restart. Verify by restarting the container and confirming the data
survived, before there is data worth losing.

## 3.1 Bootstrapping the instance: [`db/bootstrap.sql`](../db/bootstrap.sql)

One script, run once as superuser, before any dashboard applies its own
`schema.sql`. Idempotent. It creates all four schemas, four roles, the grants,
the `search_path` defaults, and `geo.boundaries` — for **all three dashboards at
once**, because one database means the roles interlock and splitting them across
files would impose a run order nothing enforces.

It lives here rather than in a dashboard because it is precisely what §2 and §4
own. A dashboard's own tables stay in its own repo.

**Unqualified SQL plus a per-role `search_path` is the mechanism, not table-name
prefixes.** `toolkit.postgres_store` writes `INSERT INTO indicators`; the
connecting role supplies the namespace via
`ALTER ROLE economy_app SET search_path = economy, geo, public`. That is a
one-time catalog setting, inherited by every later connection, and it is why one
store module serves every dashboard — hardcoding `economy.indicators` would make
it economy-only, and parameterizing the schema into every query means threading a
name through the whole API.

The failure mode to know: a role *without* that setting resolves to `public` and
**works while writing to the wrong place**. Mitigation is structural — nothing
belongs in `public` but PostGIS's own `spatial_ref_sys`, so a missing
`search_path` errors with "relation does not exist" rather than silently
succeeding.

**Creating a schema is not a migration commitment.** `education` and `justice`
exist from the first run, but §1 still governs the store choice — education is on
the NDJSON ledger and justice is a deliberate judgment call. Their namespaces
exist so either can read `geo.boundaries` at build time without owning any of it,
and so adopting Postgres later needs no second bootstrap.

**`geo` gets its own role.** `geo_loader` owns the schema; the three app roles get
`USAGE` + `SELECT` and nothing more. If `economy_app` owned `geo`, the other
dashboards would read from a namespace one dashboard controls, and "shared" would
hold only by convention. `ALTER DEFAULT PRIVILEGES` covers tables added later, so
a second `geo` table does not silently become unreadable.

**No passwords in the file** — this repo is public. Roles are created with `LOGIN`
and no password, so they cannot authenticate until `\password <role>` is run in
the same psql session. That prompts and hashes client-side, keeping the secret out
of the file, the shell history, and the process list.

Verified against a real Postgres 18 + PostGIS 3.6: two consecutive runs both exit
0; the four schemas come out owned by their roles; 901economy's `schema.sql`
applied as `economy_app` puts its 6 tables in `economy` with only
`spatial_ref_sys` in `public`; an unqualified `INSERT` lands in `economy`;
`economy_app` can read `geo.boundaries` and is refused on write with
`permission denied for table boundaries`.

## 4. The shared `geo` schema

```sql
CREATE SCHEMA IF NOT EXISTS geo;
CREATE EXTENSION IF NOT EXISTS postgis;

-- One row per boundary polygon, across every layer any dashboard plots.
-- Deliberately NOT keyed to any dashboard's own `geographies` table: a tract
-- exists as geography whether or not a given dashboard publishes an indicator
-- for it. Join on `geo_key` when a dashboard needs to tie a polygon to its own
-- geography row.
CREATE TABLE geo.boundaries (
    boundary_id   BIGSERIAL PRIMARY KEY,
    layer         TEXT NOT NULL,        -- 'municipality' | 'zip' | 'tract'
                                        -- | 'city-council' | 'county-commission'
                                        -- | 'state-house' | 'state-senate' | 'congressional'
    geo_key       TEXT NOT NULL,        -- natural key within the layer: place GEOID
                                        -- '4748000', zip '38114', tract '47157009700'
    name          TEXT NOT NULL,
    geom          geometry(MultiPolygon, 4326) NOT NULL,   -- WGS84, web-map native
    vintage       TEXT NOT NULL,        -- 'TIGER 2024', 'Shelby County GIS 2023-03-11'
    source_url    TEXT,
    retrieved_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (layer, geo_key, vintage)    -- re-pulling a vintage is idempotent; a NEW
                                        -- vintage is a new row, so redistricting and
                                        -- annexation keep their history
);

CREATE INDEX idx_geo_boundaries_layer ON geo.boundaries (layer, geo_key);
CREATE INDEX idx_geo_boundaries_geom  ON geo.boundaries USING GIST (geom);
```

**Boundaries are versioned, not static.** `vintage` is required and part of the
unique key, so a tract redraw or a municipal annexation adds rows rather than
overwriting them — the same append-only discipline the indicator stores use, for
the same reason: a map published last year should still be reconstructible.

**Refresh cadence: rare and on demand, never per build.** Tracts change on a
decennial cycle; municipal limits change on annexation. Regenerating these on a
nightly JSON build would be pure waste.

## 5. Municipal boundaries: all seven Shelby County municipalities

Shelby County has seven incorporated municipalities — **Memphis, Bartlett,
Collierville, Germantown, Lakeland, Millington, Arlington**. All seven belong in
`geo.boundaries`, not Memphis alone.

The six suburbs formed **their own municipal school districts in 2014**, so the
municipal boundary *is* the school district boundary there. That makes this a
cross-dashboard equity comparison rather than any one dashboard's nicety:
education compares districts, economy separates city-vs-suburb tax base and
city-vs-MSA framing, justice already carries council and commission districts
that sit inside them.

Source: Census TIGER **Places** for TN (Memphis is GEOID 4748000), filtered to
Shelby County — one pull yields all seven.

## 6. Where boundary data lives today

901justice holds the only real polygons in the series today, under
`data/boundaries/`: city council, county commission, congressional, state house,
state senate, Memphis zips, and MPD ward/station areas. It has **no city-limits
polygon** — a union of council districts is not a city boundary.

`toolkit.geo` is 901justice's `convert_boundary_shapefiles.py`, generalized and
moved here. **There is no third copy of that parsing logic to write**; loading
into `geo.boundaries` uses this package.

Open, not decided here: whether the MPD ward/station-area layers belong in the
shared schema or stay justice-specific. They are currently treated as
justice-specific.

## 7. Shared frontend code ships from this repo, as a second package

**The data-status UI is extracted here, and this repo becomes dual-published:**
a Python distribution installed with pip and a TypeScript package installed with
npm, from one repo, with both manifests at the root. This supersedes
901education's "frontend extraction remains unevaluated" and 901economy's task 8
note that deferred to it.

### Why one repo rather than a second one

**npm cannot install a package from a subdirectory of a git repo; pip can**
(`#subdirectory=`). A separate `901-ui` repo would work, but so does putting
`package.json` beside `pyproject.toml` at this repo's root — the two package
managers look for different manifests and ignore each other. One repo means the
`DataStatus` union and the Python code that reasons about the same status values
cannot drift apart in separate release cycles.

This is not hypothetical caution. The series already hit the subdirectory
problem once: installing the toolkit from 901education's `toolkit/` subdirectory
failed on cross-repo auth, which is what forced the extraction recorded in
[901education decision 3](https://github.com/cardelljo/901education/blob/main/docs/ARCHITECTURE.md).
Root-level manifests avoid the same class of problem for the JS half.

### What is in scope — deliberately narrow

901education's codebase analysis found **~85% of the frontend is
domain-specific**, with the genuinely shared remainder being the `_meta`
provenance contract and the data-status UI. That finding stands and it bounds
this decision. Extracted:

- the canonical `DataStatus` union, and `resolveStatus()` — the
  `status ?? (isSample ? 'sample' : 'live')` fallback every consumer of a
  pre-`status` snapshot needs
- `SampleBadge` and `DataStatusPanel`
- `SourceLine` — the standard attribution line (see §7.1; this one is a
  standardization, not a lift)

Not extracted: sections, charts, narrative components, branding, layout shell.
Those are the 85%.

The evidence that the status UI crossed the line is duplication, not drift.
Measured at 901economy `bd3f1bb1`, 901education `5399247c`, 901justice
`a7cdf9f4`: `SampleBadge.tsx` is 57/58/58 lines and `DataStatusPanel.tsx` is
241/242/242, but **the whole of that difference is one line** — justice imports
`DataStatus` from `@/lib/types`, the other two declare it locally. `diff` is
otherwise empty across all three. So the earlier "drift already in progress"
framing overstated it: what the three repos have is three byte-identical copies
held in sync by nothing. That is a cleaner case for extraction than drift would
be — the lift needed no reconciliation — and rule-of-three is met either way.

**`lib/choropleth.ts` does not come along yet.** 901economy's task 8 kept it
dependency-free specifically to be cheap to lift, and that was right — but it is
still the first real choropleth in the series. Rule-of-three applies to it
independently of this decision. What changes for task 8 is only that the
destination now exists and is named; the timing rule is unchanged.

## 7.1 The source line is standardized, not extracted

**These are two different arguments and only one of them is rule-of-three.**
Extraction asks whether the same code exists three times; standardization asks
whether three dashboards should present the same thing the same way. The
attribution line fails the first test and passes the second, and the second is
the one that matters for it — "every figure carries source and vintage" is
already a stated non-negotiable in each repo, but nothing said *how*, so three
repos answered differently and no rule was checkable.

An earlier revision of §7 struck the source line on the grounds that there was
no shared code to lift. That was true and beside the point.

### What the inventory found

Ten `Source:` call sites across the three repos are not ten attribution lines.
They are three different kinds of thing sharing a prefix:

| Kind | Sites | Example |
|---|---|---|
| Structured attribution — name, vintage, link | 4 | justice `JailSection`: `Shelby County Jail — {reportMonth} · Source: {source}↗` |
| Attribution fused to a methodology caveat | 4 | education `AcademicOutcomesSection`: `note="Source: TDOE TCAP Assessment Files. 2019-20 canceled and 2020-21 disrupted by COVID; treat those years with caution."` |
| Prose that merely begins with the word | 2 | justice `CommunitySection`: six lines on what is and is not machine-extracted |

So the standard has to **split structured attribution from caveat prose**. That
split is most of the value: a caveat baked into a string literal cannot be
searched, audited, or shown consistently, and today most of them are.

### The standard

```
Source: {source}↗ · {vintage} · {geography}   [caveat]
```

- **`·` rather than commas**, so an absent `vintage` or `geography` drops out
  without leaving stray punctuation.
- **The link wraps the source name** — the thing a reader clicks to verify a
  figure. 901economy currently links the vintage instead, which is less
  discoverable.
- **The form is fixed.** A standard each dashboard restyles is not a standard.
  What *is* local: the component defaults to the `data-note` class, which all
  three repos already define in `globals.css` with their own muted color, so the
  line inherits local theming without importing a palette.
- **`caveat` accepts markup**, because justice's caveats contain links.

### A source name is optional, and that is a concession to real data

901economy has **no per-row publisher name**. Its rows carry
`source_key: 'bea-gdp'` and `source_url`; the only human-readable name in its
`_meta` is `sourceName: "Postgres indicators_current"`, which names its own
pipeline, not the publisher. That is *why* it renders `{vintage} · {geography}`
rather than a source name.

So `source` is optional and `vintage` is promoted into the primary slot when it
is absent. Requiring a name would have blocked economy's adoption behind a
`source_key` → display-name registry for ~30 sources. Uniform shape now, complete
content later; building that registry is 901economy's own follow-up, not a
prerequisite.

**Adoption changes what visitors see**, unlike the data-status lift. Justice's
subheaders reorder (`Source:` moves to the front), education's four `note=`
strings split into attribution plus caveat, and economy's lines gain the
`Source:` label. That is the point of standardizing, but it means each adoption
is a visible change to review on the page, not just a green build.

### Mechanics

```
pyproject.toml     ← Python distribution (unchanged)
package.json       ← TypeScript package (new, beside it)
src/toolkit/       ← Python source (unchanged)
ui/                ← TypeScript components (new, outside src/ so setuptools'
                     `where = ["src"]` does not try to package it)
```

- **Install, JS side:** `npm install github:cardelljo/civic-dashboard-kit#<sha>`.
  Package name `civic-dashboard-kit`, single entry point — everything imports
  from the package root, `import { SampleBadge } from 'civic-dashboard-kit'`.
  SHA pinning works exactly as it does for pip, so both halves pin the same way
  ([901economy/pyproject.toml](https://github.com/cardelljo/901Economy/blob/main/pyproject.toml)
  and [901education/scripts/requirements.txt](https://github.com/cardelljo/901education/blob/main/scripts/requirements.txt)
  pin `351a0bbd` = 0.2.0 today).
- **Consumption:** ship raw `.tsx` and have consumers add `transpilePackages` in
  `next.config.js`. No build step, no compiled artifacts committed, nothing to
  keep in sync.
- **Versioning:** one repo, one tag, covering both halves. `CHANGELOG.md` entries
  must name which half changed, because a JS consumer reading it will otherwise
  see Python-only releases it has no reason to act on.
- **CI runs both suites.** A JS-only change must not be able to ship without the
  Python tests, or vice versa.

### What building it changed

**The union is now actually canonical. It was not before.** This section
justified one repo partly on the grounds that it "keeps the `DataStatus` union
next to the Python code reasoning about the same values" — but on the Python
side `status` was an unconstrained `str` (`build_meta(status: str = "live")`),
and `validate_meta` only checked that it was non-empty. There was nothing for
the TypeScript union to be pinned to; `status="livee"` was a valid snapshot.
So:

- `snapshot.DATA_STATUSES` enumerates the six values, and both `build_meta` and
  `validate_meta` reject anything else. Verified against every committed
  `_meta.status` in all three dashboards first — all on the union, so nothing
  newly fails. (901justice's `data/doj_findings.json` carries `published` /
  `not_linked` / `not_available`, but those are domain milestone statuses on
  `responseMilestones[]`, not `_meta.status`.)
- `tests/test_data_status_union.py` parses `ui/types.ts` and fails if the two
  lists stop matching. It runs in the **Python** job, so a JS-only change that
  adds a status still has to add it to Python. This is the mechanism the
  one-repo decision claimed; until it existed the claim was an intention.

**Two adoption requirements that fail silently.** Both are consumer-side config,
neither is caught by any test in this repo:

1. **Tailwind must scan the package.** Tailwind 3 generates only the classes it
   finds in `content` globs, and does not scan `node_modules`. Without
   `'./node_modules/civic-dashboard-kit/ui/**/*.{js,ts,jsx,tsx}'` added to
   `content`, the components mount correctly and render **unstyled**.
2. **`brand.blue` must exist.** `DataStatusPanel` uses `text-brand-blue` for its
   two verify links. All three dashboards define it today, so this is a
   documented requirement rather than a change — but it means the package is not
   theme-free, and a fourth dashboard without that token gets inherited-color
   links.

**Adoption order is not a matter of taste.** Adopt in **901economy or
901education first, never 901justice first.** Justice is a live site with a
daily cron, no test suite, and `typescript.ignoreBuildErrors: true` — its
`npm run build` passes *through* type errors, so it structurally cannot verify
the swap. A repo with a real gate proves the package before the one that can't.

### The honest cost

**The repo stops being one thing.** A contributor now has to know which half
they are touching, the CI is two toolchains, and an npm git install clones the
Python source it will never use. Version coupling is real: a Python-only release
still moves the tag JS consumers see. SHA pinning bounds that — consumers only
move when they choose to — but it puts the burden on the CHANGELOG to be honest
about scope, which is a discipline, not a guarantee.

The alternative (a second repo) trades that for a worse failure: two repos whose
status vocabularies drift, which is the exact problem being fixed.

### What this does not change

**The static-data philosophy is untouched.** These components are presentational
— they receive already-imported JSON as props. No component in this package
fetches anything, and no dashboard frontend queries a database or an API. Each
site still imports pre-built JSON at build time. If that ever changes it will be
a separate decision, argued on its own.

Also unchanged: fork-per-dashboard (this is a shared *library*, not a platform —
the same model already applied to the Python toolkit); the per-dashboard store
choice in §1; the Python distribution name and its `toolkit.*` import path.

**Adoption is opt-in, and 901justice specifically is not on a schedule.** It is
a live site with a daily cron, and it builds with type errors ignored — so its
`npm run build` cannot fail on a bad component swap. It does have a Python test
suite (§8 corrects an earlier claim here that it had none), but a Python suite
cannot verify a React swap. Its existing duplicate components keep working
indefinitely, and nothing here obliges any dashboard to migrate on someone else's
timeline.

### What does not go in this repo

**The admin application is a separate repo.** It is an application, not a
library: no dashboard installs it, and bundling it would drag its dependency tree
into every git clone. That is the reason — not secrecy. Its configuration belongs
in environment variables regardless of where the source lives.

---

## 8. The verification floor across the three dashboards

**Why this is in the shared file.** A single dashboard's test setup is its own
business, but "are the three at a consistent floor" is a comparison no one repo
can hold, and the plan of record was working from a table that had drifted out of
date. Measured directly from the workflows and configs at 901economy `bd3f1bb1`,
901education `5399247c`, 901justice `a7cdf9f4`.

### Measured state

| | Type errors fail the build | Python tests on PRs | Frontend tests | CI jobs on a PR |
|---|---|---|---|---|
| 901economy | yes | yes — 7 files, with a Postgres service, plus `validate_snapshots.py` | **yes** — vitest, 2 files | `pipeline` + `frontend` (`npm test`, `lint`, `build`) |
| 901education | yes | yes — 4 files, `pytest -q` | none | `build` + `tests` |
| 901justice | **no** — `typescript.ignoreBuildErrors` *and* `eslint.ignoreDuringBuilds` | yes — 9 files, `pytest -v --strict-markers` | none | `tests` + `build` |

### Two items on the work list are already done

- **"Add pytest to 901education's build-check.yml."** Already there: a `tests`
  job installs `scripts/requirements-dev.txt` and runs `pytest -q`. The earlier
  note that it "never installs requirements.txt" is wrong in a way worth
  recording — `requirements-dev.txt` begins with `-r requirements.txt`, so the
  pinned `civic-dashboard-kit` commit *is* installed and exercised on every PR.
  That makes education's CI a real gate on a bad toolkit pin, which was the
  concern behind the item.
- **"Start a test suite in 901justice."** Already there: 9 files, added with the
  ArcGIS consolidation, running on `pull_request`. An earlier revision of this
  document (§7) described justice as having "no test suite"; that is corrected.

### What is actually still uneven

1. **Frontend tests exist in one repo of three.** Only economy runs any (vitest,
   2 files). Education and justice have zero `*.test.tsx`. This is the gap that
   matters for the `ui/` adoption in §7 — and it is why adoption order is not
   arbitrary.
2. **901justice verifies nothing about its frontend.** With both
   `ignoreBuildErrors` and `ignoreDuringBuilds` set, `npm run build` passes
   through type *and* lint errors. **This is a deliberate judgment call about a
   live site, not an oversight — do not flip it without a decision.** The
   consequence to plan around is narrow: justice cannot self-verify a frontend
   change, so a frontend change should be proven elsewhere first.
3. **901economy's CI Postgres is `postgres:16`; the real instance is
   `postgis/postgis:18-3.6-alpine`.** Two divergences in one, and the major
   version is the bigger of them: economy's suite has never run against the
   Postgres its pipeline will actually write to. Harmless so far — nothing in its
   schema is version-sensitive (§3) — but the first PostGIS-touching test would
   fail in CI while passing against the real database, which is the confusing
   direction. This package's own CI matches the host image; economy's is its own
   call, and its own repo.

### The floor itself

Four requirements, each of which exists because it has already failed here:

- **A skipped test is not a passing test.** `pytest` exits 0 when every database
  test skips for want of a connection string. Assert the environment rather than
  trusting the exit code — this repo's `tests/test_ci_guards.py` is the worked
  exemplar, and it deliberately lives outside `test_postgres_store.py` because
  that module's `pytestmark` would skip the guard in exactly the case it detects.
- **Zero checks is not a pass.** Confirm *which* checks ran, not that the badge
  is green.
- **A pipe destroys an exit code.** `pytest ... | tail -2 && git commit` commits
  on failure.
- **A test that has never failed may assert nothing.** Break the code
  deliberately and confirm the suite goes red.

Whether each repo's suite can currently all-skip has **not** been verified here;
only its configuration has.
