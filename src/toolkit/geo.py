"""
Dependency-free shapefile -> GeoJSON conversion.

Extracted from 901justice's convert_boundary_shapefiles.py. Parses .shp/.dbf
pairs from a zip archive with the standard library only (no GDAL/geopandas),
simplifies rings with Douglas-Peucker, and emits GeoJSON-shaped dicts that
Next.js can import directly.

Supports the two projections local sources publish in:
  - EPSG:2274 / NAD83 Tennessee StatePlane feet (use stateplane_tn_to_wgs84)
  - EPSG:4326 / WGS84 (use identity)

Usage (e.g. school attendance boundaries):
    from toolkit.geo import convert_layer, feature_collection, stateplane_tn_to_wgs84

    features = convert_layer(
        zip_path=Path("raw/attendance_boundaries.zip"),
        prefix="MSCS_Elementary_Boundaries",
        transform=stateplane_tn_to_wgs84,
        tolerance=350.0,   # simplification tolerance in source units
        make_properties=lambda row: {"school": row.get("SCH_NAME", "").strip()},
    )
    geojson = feature_collection(features, "MSCS attendance boundaries", "2026-01-15")
"""

from __future__ import annotations

import math
import struct
import zipfile
from pathlib import Path
from typing import Callable


def read_zip_member(zip_path: Path, name: str) -> bytes:
    with zipfile.ZipFile(zip_path) as zf:
        return zf.read(name)


def parse_dbf(data: bytes) -> list[dict]:
    record_count = struct.unpack("<I", data[4:8])[0]
    header_len = struct.unpack("<H", data[8:10])[0]
    record_len = struct.unpack("<H", data[10:12])[0]
    fields = []
    pos = 32
    while data[pos] != 0x0D:
        raw = data[pos:pos + 32]
        name = raw[:11].split(b"\0", 1)[0].decode("ascii", "ignore")
        field_type = chr(raw[11])
        length = raw[16]
        decimals = raw[17]
        fields.append((name, field_type, length, decimals))
        pos += 32

    rows = []
    for idx in range(record_count):
        start = header_len + idx * record_len
        record = data[start:start + record_len]
        if not record or record[0:1] == b"*":
            rows.append({})
            continue
        cursor = 1
        row = {}
        for name, field_type, length, _decimals in fields:
            raw_value = record[cursor:cursor + length].decode("latin1", "ignore").strip()
            cursor += length
            if field_type in {"N", "F"} and raw_value:
                try:
                    row[name] = float(raw_value) if any(c in raw_value.lower() for c in [".", "e"]) else int(raw_value)
                except ValueError:
                    row[name] = raw_value
            else:
                row[name] = raw_value
        rows.append(row)
    return rows


def perpendicular_distance(point: tuple[float, float], start: tuple[float, float], end: tuple[float, float]) -> float:
    if start == end:
        return math.hypot(point[0] - start[0], point[1] - start[1])
    numerator = abs(
        (end[0] - start[0]) * (start[1] - point[1])
        - (start[0] - point[0]) * (end[1] - start[1])
    )
    denominator = math.hypot(end[0] - start[0], end[1] - start[1])
    return numerator / denominator


def simplify_line(points: list[tuple[float, float]], tolerance: float) -> list[tuple[float, float]]:
    if len(points) <= 3 or tolerance <= 0:
        return points
    closed = points[0] == points[-1]
    work = points[:-1] if closed else points
    if len(work) <= 3:
        return points

    def simplify_segment(segment: list[tuple[float, float]]) -> list[tuple[float, float]]:
        if len(segment) <= 2:
            return segment
        start, end = segment[0], segment[-1]
        max_dist = -1.0
        index = 0
        for i in range(1, len(segment) - 1):
            dist = perpendicular_distance(segment[i], start, end)
            if dist > max_dist:
                max_dist = dist
                index = i
        if max_dist > tolerance:
            left = simplify_segment(segment[:index + 1])
            right = simplify_segment(segment[index:])
            return left[:-1] + right
        return [start, end]

    simplified = simplify_segment(work)
    if closed:
        simplified.append(simplified[0])
    return simplified if len(simplified) >= 4 else points


def parse_shp(data: bytes, transform: Callable[[float, float], tuple[float, float]], tolerance: float) -> list[list[list[list[float]]]]:
    shapes = []
    pos = 100
    while pos < len(data):
        if pos + 8 > len(data):
            break
        _record_number, content_len_words = struct.unpack(">2i", data[pos:pos + 8])
        pos += 8
        content_len = content_len_words * 2
        content = data[pos:pos + content_len]
        pos += content_len
        if len(content) < 44:
            continue
        shape_type = struct.unpack("<i", content[:4])[0]
        if shape_type == 0:
            shapes.append([])
            continue
        if shape_type not in {5, 15, 25}:
            raise ValueError(f"Unsupported shape type {shape_type}")
        num_parts, num_points = struct.unpack("<2i", content[36:44])
        parts_start = 44
        points_start = parts_start + num_parts * 4
        parts = list(struct.unpack(f"<{num_parts}i", content[parts_start:points_start]))
        parts.append(num_points)
        points = [
            struct.unpack("<2d", content[points_start + i * 16:points_start + (i + 1) * 16])
            for i in range(num_points)
        ]
        polygons = []
        for idx in range(num_parts):
            raw_ring = points[parts[idx]:parts[idx + 1]]
            raw_ring = simplify_line(raw_ring, tolerance)
            ring = []
            for x, y in raw_ring:
                lon, lat = transform(x, y)
                ring.append([round(lon, 6), round(lat, 6)])
            if ring and ring[0] != ring[-1]:
                ring.append(ring[0])
            if len(ring) >= 4:
                polygons.append([ring])
        shapes.append(polygons)
    return shapes


def stateplane_tn_to_wgs84(x_ft: float, y_ft: float) -> tuple[float, float]:
    # Inverse Lambert Conformal Conic for NAD83 / Tennessee StatePlane feet.
    foot = 0.3048006096012192
    a = 6378137.0
    inv_f = 298.257222101
    e = math.sqrt(2 / inv_f - 1 / (inv_f * inv_f))
    false_easting = 1968500.0 * foot
    false_northing = 0.0
    lon0 = math.radians(-86.0)
    lat0 = math.radians(34.33333333333334)
    lat1 = math.radians(35.25)
    lat2 = math.radians(36.41666666666666)
    x = x_ft * foot - false_easting
    y = y_ft * foot - false_northing

    def m(phi: float) -> float:
        return math.cos(phi) / math.sqrt(1 - e * e * math.sin(phi) ** 2)

    def t(phi: float) -> float:
        sin_phi = math.sin(phi)
        return math.tan(math.pi / 4 - phi / 2) / ((1 - e * sin_phi) / (1 + e * sin_phi)) ** (e / 2)

    n = (math.log(m(lat1)) - math.log(m(lat2))) / (math.log(t(lat1)) - math.log(t(lat2)))
    f = m(lat1) / (n * (t(lat1) ** n))
    rho0 = a * f * (t(lat0) ** n)
    rho = math.copysign(math.hypot(x, rho0 - y), n)
    theta = math.atan2(x, rho0 - y)
    t_value = (rho / (a * f)) ** (1 / n)
    phi = math.pi / 2 - 2 * math.atan(t_value)
    for _ in range(8):
        sin_phi = math.sin(phi)
        phi = math.pi / 2 - 2 * math.atan(
            t_value * ((1 - e * sin_phi) / (1 + e * sin_phi)) ** (e / 2)
        )
    lon = lon0 + theta / n
    return math.degrees(lon), math.degrees(phi)


def identity(x: float, y: float) -> tuple[float, float]:
    return x, y


def feature_collection(features: list[dict], source: str, source_date: str,
                       generated_by: str = "toolkit/geo.py") -> dict:
    return {
        "type": "FeatureCollection",
        "_meta": {
            "source": source,
            "sourceDate": source_date,
            "generatedBy": generated_by,
            "coordinateSystem": "EPSG:4326",
            "publicGrain": "Boundary polygons only",
        },
        "features": features,
    }


def filter_by_name(features: list[dict], names: set[str], name_property: str = "NAME") -> list[dict]:
    """Keep only the features whose `name_property` is in `names`.

    For a source with no finer-grained cut than "the whole state" -- Census
    TIGER Places has no county-level filter, since a place can straddle a
    county line -- this is the only way to narrow a statewide pull down to
    the handful of features a dashboard actually wants.
    """
    return [f for f in features if f["properties"].get(name_property) in names]


def convert_layer(zip_path: Path, prefix: str, transform, tolerance: float, make_properties) -> list[dict]:
    shapes = parse_shp(read_zip_member(zip_path, f"{prefix}.shp"), transform, tolerance)
    rows = parse_dbf(read_zip_member(zip_path, f"{prefix}.dbf"))
    features = []
    for shape, row in zip(shapes, rows):
        if not shape:
            continue
        features.append({
            "type": "Feature",
            "geometry": {
                "type": "MultiPolygon",
                "coordinates": shape,
            },
            "properties": make_properties(row),
        })
    return features
