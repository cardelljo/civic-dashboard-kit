"""
Loader for the shared `geo.boundaries` table (docs/ARCHITECTURE.md §4).

901justice's `data/boundaries/*.json` files are already GeoJSON -- converted
from shapefiles by `toolkit.geo` -- so this module does no shapefile parsing.
Its only job is the second half of that pipeline: taking a FeatureCollection
already on disk and upserting it into Postgres.

`geo.boundaries` is shared across dashboards and owned by `geo_loader`
(db/bootstrap.sql), not by any one dashboard's app role, so this module lives
in the toolkit rather than in 901justice even though justice holds the only
real data today.

Requires psycopg2 (the `postgres` extra) -- same as toolkit.postgres_store.

Usage (typically from scripts/load_boundaries.py):

    from toolkit.boundaries import load_geojson

    with open("data/boundaries/cityCouncil.json") as f:
        collection = json.load(f)
    n = load_geojson(
        conn, collection,
        layer="city-council", geo_key_property="id", name_property="name",
        vintage="Shelby County GIS 2023-08-21",
    )
"""

from __future__ import annotations

import json

try:
    import psycopg2
except ImportError as exc:  # pragma: no cover - exercised only when the extra is missing
    raise ImportError(
        "toolkit.boundaries requires the 'postgres' extra: "
        'pip install "civic-dashboard-kit[postgres] @ '
        'git+https://github.com/cardelljo/civic-dashboard-kit.git@main"'
    ) from exc


def load_geojson(
    conn,
    feature_collection: dict,
    *,
    layer: str,
    geo_key_property: str,
    name_property: str,
    vintage: str,
    source_url: str | None = None,
) -> int:
    """Upsert every feature in a GeoJSON FeatureCollection into `geo.boundaries`.

    One row per feature, keyed on `(layer, geo_key, vintage)` -- the same
    tuple db/bootstrap.sql's UNIQUE constraint enforces. Re-running with the
    same `vintage` corrects that vintage's rows in place (a fixed source file,
    a rerun after a bug fix); a new `vintage` -- a redistricting, an
    annexation -- adds new rows and leaves the old ones exactly as published,
    per the append-only discipline the indicator stores also use.

    The column is `geometry(MultiPolygon, 4326)`. A source that hands back a
    bare Polygon (901justice's MPD layers do; the district/zip layers don't)
    is wrapped with `ST_Multi` rather than rejected at the constraint.

    `geo_key_property` and `name_property` name the GeoJSON `properties` keys
    to read per feature -- not hardcoded, because the six layers this loads
    today don't agree on one: district layers use `id`/`name`,
    `memphisZips.json` uses `zip`/`name`. A feature missing either property
    raises `KeyError` rather than silently skipping a boundary.

    Returns the number of features upserted.
    """
    n = 0
    with conn.cursor() as cur:
        for feature in feature_collection["features"]:
            props = feature["properties"]
            cur.execute(
                """
                INSERT INTO geo.boundaries (layer, geo_key, name, geom, vintage, source_url)
                VALUES (
                    %(layer)s, %(geo_key)s, %(name)s,
                    ST_SetSRID(ST_Multi(ST_GeomFromGeoJSON(%(geometry)s)), 4326),
                    %(vintage)s, %(source_url)s
                )
                ON CONFLICT (layer, geo_key, vintage) DO UPDATE SET
                    name = EXCLUDED.name,
                    geom = EXCLUDED.geom,
                    source_url = EXCLUDED.source_url,
                    retrieved_at = now()
                """,
                {
                    "layer": layer,
                    "geo_key": str(props[geo_key_property]),
                    "name": str(props[name_property]),
                    "geometry": json.dumps(feature["geometry"]),
                    "vintage": vintage,
                    "source_url": source_url,
                },
            )
            n += 1
    conn.commit()
    return n
