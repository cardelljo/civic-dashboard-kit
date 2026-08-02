"""Offline fixtures for shared toolkit clients; no test performs network I/O."""
from datetime import datetime
from urllib.parse import parse_qs

from toolkit.arcgis import FeatureService, date_where
from toolkit.bea import BeaClient
from toolkit.census import AcsClient, bls_monthly_series
from toolkit.fred import FredClient


class Response:
    def __init__(self, body): self.body = body
    def raise_for_status(self): pass
    def json(self): return self.body


def q(query: str) -> dict[str, list[str]]:
    """Decode an ACS query string back into parameters.

    `AcsClient` encodes its own query (to emit `%20` rather than `+` for the
    spaces in Census geography names), so assertions decode the wire format
    instead of reading a params dict. `parse_qs` treats `+` as a space, so
    checking raw substrings below is what actually pins the encoding.
    """
    return parse_qs(query)


def test_acs_subject_table_and_pct(monkeypatch):
    seen = []
    def get(url, params, timeout):
        seen.append(url)
        return Response([["NAME", "S1701_C03_001E", "S1701_C01_001E"], ["Shelby", "12", "100"]])
    monkeypatch.setattr("toolkit.census.requests.get", get)
    client = AcsClient(2024)
    assert client.pct("S1701_C03_001E", "S1701_C01_001E") == 12.0
    assert seen[0].endswith("/acs/acs5/subject")


def test_acs_msa_geography_clause(monkeypatch):
    seen = []
    def get(url, params, timeout):
        seen.append(params)
        return Response([["NAME", "B19013_001E"], ["Memphis, TN-MS-AR Metro Area", "58000"]])
    monkeypatch.setattr("toolkit.census.requests.get", get)
    client = AcsClient(2024)
    result = client.msa("B19013_001E", cbsa="32820")
    assert result["B19013_001E"] == "58000"
    assert q(seen[0])["for"] == [
        "metropolitan statistical area/micropolitan statistical area:32820"
    ]
    # This geography name is the one place a space reaches the wire. Census's
    # examples encode it %20; requests' own quote_plus would emit `+`, which is
    # why the client encodes the query itself. Assert on the raw string --
    # parse_qs decodes both forms identically and would not catch a regression.
    assert "metropolitan%20statistical%20area/micropolitan" in seen[0]
    assert "+" not in seen[0]


def test_acs_place_geography_clause(monkeypatch):
    seen = []
    def get(url, params, timeout):
        seen.append(params)
        return Response([["NAME", "B19013_001E"], ["Memphis city, Tennessee", "45000"]])
    monkeypatch.setattr("toolkit.census.requests.get", get)
    client = AcsClient(2024)
    result = client.place("B19013_001E", place="48000")
    assert result["B19013_001E"] == "45000"
    assert q(seen[0])["for"] == ["place:48000"]
    assert q(seen[0])["in"] == ["state:47"]


def test_bls_filters_annual_average_and_sorts(monkeypatch):
    def post(url, json, timeout):
        return Response({"status": "REQUEST_SUCCEEDED", "Results": {"series": [{"data": [
            {"year": "2025", "period": "M13", "value": "99"},
            {"year": "2025", "period": "M02", "value": "4.1"},
            {"year": "2025", "period": "M01", "value": "4.2"},
        ]}]}})
    monkeypatch.setattr("toolkit.census.requests.post", post)
    assert bls_monthly_series("fixture", months=2) == [{"month": "Jan 2025", "value": 4.2}, {"month": "Feb 2025", "value": 4.1}]


def test_arcgis_grouped_count_and_date_clause(monkeypatch):
    def get(url, timeout):
        return Response({"features": [{"attributes": {"category": "A", "total": 3}}]})
    monkeypatch.setattr("toolkit.arcgis.requests.get", get)
    assert FeatureService("https://example.test/0").count_by("category") == {"A": 3}
    assert date_where("when", datetime(2025, 1, 1), datetime(2025, 1, 31)) == "when >= date '2025-01-01' AND when <= date '2025-01-31'"


def test_fred_drops_missing_observations(monkeypatch):
    seen = []
    def get(url, params, timeout):
        seen.append(params)
        return Response({"observations": [
            {"date": "2024-01-01", "value": "4.2"},
            {"date": "2024-02-01", "value": "."},  # FRED's missing-value sentinel
            {"date": "2024-03-01", "value": "4.4"},
        ]})
    monkeypatch.setattr("toolkit.fred.requests.get", get)
    client = FredClient(api_key="fixture-key")
    result = client.series_observations("MPHNA", start="2024-01-01")
    assert result == [
        {"date": "2024-01-01", "value": 4.2},
        {"date": "2024-03-01", "value": 4.4},
    ]
    assert seen[0]["series_id"] == "MPHNA"
    assert seen[0]["observation_start"] == "2024-01-01"


def test_bea_regional_gdp_strips_comma_grouping(monkeypatch):
    seen = []
    def get(url, params, timeout):
        seen.append(params)
        return Response({"BEAAPI": {"Results": {"Data": [
            {"GeoFips": "28700", "GeoName": "Memphis, TN-MS-AR (Metropolitan Statistical Area)",
             "TimePeriod": "2023", "DataValue": "102,900.0"},
        ]}}})
    monkeypatch.setattr("toolkit.bea.requests.get", get)
    client = BeaClient(api_key="fixture-key")
    result = client.regional_gdp(table_name="CAGDP1", geo_fips="28700", year="2023")
    assert result == [{
        "geo_fips": "28700",
        "geo_name": "Memphis, TN-MS-AR (Metropolitan Statistical Area)",
        "period": "2023",
        "value": 102900.0,
    }]
    assert seen[0]["TableName"] == "CAGDP1"


def test_bea_raises_on_api_error(monkeypatch):
    def get(url, params, timeout):
        return Response({"BEAAPI": {"Results": {"Error": {"APIErrorCode": "3", "APIErrorDescription": "bad param"}}}})
    monkeypatch.setattr("toolkit.bea.requests.get", get)
    client = BeaClient(api_key="fixture-key")
    try:
        client.regional_gdp(table_name="CAGDP1", geo_fips="bad")
        assert False, "expected RuntimeError"
    except RuntimeError as e:
        assert "bad param" in str(e)


def test_acs_sends_api_key_when_configured(monkeypatch):
    seen = []
    def get(url, params, timeout):
        seen.append(params)
        return Response([["NAME", "B19013_001E"], ["Memphis, TN-MS-AR Metro Area", "58000"]])
    monkeypatch.setattr("toolkit.census.requests.get", get)
    AcsClient(2023, api_key="fixture-key").msa("B19013_001E", cbsa="32820")
    assert q(seen[0])["key"] == ["fixture-key"]


def test_acs_omits_key_when_not_configured(monkeypatch):
    """Backwards compatibility: existing callers construct AcsClient(year)."""
    seen = []
    def get(url, params, timeout):
        seen.append(params)
        return Response([["NAME", "B19013_001E"], ["Shelby County", "58000"]])
    monkeypatch.setattr("toolkit.census.requests.get", get)
    AcsClient(2023).county("B19013_001E")
    assert "key" not in q(seen[0])


def test_county_tracts_also_carries_the_key(monkeypatch):
    """Tract queries used to build their own URL, so the key was easy to drop."""
    seen = []
    def get(url, params, timeout):
        seen.append(params)
        return Response([["NAME", "B19013_001E", "tract"], ["Tract 1", "42000", "000100"]])
    monkeypatch.setattr("toolkit.census.requests.get", get)
    AcsClient(2023, api_key="fixture-key").county_tracts("B19013_001E")
    assert q(seen[0])["key"] == ["fixture-key"]


def test_county_tracts_repeats_the_in_parameter(monkeypatch):
    """`in` is a list, so the query carries `in=state:47&in=county:157`.

    Census documents that form alongside the space-separated
    `in=state:47%20county:157`. The repeated form is chosen because it has no
    space in it, so correctness does not hinge on whether the server reads an
    encoded space as `+` or `%20`.
    """
    seen = []
    def get(url, params, timeout):
        seen.append(params)
        return Response([["NAME", "B19013_001E", "tract"], ["Tract 1", "42000", "000100"]])
    monkeypatch.setattr("toolkit.census.requests.get", get)
    AcsClient(2023).county_tracts("B19013_001E")
    assert q(seen[0])["in"] == ["state:47", "county:157"]
    assert q(seen[0])["for"] == ["tract:*"]
    assert "in=state:47&in=county:157" in seen[0]


def test_acs_names_a_missing_key_instead_of_leaking_a_decode_error(monkeypatch):
    """A keyless request 200s with HTML, so raise_for_status() cannot catch it."""
    class HtmlResponse:
        def raise_for_status(self): pass
        def json(self): raise ValueError("Expecting value: line 1 column 1 (char 0)")

    monkeypatch.setattr("toolkit.census.requests.get",
                        lambda url, params, timeout: HtmlResponse())
    try:
        AcsClient(2023).county("B19013_001E")
        assert False, "expected RuntimeError"
    except RuntimeError as e:
        assert "API key" in str(e)
