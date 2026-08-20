"""Unit tests for toolkit.geo's dashboard-agnostic helpers."""

from __future__ import annotations

from toolkit.geo import filter_by_name


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
