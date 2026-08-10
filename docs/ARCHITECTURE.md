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

## 1. Choosing a store is per dashboard, and that is deliberate

901education writes a git-committed NDJSON ledger (`observations.py`);
901economy writes Postgres (`postgres_store.py`). That is **not** drift — the
two share one append-only design, and the README's
[Choosing a store](../README.md#choosing-a-store-observationspy-vs-postgres_storepy)
section is the decision record. A single-district annual dashboard and a
~30-source multi-cadence one legitimately want different stores.

What follows applies to whichever dashboards land on Postgres.

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
the image under a running database later is not. Use `postgis/postgis:16-*`
rather than plain `postgres:16` — same Postgres 16 this package's
`postgres_store` was tested against.

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
a live site with a daily cron, no test suite, and type checks disabled. Its
existing duplicate components keep working indefinitely. Nothing here obliges any
dashboard to migrate on someone else's timeline.

### What does not go in this repo

**The admin application is a separate repo.** It is an application, not a
library: no dashboard installs it, and bundling it would drag its dependency tree
into every git clone. That is the reason — not secrecy. Its configuration belongs
in environment variables regardless of where the source lives.
