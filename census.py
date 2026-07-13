"""
U.S. Census Bureau ACS and BLS API clients.

Generalized from 901justice's fetch_community_data.py: the Shelby County
constants become parameters so any dashboard (education, economic development)
can pull ACS variables for any geography without re-learning the API quirks —
detail vs. subject-table endpoints, header-row response format, and the BLS
monthly-period filtering.

No API keys required for either service at moderate volumes.

Usage:
    from toolkit.census import AcsClient, bls_monthly_series

    acs = AcsClient(year=2022)
    values = acs.county("B17001_002E,B17001_001E", state="47", county="157")
    # -> {"NAME": "Shelby County, Tennessee", "B17001_002E": "...", ...}

    trend = bls_monthly_series("LAUCN470570000000003", months=24)
    # -> [{"month": "Jan 2024", "value": 4.2}, ...] oldest -> newest
"""

from __future__ import annotations

import requests

SHELBY_STATE = "47"
SHELBY_COUNTY = "157"

BLS_API_URL = "https://api.bls.gov/publicAPI/v2/timeseries/data/"

_MONTH_NAMES = {
    "M01": "Jan", "M02": "Feb", "M03": "Mar", "M04": "Apr",
    "M05": "May", "M06": "Jun", "M07": "Jul", "M08": "Aug",
    "M09": "Sep", "M10": "Oct", "M11": "Nov", "M12": "Dec",
}


class AcsClient:
    """ACS 5-year estimates client covering detail (B-) and subject (S-) tables."""

    def __init__(self, year: int, dataset: str = "acs/acs5", timeout: int = 30):
        self.year = year
        self.dataset = dataset
        self.timeout = timeout

    def _base(self, variables: str) -> str:
        # Subject tables (S-prefixed variables) live under a different path
        # than detail tables; route automatically.
        path = self.dataset
        if variables.lstrip().upper().startswith("S"):
            path = f"{self.dataset}/subject"
        return f"https://api.census.gov/data/{self.year}/{path}"

    def _get(self, variables: str, geo_clause: str) -> dict[str, str]:
        url = f"{self._base(variables)}?get=NAME,{variables}&{geo_clause}"
        r = requests.get(url, timeout=self.timeout)
        r.raise_for_status()
        rows = r.json()
        # rows[0] = headers, rows[1] = data
        if len(rows) < 2:
            raise ValueError(f"Unexpected Census response: {rows}")
        return dict(zip(rows[0], rows[1]))

    def county(self, variables: str, state: str = SHELBY_STATE,
               county: str = SHELBY_COUNTY) -> dict[str, str]:
        return self._get(variables, f"for=county:{county}&in=state:{state}")

    def county_tracts(self, variables: str, state: str = SHELBY_STATE,
                      county: str = SHELBY_COUNTY) -> list[dict[str, str]]:
        """One dict per census tract in the county."""
        url = (
            f"{self._base(variables)}?get=NAME,{variables}"
            f"&for=tract:*&in=state:{state}%20county:{county}"
        )
        r = requests.get(url, timeout=self.timeout)
        r.raise_for_status()
        rows = r.json()
        headers = rows[0]
        return [dict(zip(headers, row)) for row in rows[1:]]

    def pct(self, numerator_var: str, denominator_var: str,
            state: str = SHELBY_STATE, county: str = SHELBY_COUNTY) -> float | None:
        """Convenience: fetch two detail variables and return num/den * 100."""
        d = self.county(f"{numerator_var},{denominator_var}", state, county)
        num = float(d[numerator_var])
        den = float(d[denominator_var])
        return round(num / den * 100, 1) if den else None


def bls_monthly_series(series_id: str, months: int = 24,
                       timeout: int = 30) -> list[dict]:
    """
    Pull the last `months` months of a BLS time series.
    Returns [{"month": "Jan 2024", "value": 4.2}, ...] oldest -> newest.
    """
    from datetime import date

    today = date.today()
    payload = {
        "seriesid": [series_id],
        "startyear": str(today.year - max(2, months // 12)),
        "endyear": str(today.year),
    }
    r = requests.post(BLS_API_URL, json=payload, timeout=timeout)
    r.raise_for_status()
    body = r.json()
    if body.get("status") != "REQUEST_SUCCEEDED":
        raise RuntimeError(f"BLS request failed: {body.get('message', body)}")

    series_list = body.get("Results", {}).get("series", [])
    if not series_list:
        raise ValueError("BLS returned no series data")

    monthly = [
        item for item in series_list[0].get("data", [])
        if item.get("period", "").startswith("M") and item["period"] != "M13"
    ]
    monthly.sort(key=lambda x: (x["year"], x["period"]))
    monthly = monthly[-months:]

    return [
        {
            "month": f"{_MONTH_NAMES[item['period']]} {item['year']}",
            "value": float(item["value"]),
        }
        for item in monthly
    ]
