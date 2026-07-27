"""
U.S. Bureau of Economic Analysis (BEA) Regional API client.

Same shape as toolkit.census.AcsClient / toolkit.fred.FredClient: a thin,
free-key-based client for the Regional dataset's GDP-by-area tables
(CAGDP1 nominal GDP, CAGDP9 real/chained GDP, CAGDP2 GDP by industry) --
the tables 901economy's GRP section needs (PLAN.md's dual-mode rule: CAGDP1
for current-dollar levels, CAGDP9 for chained-dollar growth rates, never
mixed in one chart).

Requires a free API key (apps.bea.gov/api/signup/).

Usage:
    from toolkit.bea import BeaClient

    bea = BeaClient(api_key="...")
    rows = bea.regional_gdp(table_name="CAGDP1", geo_fips="28700", year="2023")
    # -> [{"geo_fips": "28700", "geo_name": "Memphis, TN-MS-AR (Metropolitan
    #      Statistical Area)", "period": "2023", "value": 102900.0, ...}]
"""

from __future__ import annotations

import requests

BEA_API_URL = "https://apps.bea.gov/api/data/"


class BeaClient:
    """BEA Regional dataset client (GetData method, Regional dataset)."""

    def __init__(self, api_key: str, timeout: int = 30):
        self.api_key = api_key
        self.timeout = timeout

    def regional_gdp(
        self,
        table_name: str,
        geo_fips: str,
        year: str = "LAST5",
        line_code: str = "1",
    ) -> list[dict]:
        """
        Pull a Regional GDP table for one geography.

        `table_name`: 'CAGDP1' (nominal GDP), 'CAGDP9' (real/chained GDP), or
        'CAGDP2' (GDP by industry -- pass the relevant `line_code` for the
        private-industry-share line).
        `geo_fips`: BEA's regional GeoFips code (MSAs use their CBSA code,
        e.g. '28700' for Memphis MSA; a two-letter state postal code pulls
        every county in that state).
        `year`: a single year, comma-separated years, or BEA's 'LASTn' /
        'ALL' shorthand.

        Returns one dict per (geography, period) row -- a table_name with
        multiple periods/geographies in one call returns one list entry per
        row, not aggregated.
        """
        params = {
            "UserID": self.api_key,
            "method": "GetData",
            "datasetname": "Regional",
            "TableName": table_name,
            "LineCode": line_code,
            "GeoFips": geo_fips,
            "Year": year,
            "ResultFormat": "JSON",
        }
        r = requests.get(BEA_API_URL, params=params, timeout=self.timeout)
        r.raise_for_status()
        body = r.json()

        results = body.get("BEAAPI", {}).get("Results", {})
        error = results.get("Error") if isinstance(results, dict) else None
        if error:
            raise RuntimeError(f"BEA request failed: {error}")

        rows = results.get("Data", []) if isinstance(results, dict) else []
        return [
            {
                "geo_fips": row["GeoFips"],
                "geo_name": row["GeoName"],
                "period": row["TimePeriod"],
                # BEA returns DataValue as a comma-grouped string ("102,900.0");
                # strip grouping commas before parsing.
                "value": float(row["DataValue"].replace(",", "")),
            }
            for row in rows
        ]
