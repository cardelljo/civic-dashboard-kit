"""
Integration tests for toolkit.boundaries against a real Postgres + PostGIS.

Same fixture pattern as test_postgres_store.py: skips entirely without
TOOLKIT_TEST_DATABASE_URL (see tests/test_ci_guards.py for the guard that
keeps an all-skipped run from reading as a pass). Needs PostGIS specifically
(ST_GeomFromGeoJSON, ST_Multi, the geometry column type), which
scripts/dev-postgres.sh provisions -- a plain Postgres without the extension
would fail schema setup here, not the tests themselves.
"""

from __future__ import annotations

import os

import psycopg2
import pytest

from toolkit.boundaries import load_geojson

DATABASE_URL = os.environ.get("TOOLKIT_TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(
    not DATABASE_URL, reason="TOOLKIT_TEST_DATABASE_URL not set -- no Postgres available"
)

# Mirrors db/bootstrap.sql's geo.boundaries DDL exactly -- this is the contract
# under test, not a simplification of it.
SCHEMA = """
CREATE EXTENSION IF NOT EXISTS postgis;
CREATE SCHEMA IF NOT EXISTS geo;
CREATE TABLE geo.boundaries (
    boundary_id   BIGSERIAL PRIMARY KEY,
    layer         TEXT NOT NULL,
    geo_key       TEXT NOT NULL,
    name          TEXT NOT NULL,
    geom          geometry(MultiPolygon, 4326) NOT NULL,
    vintage       TEXT NOT NULL,
    source_url    TEXT,
    retrieved_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (layer, geo_key, vintage)
);
"""


@pytest.fixture()
def conn():
    connection = psycopg2.connect(DATABASE_URL)
    with connection.cursor() as cur:
        cur.execute(SCHEMA)
    connection.commit()
    yield connection
    connection.rollback()  # in case a test left an aborted transaction
    with connection.cursor() as cur:
        cur.execute("DROP TABLE IF EXISTS geo.boundaries")
    connection.commit()
    connection.close()


# A real square, small enough to be an obviously-fake test fixture rather than
# anything that could be mistaken for actual Shelby County geography.
SQUARE_POLYGON = {
    "type": "Polygon",
    "coordinates": [[[-90.0, 35.0], [-90.0, 35.1], [-89.9, 35.1], [-89.9, 35.0], [-90.0, 35.0]]],
}
SQUARE_MULTIPOLYGON = {"type": "MultiPolygon", "coordinates": [SQUARE_POLYGON["coordinates"]]}


def _collection(*features):
    return {"type": "FeatureCollection", "features": list(features)}


def test_loads_one_row_per_feature(conn):
    collection = _collection(
        {"type": "Feature", "geometry": SQUARE_MULTIPOLYGON,
         "properties": {"id": "1", "name": "District 1"}},
        {"type": "Feature", "geometry": SQUARE_MULTIPOLYGON,
         "properties": {"id": "2", "name": "District 2"}},
    )
    n = load_geojson(
        conn, collection, layer="city-council", geo_key_property="id",
        name_property="name", vintage="test-vintage",
    )
    assert n == 2
    with conn.cursor() as cur:
        cur.execute("SELECT layer, geo_key, name FROM geo.boundaries ORDER BY geo_key")
        rows = cur.fetchall()
    assert rows == [
        ("city-council", "1", "District 1"),
        ("city-council", "2", "District 2"),
    ]


def test_wraps_a_bare_polygon_into_multipolygon(conn):
    """MPD-style layers hand back Polygon, not MultiPolygon; the column only
    accepts MultiPolygon, so a bare Polygon must be wrapped, not rejected."""
    collection = _collection(
        {"type": "Feature", "geometry": SQUARE_POLYGON,
         "properties": {"id": "1", "name": "Station 1"}},
    )
    load_geojson(
        conn, collection, layer="mpd-station-area", geo_key_property="id",
        name_property="name", vintage="test-vintage",
    )
    with conn.cursor() as cur:
        cur.execute("SELECT ST_AsText(geom) FROM geo.boundaries")
        (wkt,) = cur.fetchone()
    assert wkt.startswith("MULTIPOLYGON")


def test_rerunning_the_same_vintage_corrects_in_place(conn):
    """Idempotent means converges, not just doesn't error: a rerun with a
    fixed source file must update the row, not add a duplicate one."""
    collection = _collection(
        {"type": "Feature", "geometry": SQUARE_MULTIPOLYGON,
         "properties": {"id": "1", "name": "Wrong Name"}},
    )
    load_geojson(conn, collection, layer="zip", geo_key_property="id",
                 name_property="name", vintage="v1")

    fixed = _collection(
        {"type": "Feature", "geometry": SQUARE_MULTIPOLYGON,
         "properties": {"id": "1", "name": "Correct Name"}},
    )
    n = load_geojson(conn, fixed, layer="zip", geo_key_property="id",
                      name_property="name", vintage="v1")

    assert n == 1
    with conn.cursor() as cur:
        cur.execute("SELECT count(*), max(name) FROM geo.boundaries")
        count, name = cur.fetchone()
    assert count == 1
    assert name == "Correct Name"


def test_a_new_vintage_adds_a_row_and_keeps_the_old_one(conn):
    """A redistricting or annexation must not overwrite the boundary that was
    published under the old vintage -- that history has to stay queryable."""
    collection = _collection(
        {"type": "Feature", "geometry": SQUARE_MULTIPOLYGON,
         "properties": {"id": "9", "name": "District 9"}},
    )
    load_geojson(conn, collection, layer="congressional", geo_key_property="id",
                 name_property="name", vintage="2020-cycle")
    load_geojson(conn, collection, layer="congressional", geo_key_property="id",
                 name_property="name", vintage="2030-cycle")

    with conn.cursor() as cur:
        cur.execute(
            "SELECT vintage FROM geo.boundaries WHERE layer = 'congressional' "
            "AND geo_key = '9' ORDER BY vintage"
        )
        vintages = [row[0] for row in cur.fetchall()]
    assert vintages == ["2020-cycle", "2030-cycle"]


def test_a_feature_missing_the_geo_key_property_raises_instead_of_skipping(conn):
    collection = _collection(
        {"type": "Feature", "geometry": SQUARE_MULTIPOLYGON, "properties": {"name": "No ID"}},
    )
    with pytest.raises(KeyError):
        load_geojson(conn, collection, layer="zip", geo_key_property="zip",
                     name_property="name", vintage="test-vintage")

    conn.rollback()
    with conn.cursor() as cur:
        cur.execute("SELECT count(*) FROM geo.boundaries")
        assert cur.fetchone()[0] == 0
