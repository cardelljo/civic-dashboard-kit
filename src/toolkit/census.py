"""
U.S. Census Bureau ACS and BLS API clients.

Generalized from 901justice's fetch_community_data.py: the Shelby County
constants become parameters so any dashboard (education, economic development)
can pull ACS variables for any geography without re-learning the API quirks —
detail vs. subject-table endpoints, header-row response format, and the BLS
monthly-period filtering.

**The Census data API now requires a free API key** -- requests without one are
redirected to https://api.census.gov/data/missing_key.html instead of returning
data, so `AcsClient` accepts an optional `api_key`
(https://api.census.gov/data/key_signup.html).

That redirect lands on an HTML page served with **HTTP 200**, so
`raise_for_status()` does not catch it and the failure surfaces as an opaque
JSON decode error several frames from the cause. `_rows` converts it into a
message that names the actual problem.

The key stays optional rather than required for two reasons: the variable
*catalog* endpoints (`.../variables.json`) still need no key, and that is
exactly how a caller verifies a variable ID before using it; and making it
required would break existing callers that construct `AcsClient(year)` today.

BLS's public v2 timeseries endpoint still needs no key at moderate volumes,
though one raises the rate limit.

Usage:
    from toolkit.census import AcsClient, bls_monthly_series

    acs = AcsClient(year=2022, api_key=os.environ["CENSUS_API_KEY"])
    values = acs.county("B17001_002E,B17001_001E", state="47", county="157")
    # -> {"NAME": "Shelby County, Tennessee", "B17001_002E": "...", ...}

    trend = bls_monthly_series("LAUCN470570000000003", months=24)
    # -> [{"month": "Jan 2024", "value": 4.2}, ...] oldest -> newest
"""

from __future__ import annotations

from urllib.parse import quote, urlencode

import requests

SHELBY_STATE = "47"
SHELBY_COUNTY = "157"

BLS_API_URL = "https://api.bls.gov/publicAPI/v2/timeseries/data/"

# A query-parameter value. A list means the parameter repeats, which is how the
# multi-level `in=state:47&in=county:157` geography clause is expressed.
# (PEP 604 union, evaluated at import -- fine on the declared floor of 3.10.)
_GeoValue = str | list[str]

_MONTH_NAMES = {
    "M01": "Jan", "M02": "Feb", "M03": "Mar", "M04": "Apr",
    "M05": "May", "M06": "Jun", "M07": "Jul", "M08": "Aug",
    "M09": "Sep", "M10": "Oct", "M11": "Nov", "M12": "Dec",
}


class AcsClient:
    """ACS 5-year estimates client covering detail (B-) and subject (S-) tables."""

    def __init__(self, year: int, dataset: str = "acs/acs5", timeout: int = 30,
                 api_key: str | None = None):
        self.year = year
        self.dataset = dataset
        self.timeout = timeout
        self.api_key = api_key

    def _base(self, variables: str) -> str:
        # Subject tables (S-prefixed variables) live under a different path
        # than detail tables; route automatically.
        path = self.dataset
        if variables.lstrip().upper().startswith("S"):
            path = f"{self.dataset}/subject"
        return f"https://api.census.gov/data/{self.year}/{path}"

    def _rows(self, variables: str, geo: dict[str, _GeoValue]) -> list[list[str]]:
        """Issue one ACS query and return its raw header+data rows.

        Callers pass geography as a dict, so nothing hand-builds a query string:
        the key becomes a parameter like any other (no `?`-vs-`&` to get wrong,
        no second code path that can forget it) and values that need escaping --
        `metropolitan statistical area/micropolitan statistical area:32820` is a
        real `for=` value -- are escaped for us.

        The dict is encoded here rather than handed to requests' `params=`
        because requests encodes via `quote_plus`, which renders a space as `+`.
        Census's published examples use `%20` (`in=state:06%20county:073`), and
        whether its parser also accepts `+` is not something we can confirm
        without spending a live request to find out. `quote_via=quote` emits
        `%20` and leaves `/` and `:` literal, matching those examples in the
        places where it matters.
        """
        params: dict[str, _GeoValue] = {"get": f"NAME,{variables}", **geo}
        if self.api_key:
            params["key"] = self.api_key
        query = urlencode(params, doseq=True, quote_via=quote, safe="/:*,")

        r = requests.get(self._base(variables), params=query, timeout=self.timeout)
        r.raise_for_status()
        try:
            return r.json()
        except ValueError as exc:
            # A missing or invalid key does not 4xx: Census redirects to an HTML
            # page served with HTTP 200, so raise_for_status() passes and the
            # only symptom is JSON that will not parse. Say what went wrong here
            # rather than letting a decode error stand in for it.
            raise RuntimeError(
                "Census returned a non-JSON body. The usual cause is a missing or "
                "invalid API key -- the data endpoints now require one, and reject "
                "requests with an HTML page rather than an error status. "
                "Pass AcsClient(..., api_key=...); get a free key at "
                "https://api.census.gov/data/key_signup.html"
            ) from exc

    def _get(self, variables: str, geo: dict[str, _GeoValue]) -> dict[str, str]:
        rows = self._rows(variables, geo)
        # rows[0] = headers, rows[1] = data
        if len(rows) < 2:
            raise ValueError(f"Unexpected Census response: {rows}")
        return dict(zip(rows[0], rows[1]))

    def county(self, variables: str, state: str = SHELBY_STATE,
               county: str = SHELBY_COUNTY) -> dict[str, str]:
        return self._get(variables, {"for": f"county:{county}", "in": f"state:{state}"})

    def msa(self, variables: str, cbsa: str) -> dict[str, str]:
        """Metro/micro statistical area cut, e.g. cbsa='32820' for Memphis MSA."""
        return self._get(
            variables,
            {"for": f"metropolitan statistical area/micropolitan statistical area:{cbsa}"},
        )

    def place(self, variables: str, place: str, state: str = SHELBY_STATE) -> dict[str, str]:
        """Census place (city) cut, e.g. place='48000' for Memphis city, TN."""
        return self._get(variables, {"for": f"place:{place}", "in": f"state:{state}"})

    def county_tracts(self, variables: str, state: str = SHELBY_STATE,
                      county: str = SHELBY_COUNTY) -> list[dict[str, str]]:
        """One dict per census tract in the county."""
        # The two-level `in` is a list, which requests renders as the repeated
        # form `in=state:47&in=county:157`. Census documents both that and the
        # space-separated `in=state:47%20county:157`; the repeated form is used
        # here because it contains no space, so nothing depends on whether the
        # server decodes an encoded space as `+` or `%20`.
        rows = self._rows(
            variables,
            {"for": "tract:*", "in": [f"state:{state}", f"county:{county}"]},
        )
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
