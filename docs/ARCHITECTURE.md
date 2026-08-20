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

### What selects Postgres specifically — recorded 2026-08, because the argument above does not

**The reasoning as written rules out git. It does not, on its own, select
Postgres.** Server-side SQLite removes GitHub from the write path just as
completely, at a fraction of the operational cost, and at these row counts it
would not break a sweat — the whole series is tens of thousands of rows, which
is not a volume argument for anything. Neither is the superseded volume
reasoning above; it was incomplete in the direction §1 says, and it was also
never large enough to matter.

Postgres is still right, for four reasons that are specific to it. Recording
them because a stated reason gets reused: if the reason on file is "volume,"
someone will correctly observe in a year that an annual single-district
dashboard has none, and will reach for SQLite in a case where one of these four
actually binds.

- **PostGIS** (§3). Point-in-polygon, district↔tract overlay, the zip↔tract
  crosswalk. SpatiaLite exists; it is a meaningfully worse version of this, and
  spatial work is not incidental here — it is how located records become
  district-level accountability.
- **A shared `geo` across separate repos** (§2, §4). One spatial source of truth
  read by three codebases needs a server. A file-based store gives each repo its
  own copy, which is the exact duplication that justified extracting this
  package.
- **Two concurrent writers.** The pipeline appends observations while the review
  queue writes `approvals`. This arrived with the T3 gate and is new since the
  original store decision.
- **Transactional approvals.** `pending_review → success` has to be atomic and
  auditable, and it is the gate standing between an AI extraction and a
  published figure.

The first two are why 901education may want the instance even if it never moves
its own indicator storage (§2, "adoption is opt-in"). The last two are why
whichever dashboard adopts a server-side review queue is adopting Postgres with
it.

### What this does NOT change

**The delivery mechanism is a separate decision, made separately.** §3 already
draws this line: Postgres moves the *source of truth*, not how a page gets its
bytes. §1.1 settles it — public pages stay a static export, generated into a
volume rather than committed to git. Do not read "the store is Postgres" as "the
frontend queries Postgres." It does not.

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

## 1.1 Delivery: volume-generated static pages, dynamic only where it earns it

**Decided, 2026-08.** §1 moved the source of truth to Postgres. This answers how a
page gets its bytes — a separate question, as §3 always said.

### The decision

| Surface | How it is served |
|---|---|
| Public dashboard pages | **Static export, generated into a volume nginx serves — not committed to git** |
| T3 admin review queue | **Dynamic.** It writes `approvals`; it cannot be a static artifact |
| A genuinely query-driven feature | Dynamic, once one exists and is named |

The build step stops being "write JSON, commit it, redeploy" and becomes "write
JSON to the volume the site is already serving." A pipeline run becomes visible
without a commit, a deploy, or GitHub in the path at all.

### The mechanism, spelled out — corrected 2026-08

**The paragraph above, on its own, does not work, and an external review of this
architecture read it as a decision to fetch JSON in the browser.** It is not.
Recording the correction rather than editing the sentence quietly, because the
gap between "write JSON to a volume" and "a page shows a new number" is exactly
where a wrong implementation would have landed.

Every dashboard imports its data at build time — `import peopleData from
'@/data/people.json'` under `output: 'export'`. The numbers are baked into HTML
when `next build` runs. **Writing `data/*.json` to a volume therefore changes
nothing a visitor sees.** Something has to re-render. There are only three ways
to close that, and two are rejected:

| | Verdict |
|---|---|
| Browser fetches `/data/*.json` at runtime | **Rejected.** Turns a document into an SPA: loading flash, layout shift on cellular, and empty HTML for the crawlers and link-preview bots that journalists and advocates depend on. It also puts a torn or truncated read in front of a reader. |
| Coolify deploy webhook rebuilds the image | **Rejected — it does not actually work here.** The image builds from the git context. With data no longer in git, `next build` inside that image has nothing to bake. This route only works if the data goes back into git, which is the thing §1.1 set out to stop. |
| **Build on the server** | **Adopted.** |

The adopted mechanism, run by the pipeline container after a successful
extraction (or after an approval flips a `pending_review` run), is two required
steps and one cheap optional one:

```
build_data_files.py            → data/*.json
validate_snapshots.py --strict → gate; a failure stops here and publishes nothing
next build                     → out/, into the directory nginx serves
```

That is the whole requirement. Pages change, build-time imports and the compile
step survive, and GitHub is not in the path.

**Optional, ~5 lines, worth taking:** build into `releases/<timestamp>/` and
point nginx's root at a `current` symlink you flip at the end. A symlink flip is
atomic, so nginx never serves a half-finished build, and keeping the previous
release makes rollback a flip back instead of a rebuild. Take it if it is
convenient; it is a refinement of the three lines above, **not a prerequisite for
them.**

**Scaled back, 2026-08.** An earlier revision of this section made release
directories, a retention count, and a generated diff report all mandatory parts
of the mechanism. They were imported from a first draft without re-checking
whether they earned their place, and at three small dashboards they do not. The
diff report in particular is retracted as a blocker — see the honest-cost
section below.

**Writes must be atomic at the file level too.** `Path(...).write_text()` on a
file something else may be reading is a torn read waiting to happen — write to a
temp file and `os.replace()` onto the same filesystem. This applies to the JSON
build regardless of which delivery mechanism is in use.

**One thing to check on the host before building this:** whether the two
containers can share the volume as separate Coolify resources, or whether the
builder has to be a job inside the pipeline container writing to a host bind
mount. Either shape works with the design above; the difference is operational,
and it is worth confirming rather than assuming.

### Why this rather than going fully dynamic

The complaint that drove this was **GitHub as operational infrastructure** — the
same thing §1 removed from the write path. The static export never caused that;
the *commit step* did. Removing the commit addresses the actual problem, and keeps
two properties that a live-querying frontend gives up:

- **Availability.** nginx serving files stays up when Postgres does not. A civic
  dashboard going dark because of a database problem is a real regression, and
  these sites are the public record for people who have no other copy.
- **A published page is a fixed artifact.** What a visitor sees is a file that was
  written deliberately, not the result of whatever state the database is in at that
  millisecond — including mid-pipeline-run.

**Decided without a feature list, deliberately.** There is no current set of
features that requires a dynamic public frontend. That absence is the argument:
you do not buy the cost of dynamic rendering — a query per page load, a connection
pool, a caching tier, and a new outage surface — before something needs it. The
admin queue is the one surface that genuinely needs it today, and it gets it.

**Revisit if** a real feature list arrives that is mostly user-driven querying
across many geographies, periods, or demographic groups. Pre-generating those
combinations stops scaling, and at that point dynamic public pages become the
cheaper answer rather than the more expensive one. Name the features; don't
re-argue the principle.

### The honest cost: the git diff was a review surface, and it is going away

This is the part not to gloss. Committing built JSON meant every published figure
had a diff and a history — a bad pipeline run showed up as a reviewable change
before anyone saw it. Writing to a volume keeps the *artifact* property and loses
the *audit* property. The `pending_review` gate still holds (`indicators_current`
filters on `status = 'success'`), but a gate and a diff catch different failures,
and this project has already shipped fabricated placeholder values once.

So the replacement has to be deliberate, not assumed. What already exists:

- `source_runs` records every run, its status, and its row count — server-side and
  append-only.
- `validate_snapshots.py` gates the contract *before* publish.

**Corrected 2026-08 — this section overstated the loss, and a generated diff
report is no longer a prerequisite for cutover.** Two things were conflated:

- **T3 (AI-extracted) data has a real, enforced gate**, and it is untouched by
  any of this: `pending_review` → `/admin` approve/reject → an `approvals` row,
  with `indicators_current` filtering on `status = 'success'`. That gate lives in
  the schema, not in git, and no delivery mechanism can weaken it.
- **T1/T2 data — the federal API pulls — was never gated by the diff.** §5's
  extractor contract is explicit that the default `success` is right for T1/T2,
  "which need no review." A push to `main` deploys with no PR and no required
  review, so the commit diff was something a person *could* read afterward, not a
  checkpoint that stopped a bad number. Losing it loses a retrospective
  convenience, not a control.

The fabricated-placeholder incident this section invokes is a genuine scar, but
it was caught by *review of the extractor code*, not by reading a data diff — and
`validate_snapshots.py --strict` now rejects a sample or gap file outright, which
is the specific defense against a repeat.

So: build the diff report if it proves useful, as a convenience for spotting a
figure that moved unexpectedly. **Do not treat it as a blocker.** What actually
protects a publish is already in place — `source_runs` recording every run
server-side, `validate_snapshots.py --strict` gating the contract, and the T3
approval gate for anything a model extracted.

## 1.2 The container boundary is audience, not language

**Decided, 2026-08.** Each dashboard runs a public site container and the series
runs a pipeline container. That split predates any of these decisions — it fell
out of "Next.js builds with Node, extractors run in Python" — and the question
was raised fairly: now that the admin side is becoming a real application, does
the split still hold?

It holds. The axis is just misnamed. The durable boundary is not Node vs.
Python, it is **a public artifact and an internal application**, and their
requirements are opposite in every row:

| | Public dashboard | Admin / review queue |
|---|---|---|
| Readers | anonymous, mobile, crawlers, link-preview bots | one to three, authenticated |
| Must survive Postgres being down | **yes** | no — it is meaningless without it |
| Search and social preview | load-bearing | irrelevant |
| Writes | never | its entire purpose |
| Traffic shape | bursty, uncached-hostile | a handful of requests a day |

Two consequences follow, and both are decisions:

**The public site is a published document, not an application.** Whatever the
admin grows into, it does not pull the public pages with it. The direction of
travel is the opposite one: the public surface gets *more* static over time, not
less. A civic dashboard going dark because of a database problem is a real
regression — these sites are the public record for readers who have no other
copy.

**The review queue stays server-rendered inside the pipeline container.**
Rejected: a second Next.js application for `/admin`. The queue is a table of
pending extractions, each value beside its source quote, with approve and reject
buttons — server-rendered forms, a few hundred lines, in the container that
already holds the database credentials and already runs the extractors it is
reviewing. A React admin would add a second frontend toolchain, a second auth
surface, and a second deploy, and the shared component kit (§7) offers it
nothing: a review queue needs a table and two buttons, not `KpiCard` and
`TrendChart`. If it ever becomes something a person uses all day, moving it is a
contained rewrite of a small app — not a decision this one forecloses.

Also rejected, and worth naming because it is the conventional answer: merging
public and admin into one Next.js server with `/admin` as a route. That takes
the one surface that must never go down and couples it to the one that is
allowed to.

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
Shelby County — one pull yields all seven. Loaded as the `municipality` layer;
see §6.2 for the converter and verification.

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
justice-specific, so only the other six layers below load into `geo.boundaries`.

### 6.1 The loader: [`toolkit/boundaries.py`](../src/toolkit/boundaries.py)

901justice's files are already GeoJSON, not raw shapefiles, so the loader does
no shapefile parsing — that stays `toolkit.geo`'s job. `load_geojson()` takes a
FeatureCollection already on disk and upserts it into `geo.boundaries`, keyed on
`(layer, geo_key, vintage)` exactly like the table's `UNIQUE` constraint: a
rerun with the same vintage corrects that vintage's rows in place, and a new
vintage adds rows without touching the old ones. A bare `Polygon` feature (the
MPD layers, left unloaded here) is wrapped with `ST_Multi` rather than rejected
by the column's `MultiPolygon` type.

[`scripts/load_boundaries.py`](../scripts/load_boundaries.py) is the CLI over
it — dashboard-agnostic, since `geo.boundaries` is shared: it takes the
`properties` key names to read rather than assuming any one convention. The six
shareable layers all load with one invocation shape:

```
export DATABASE_URL=postgresql://geo_loader:<password>@<host>/civic
python3 scripts/load_boundaries.py \
    --file data/boundaries/cityCouncil.json \
    --layer city-council --geo-key-property id --name-property name \
    --vintage "Shelby County GIS 2023-08-21"
```

(`congressional`/`countyCommission`/`stateHouse`/`stateSenate` follow the same
`id`/`name` shape; `memphisZips.json` uses `--geo-key-property zip`.) This runs
from inside the Coolify network, authenticated as `geo_loader` — the role
`geo.boundaries` is owned by, not any dashboard's app role — because
`DATABASE_URL`'s host is internal-only (§1a).

Verified against a real Postgres 18 + PostGIS 3.6, including against
901justice's actual files, not synthetic fixtures: `city-council` (8 features)
and `zip` (31 features) both load; a rerun of `city-council` with the same
vintage stays at 8 rows rather than becoming 16; every loaded geometry reports
`ST_MultiPolygon`.

**Found in the process, not fixed here:** `ST_IsValid` flags 2 of the 31 zip
polygons (self-intersecting shells) — a data-quality issue in the source
shapefile conversion, not something the loader introduces or should silently
repair. Whoever runs the real load should expect `ST_IsValid` to flag these two
and decide whether to re-derive them from source before loading, not treat a
loader that reports success as proof the geometries are clean.

### 6.2 The `municipality` layer, from Census TIGER

§5 named the source (Census TIGER Places, one statewide pull) and the target
(all seven Shelby County municipalities). This fills in the pull itself:
[`scripts/fetch_municipalities.py`](../scripts/fetch_municipalities.py) converts
the statewide shapefile and [`toolkit.geo.filter_by_name`](../src/toolkit/geo.py)
narrows it to the seven, then the existing `load_boundaries.py` loads the
result unchanged — TIGER needed a new *converter*, not a new *loader*.

```
curl -O https://www2.census.gov/geo/tiger/TIGER2023/PLACE/tl_2023_47_place.zip
python3 scripts/fetch_municipalities.py \
    --zip tl_2023_47_place.zip --source-date 2023-11-09 \
    --out data/boundaries/municipalities.json

python3 scripts/load_boundaries.py \
    --file data/boundaries/municipalities.json \
    --layer municipality --geo-key-property GEOID --name-property NAME \
    --vintage "Census TIGER/Line 2023" \
    --source-url https://www2.census.gov/geo/tiger/TIGER2023/PLACE/tl_2023_47_place.zip
```

TIGER Places has no county-level cut — a place's polygon can straddle a county
line, so the source can't be asked for "just Shelby County." The converter
pulls the whole state (504 places for TN) and filters by name after
conversion; it refuses to write a partial result if any of the seven is
missing, rather than silently loading six.

Verified against the real 2023 file, not a fixture: all seven names resolve to
the exact GEOIDs §5 already recorded (Memphis is `4748000`); a rerun of
`load_boundaries.py` stays at 7 rows rather than 14; every loaded geometry
reports `ST_MultiPolygon`.

**Found in the process, not fixed here:** `ST_IsValid` flags Memphis and
Collierville — the two multi-part places (2 and 5 parts respectively, real
non-contiguous annexations) — as "nested shells," at simplification tolerance
0 as well as the loader's default, so this is a property of the TIGER source
geometry, not something this converter's simplification introduces. Same
posture as §6.1's zip-code finding: recorded here, not silently repaired.



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

## 7.2 Extraction happened; adoption did not — and that is where drift starts

**Measured 2026-08, on the working copies of all four repos.** §7 records the
extraction as done, and it is: `civic-dashboard-kit/ui/` ships a real npm
package — root `package.json`, `main: ui/index.ts`, peer deps, its own vitest
suite. What §7 does not say is that **no dashboard depends on it.** Not one of
the three `package.json` files names `civic-dashboard-kit`. All three still
import from their own `components/data-status/`.

So the copies are still copies:

| | `DataStatusPanel.tsx` | `SampleBadge.tsx` |
|---|---|---|
| civic-dashboard-kit `ui/` | 238 | 58 |
| 901justice | 241 | 57 |
| 901education | 242 | 58 |
| 901economy | 242 | 58 |
| 901economy `reference/901justice/` | 242 | 58 | 

§7 measured these as byte-identical apart from one import line, and called that
a cleaner case for extraction than drift would be. **That is no longer true.**
The kit's copy has moved: it imports `resolveStatus` from `./types`, where the
dashboards still inline a local `getStatus`, and each dashboard still declares
its own `DataStatus` union (901economy at `lib/types.ts:11`) alongside the one
`ui/types.ts` calls canonical. The extraction was supposed to end that. It ended
it in one repo out of four.

**This is the series' actual scaling problem, and it is worth saying plainly
next to the infrastructure decisions above.** The Python half of this package is
genuine reuse — clients, stores, boundaries, the snapshot contract, all imported
for real by consumers that break loudly when it changes. The TypeScript half is
aspirational. At three dashboards a fourth copy is an annoyance. At the number
of dashboards this series is aiming for, it is N places to fix a provenance bug
— in precisely the layer where a bug is an editorial failure rather than a
cosmetic one, because it is the layer that tells a reader whether a number is
real.

### Two frictions that explain the stall, both small

- **The package exports raw `.tsx`.** A consuming Next app needs
  `transpilePackages: ['civic-dashboard-kit']` in `next.config.js`. One line,
  undocumented until now.
- **The pinning rule makes adoption deliberate.** Dependencies pin to immutable
  commits, not `@main`, so adopting is a commit per dashboard rather than a
  drive-by — correctly, but it means nothing happens by default.

### Sequencing

**901economy adopts first, alone, and runs on it before anything is backported.**
It is the repo under active work, so a problem with the package surfaces where
someone is already looking. Backport to 901justice and 901education after it has
run through a real publish cycle.

**What comes along and what does not.** In scope: `DataStatusPanel`,
`SampleBadge`, and the `DataStatus`/`resolveStatus` pair, which is the §7 list
minus `SourceLine`. `SourceLine` is a *standardization* (§7.1) — adopting it
changes rendered attribution on every figure, which is an editorial change and
belongs in its own reviewed step, not bundled into a mechanical deduplication.
The chart and map primitives (`KpiCard`, `TrendChart`, `ChoroplethMap`,
`lib/choropleth.ts`) stay out until rule-of-three is met on them independently,
unchanged from §7's last paragraph — but they are the obvious next candidates,
and they are the ones where sharing pays most.

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
