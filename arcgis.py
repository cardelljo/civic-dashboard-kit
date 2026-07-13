"""
Generic ArcGIS Feature Service client.

Consolidates the per-script `arcgis_query()` helpers that 901justice duplicated
across fetch_crime_data.py, fetch_traffic_stops.py, and fetch_traffic_citations.py.

Prefers server-side aggregation (outStatistics + groupByFieldsForStatistics) so
callers never download full record-level datasets — both a bandwidth and a
privacy measure: aggregate queries keep person/event-level rows off our disks.

Usage:
    from toolkit.arcgis import FeatureService

    svc = FeatureService(
        "https://services2.arcgis.com/.../FeatureServer/0"
    )
    result = svc.count_by(
        group_field="UCR_Category",
        where="Offense_Datetime >= date '2026-01-01'",
    )
    # -> {"ASSAULT": 1234, "ROBBERY": 210, ...}
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any
from urllib.parse import urlencode

import requests


class ArcGISError(RuntimeError):
    pass


class FeatureService:
    def __init__(self, layer_url: str, timeout: int = 60):
        self.layer_url = layer_url.rstrip("/")
        self.query_url = f"{self.layer_url}/query"
        self.timeout = timeout

    def query(self, params: dict[str, Any]) -> dict:
        """Run a raw query against the layer and return parsed JSON."""
        defaults = {"f": "json", "returnGeometry": "false"}
        url = self.query_url + "?" + urlencode({**defaults, **params})
        r = requests.get(url, timeout=self.timeout)
        r.raise_for_status()
        data = r.json()
        if "error" in data:
            raise ArcGISError(f"ArcGIS error: {data['error']}")
        return data

    def count_by(self, group_field: str, where: str = "1=1",
                 count_field: str = "OBJECTID") -> dict[str, int]:
        """Server-side grouped count. Returns {group_value: count}."""
        resp = self.query({
            "where": where,
            "outStatistics": json.dumps([{
                "statisticType": "count",
                "onStatisticField": count_field,
                "outStatisticFieldName": "total",
            }]),
            "groupByFieldsForStatistics": group_field,
        })
        counts: dict[str, int] = {}
        for feat in resp.get("features", []):
            attrs = feat["attributes"]
            counts[str(attrs.get(group_field))] = int(attrs.get("total") or 0)
        return counts

    def total_count(self, where: str = "1=1") -> int:
        """Server-side record count for a filter."""
        resp = self.query({"where": where, "returnCountOnly": "true"})
        return int(resp.get("count", 0))

    def statistics(self, out_statistics: list[dict], where: str = "1=1",
                   group_by: str | None = None) -> list[dict]:
        """Arbitrary outStatistics query; returns the attribute dicts."""
        params: dict[str, Any] = {
            "where": where,
            "outStatistics": json.dumps(out_statistics),
        }
        if group_by:
            params["groupByFieldsForStatistics"] = group_by
        resp = self.query(params)
        return [feat["attributes"] for feat in resp.get("features", [])]


def date_where(field: str, start: datetime, end: datetime) -> str:
    """Build an ArcGIS date-range WHERE clause for a datetime field."""
    return (
        f"{field} >= date '{start.strftime('%Y-%m-%d')}' "
        f"AND {field} <= date '{end.strftime('%Y-%m-%d')}'"
    )
