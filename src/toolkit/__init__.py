"""
Civic data toolkit — shared data-acquisition clients for Bluff City Tech dashboards.

Extracted from 901justice's ETL scripts so 901education (and future dashboards,
e.g. economic development) reuse one implementation of each retrieval pattern:

    arcgis      ArcGIS Feature Service queries with server-side aggregation
    census      U.S. Census ACS (detail + subject tables) and BLS time series
    ai_extract  Multi-provider AI structured extraction from unstructured text
    pdf_report  PDF report pipeline: download -> text -> regex-first, AI-fallback
    snapshot    _meta data-provenance contract: writer + validators
    geo         Dependency-free shapefile -> GeoJSON conversion

Domain-specific fetch scripts live in scripts/ and should stay thin recipes
that call these clients. See toolkit/README.md and DATA_SNAPSHOT_CONTRACT.md.
"""

from . import snapshot  # noqa: F401
