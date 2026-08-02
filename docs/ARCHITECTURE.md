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
