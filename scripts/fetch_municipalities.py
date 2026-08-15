#!/usr/bin/env python3
"""
Convert Census TIGER/Line Places into the GeoJSON `geo.boundaries` loads from.

ARCHITECTURE §5: all seven Shelby County municipalities -- Memphis, Bartlett,
Collierville, Germantown, Lakeland, Millington, Arlington -- belong in
`geo.boundaries`, not Memphis alone, because the six suburbs' 2014 municipal
school districts share the same polygon as the municipal boundary. TIGER
Places for TN is one statewide shapefile with no county-level cut (a place
can straddle a county line), so this converts the whole file and then filters
by name to just those seven, verified against the real 2023 file to be exact
matches for the GEOIDs §5 already records (Memphis is 4748000).

Usage:
    curl -O https://www2.census.gov/geo/tiger/TIGER2023/PLACE/tl_2023_47_place.zip
    python3 scripts/fetch_municipalities.py \\
        --zip tl_2023_47_place.zip \\
        --source-date 2023-11-09 \\
        --out data/boundaries/municipalities.json

Then load into geo.boundaries with the existing generic loader (unchanged --
this script only produces the FeatureCollection it expects):
    python3 scripts/load_boundaries.py \\
        --file data/boundaries/municipalities.json \\
        --layer municipality --geo-key-property GEOID --name-property NAME \\
        --vintage "Census TIGER/Line 2023" \\
        --source-url https://www2.census.gov/geo/tiger/TIGER2023/PLACE/tl_2023_47_place.zip
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from toolkit.geo import convert_layer, feature_collection, filter_by_name, identity

# The seven incorporated municipalities in Shelby County, TN (ARCHITECTURE §5).
SHELBY_COUNTY_MUNICIPALITIES = {
    "Memphis", "Bartlett", "Collierville", "Germantown",
    "Lakeland", "Millington", "Arlington",
}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--zip", required=True, type=Path,
                         help="tl_YYYY_47_place.zip, downloaded from Census TIGER")
    parser.add_argument("--prefix", default=None,
                         help="shapefile member prefix inside the zip; defaults to the zip's stem")
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--tolerance", type=float, default=0.0001,
                         help="Douglas-Peucker tolerance in degrees (default ~11m; "
                              "cuts these seven shapes from ~11,900 points to ~1,700)")
    parser.add_argument("--source-date", required=True,
                         help="TIGER vintage, e.g. 2023-11-09 -- the .dbf's file date in the zip")
    args = parser.parse_args()

    prefix = args.prefix or args.zip.stem

    features = convert_layer(
        zip_path=args.zip, prefix=prefix, transform=identity, tolerance=args.tolerance,
        make_properties=lambda row: {"GEOID": row["GEOID"], "NAME": row["NAME"]},
    )
    features = filter_by_name(features, SHELBY_COUNTY_MUNICIPALITIES)

    found = {f["properties"]["NAME"] for f in features}
    missing = SHELBY_COUNTY_MUNICIPALITIES - found
    if missing:
        raise SystemExit(
            f"error: {args.zip} is missing expected municipalities: {sorted(missing)} -- "
            "wrong file, wrong year, or a name changed. Not writing a partial result."
        )

    collection = feature_collection(
        features,
        source="Census TIGER/Line Places (TN)",
        source_date=args.source_date,
        generated_by="scripts/fetch_municipalities.py",
    )
    args.out.write_text(json.dumps(collection, indent=2) + "\n")
    print(f"wrote {len(features)} municipalities to {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
