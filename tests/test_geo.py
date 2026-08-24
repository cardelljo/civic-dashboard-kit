"""Unit tests for toolkit.geo's dashboard-agnostic helpers."""

from __future__ import annotations

from toolkit.geo import filter_by_name, nest_rings, point_in_ring, signed_area


def _feature(name: str) -> dict:
    return {"type": "Feature", "geometry": None, "properties": {"NAME": name}}


def test_filter_by_name_keeps_only_the_named_features():
    features = [_feature("Memphis"), _feature("Nashville"), _feature("Bartlett")]
    kept = filter_by_name(features, {"Memphis", "Bartlett"})
    assert [f["properties"]["NAME"] for f in kept] == ["Memphis", "Bartlett"]


def test_filter_by_name_respects_a_different_property_key():
    features = [{"type": "Feature", "geometry": None, "properties": {"id": "1"}}]
    assert filter_by_name(features, {"1"}, name_property="id") == features
    assert filter_by_name(features, {"2"}, name_property="id") == []


# A shapefile-convention outer ring (clockwise) with a shapefile-convention
# hole (counter-clockwise) fully inside it -- an enclave, like an
# unincorporated pocket surrounded by a city.
OUTER = [[0.0, 0.0], [0.0, 10.0], [10.0, 10.0], [10.0, 0.0], [0.0, 0.0]]
HOLE = [[4.0, 4.0], [6.0, 4.0], [6.0, 6.0], [4.0, 6.0], [4.0, 4.0]]
DISJOINT = [[20.0, 20.0], [20.0, 22.0], [22.0, 22.0], [22.0, 20.0], [20.0, 20.0]]


def test_signed_area_sign_distinguishes_winding():
    assert signed_area(OUTER) < 0  # shapefile outer: clockwise
    assert signed_area(HOLE) > 0   # shapefile hole: counter-clockwise


def test_point_in_ring():
    assert point_in_ring([5.0, 5.0], OUTER) is True
    assert point_in_ring([15.0, 15.0], OUTER) is False


def test_nest_rings_attaches_an_enclave_as_a_hole_of_its_parent():
    """The bug this guards against: a naive one-ring-per-polygon reading
    renders an enclave as its own solid polygon rather than a hole, so a
    real place like Memphis (TIGER Places, one enclave) or Collierville
    (four) silently loses its holes -- and PostGIS reports the result as
    "nested shells" rather than a clean multi-polygon with holes."""
    polygons = nest_rings([OUTER, HOLE])
    assert len(polygons) == 1
    outer, *holes = polygons[0]
    assert len(holes) == 1
    # RFC 7946: exterior counter-clockwise, interior clockwise -- the
    # reverse of the shapefile convention each input ring was given in.
    assert signed_area(outer) > 0
    assert signed_area(holes[0]) < 0


def test_nest_rings_keeps_a_ring_with_no_parent_as_its_own_polygon():
    """A hole-wound ring that contains no matching outer -- shouldn't happen
    in real data, but preserves the area rather than silently dropping it."""
    polygons = nest_rings([HOLE])
    assert len(polygons) == 1
    assert len(polygons[0]) == 1


def test_nest_rings_does_not_merge_disjoint_places():
    """Two unrelated outer rings -- e.g. Memphis and Collierville in one
    statewide pull -- must stay two separate polygons, not one with a
    spurious hole."""
    polygons = nest_rings([OUTER, DISJOINT])
    assert len(polygons) == 2
    assert all(len(p) == 1 for p in polygons)
