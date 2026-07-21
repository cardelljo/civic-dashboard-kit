"""
Federal Reserve Economic Data (FRED) API client.

Same shape as toolkit.census.AcsClient: a thin, free-key-based series-fetch
client so any dashboard can pull a FRED series for any geography (a metro's
FRED series ID, e.g. Memphis MSA unemployment) without re-learning FRED's
response quirks -- the "." sentinel for a missing observation, and the
realtime_start/realtime_end vintage fields most callers don't need.

Requires a free API key (fred.stlouisfed.org/docs/api/api_key.html).

Usage:
    from toolkit.fred import FredClient

    fred = FredClient(api_key="...")
    trend = fred.series_observations("MPHNA", start="2015-01-01")
    # -> [{"date": "2015-01-01", "value": 123.4}, ...] oldest -> newest;
    #    missing observations are dropped, not returned as None.
"""

from __future__ import annotations

import requests

FRED_API_URL = "https://api.stlouisfed.org/fred/series/observations"

# FRED's sentinel string for "no observation available for this period" --
# distinct from a real zero, so it must be filtered rather than parsed as 0.0.
_MISSING_VALUE = "."


class FredClient:
    """FRED series-observations client."""

    def __init__(self, api_key: str, timeout: int = 30):
        self.api_key = api_key
        self.timeout = timeout

    def series_observations(
        self,
        series_id: str,
        start: str | None = None,
        end: str | None = None,
        frequency: str | None = None,
    ) -> list[dict]:
        """
        Pull a FRED series's observations.

        `start`/`end` are 'YYYY-MM-DD' strings (FRED's observation_start/
        observation_end); omit either to get FRED's full available history.
        `frequency` (e.g. 'm', 'q', 'a') only needs setting if aggregating a
        higher-frequency series -- most economy series are natively monthly
        or annual already.

        Returns [{"date": "2024-01-01", "value": 4.2}, ...] oldest -> newest,
        with missing ('.') observations dropped rather than returned as None,
        since a dropped period should read as "not yet published," not
        "published as zero."
        """
        params = {
            "series_id": series_id,
            "api_key": self.api_key,
            "file_type": "json",
        }
        if start:
            params["observation_start"] = start
        if end:
            params["observation_end"] = end
        if frequency:
            params["frequency"] = frequency

        r = requests.get(FRED_API_URL, params=params, timeout=self.timeout)
        r.raise_for_status()
        body = r.json()
        observations = body.get("observations", [])

        return [
            {"date": obs["date"], "value": float(obs["value"])}
            for obs in observations
            if obs.get("value") != _MISSING_VALUE
        ]
