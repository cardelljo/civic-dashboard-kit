#!/usr/bin/env python3
"""
Load one GeoJSON FeatureCollection into the shared `geo.boundaries` table.

Dashboard-agnostic on purpose: `geo.boundaries` is shared (docs/ARCHITECTURE.md
§4), so this script takes the property names to read rather than assuming any
one dashboard's convention. 901justice's six shareable layers (city council,
county commission, congressional, state house, state senate, Memphis zips --
the MPD ward/station layers are left justice-specific per §6) all load with
this one invocation shape:

    export DATABASE_URL=postgresql://geo_loader:<password>@<host>/civic
    python3 scripts/load_boundaries.py \\
        --file data/boundaries/cityCouncil.json \\
        --layer city-council --geo-key-property id --name-property name \\
        --vintage "Shelby County GIS 2023-08-21"

    python3 scripts/load_boundaries.py \\
        --file data/boundaries/congressional.json \\
        --layer congressional --geo-key-property id --name-property name \\
        --vintage "Shelby County GIS 2023-08-21"

    python3 scripts/load_boundaries.py \\
        --file data/boundaries/countyCommission.json \\
        --layer county-commission --geo-key-property id --name-property name \\
        --vintage "Shelby County GIS 2023-08-21"

    python3 scripts/load_boundaries.py \\
        --file data/boundaries/stateHouse.json \\
        --layer state-house --geo-key-property id --name-property name \\
        --vintage "Shelby County GIS 2023-08-21"

    python3 scripts/load_boundaries.py \\
        --file data/boundaries/stateSenate.json \\
        --layer state-senate --geo-key-property id --name-property name \\
        --vintage "Shelby County GIS 2023-08-21"

    python3 scripts/load_boundaries.py \\
        --file data/boundaries/memphisZips.json \\
        --layer zip --geo-key-property zip --name-property name \\
        --vintage "Memphis ZIP Codes shapefile 2023-03-11"

Run from inside the Coolify network (as the pipeline container does) --
DATABASE_URL's host is internal-only, per docs/ARCHITECTURE.md §1a. `geo_loader`
is the role that owns `geo.boundaries`; the three dashboard app roles have
read-only access to it, so this must authenticate as `geo_loader`, not as
`economy_app`/`education_app`/`justice_app`.
"""

from __future__ import annotations

import argparse
import json
import os
import sys

import psycopg2

from toolkit.boundaries import load_geojson


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--file", required=True, help="path to a GeoJSON FeatureCollection")
    parser.add_argument("--layer", required=True, help="e.g. city-council, zip, congressional")
    parser.add_argument("--geo-key-property", required=True,
                         help="GeoJSON properties key holding the natural key, e.g. id, zip")
    parser.add_argument("--name-property", required=True,
                         help="GeoJSON properties key holding the display name")
    parser.add_argument("--vintage", required=True,
                         help="e.g. 'Shelby County GIS 2023-08-21' -- part of the unique key")
    parser.add_argument("--source-url", default=None)
    args = parser.parse_args()

    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        print("error: DATABASE_URL is not set", file=sys.stderr)
        return 1

    with open(args.file) as f:
        collection = json.load(f)

    conn = psycopg2.connect(database_url)
    try:
        n = load_geojson(
            conn, collection,
            layer=args.layer,
            geo_key_property=args.geo_key_property,
            name_property=args.name_property,
            vintage=args.vintage,
            source_url=args.source_url,
        )
    finally:
        conn.close()

    print(f"{args.layer}: {n} features upserted from {args.file}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
