"""
Integration tests for toolkit.postgres_store against a real Postgres.

Requires a live Postgres reachable via the TOOLKIT_TEST_DATABASE_URL env var
(e.g. "postgresql://user:pass@localhost/dbname") -- this module's whole point
is exercising `DISTINCT ON`/JSONB behavior a SQLite-based test can't stand in
for (see toolkit/observations.py's tests for the SQLite-backed sibling store,
which needs no such fixture). Skips entirely if that env var isn't set, so
901education's own CI (no Postgres) is unaffected; 901economy's CI provides it
via a Postgres service container.

The schema below is a minimal stand-in for 901economy's real db/schema.sql --
just the tables/view postgres_store.py actually touches -- so this test suite
verifies the *module's* SQL logic without needing a cross-repo checkout of the
economy repo's schema file. 901economy's own repo has its own integration
tests against the real schema.
"""
import os

import psycopg2
import psycopg2.extras
import pytest

from toolkit.postgres_store import (
    Observation,
    append,
    approve_run,
    compute_payload_hash,
    finish_run,
    latest,
    pending_reviews,
    record_run,
    reject_run,
)

DATABASE_URL = os.environ.get("TOOLKIT_TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(
    not DATABASE_URL, reason="TOOLKIT_TEST_DATABASE_URL not set -- no Postgres available"
)
# The guard that keeps an all-skipped run from reading as a pass lives in
# tests/test_ci_guards.py -- it cannot live here, because this module-level
# `pytestmark` would skip it in exactly the case it exists to catch.

SCHEMA = """
CREATE TABLE IF NOT EXISTS geographies (
    geography_id TEXT PRIMARY KEY, geography_type TEXT NOT NULL, name TEXT NOT NULL,
    is_shelby BOOLEAN NOT NULL DEFAULT FALSE
);
CREATE TABLE IF NOT EXISTS sources (
    source_key TEXT PRIMARY KEY, source_name TEXT NOT NULL,
    tier TEXT NOT NULL CHECK (tier IN ('T1','T2','T3','T4')),
    cadence TEXT NOT NULL, requires_review BOOLEAN NOT NULL DEFAULT FALSE
);
CREATE TABLE IF NOT EXISTS indicator_defs (
    indicator_id TEXT PRIMARY KEY, label TEXT NOT NULL, unit TEXT NOT NULL,
    good_direction TEXT, description TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS source_runs (
    run_id BIGSERIAL PRIMARY KEY, source_key TEXT NOT NULL REFERENCES sources(source_key),
    started_at TIMESTAMPTZ NOT NULL DEFAULT now(), finished_at TIMESTAMPTZ,
    status TEXT NOT NULL DEFAULT 'success'
        CHECK (status IN ('success','partial','failed','pending_review','rejected')),
    row_count INTEGER, review_artifact JSONB, notes TEXT
);
CREATE TABLE IF NOT EXISTS approvals (
    approval_id BIGSERIAL PRIMARY KEY, run_id BIGINT NOT NULL REFERENCES source_runs(run_id),
    decision TEXT NOT NULL CHECK (decision IN ('approved','rejected','revoked')),
    reviewer TEXT NOT NULL, reason TEXT, payload_hash TEXT NOT NULL,
    decided_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS indicators (
    id BIGSERIAL PRIMARY KEY, indicator_id TEXT NOT NULL REFERENCES indicator_defs(indicator_id),
    geography_id TEXT NOT NULL REFERENCES geographies(geography_id), period TEXT NOT NULL,
    value NUMERIC, demographic_group TEXT NOT NULL DEFAULT 'all',
    source_key TEXT NOT NULL REFERENCES sources(source_key), source_url TEXT,
    vintage TEXT NOT NULL, tier TEXT NOT NULL CHECK (tier IN ('T1','T2','T3','T4')),
    suppressed BOOLEAN NOT NULL DEFAULT FALSE, run_id BIGINT NOT NULL REFERENCES source_runs(run_id),
    retrieved_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE OR REPLACE VIEW indicators_current AS
SELECT DISTINCT ON (i.indicator_id, i.geography_id, i.period, i.demographic_group) i.*
FROM indicators i JOIN source_runs r ON r.run_id = i.run_id
WHERE r.status = 'success'
ORDER BY i.indicator_id, i.geography_id, i.period, i.demographic_group, i.retrieved_at DESC;
"""


@pytest.fixture()
def conn():
    connection = psycopg2.connect(DATABASE_URL)
    with connection.cursor() as cur:
        cur.execute(SCHEMA)
    connection.commit()
    yield connection
    # Roll back first: a test that deliberately provokes a database error (the
    # UndefinedColumn cases below) leaves the transaction aborted, and every
    # statement in this teardown -- including the TRUNCATE -- would then be
    # ignored, leaking rows and columns into the *next* run rather than this
    # one. That failure looks like an unrelated UniqueViolation later, so it is
    # worth the one line.
    connection.rollback()
    # Truncate rather than drop -- keeps the schema in place for the next test,
    # matching how a real deployment never drops these tables either.
    with connection.cursor() as cur:
        cur.execute(
            "TRUNCATE approvals, indicators, source_runs, indicator_defs, sources, "
            "geographies RESTART IDENTITY CASCADE"
        )
    connection.commit()
    connection.close()


def _seed(conn):
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO geographies (geography_id, geography_type, name, is_shelby) VALUES "
            "('memphis-msa','msa','Memphis, TN-MS-AR Metro Area', true)"
        )
        cur.execute(
            "INSERT INTO sources (source_key, source_name, tier, cadence) VALUES "
            "('fred-mphna','FRED Total Nonfarm Employment','T1','monthly'), "
            "('milken-bpc','Milken Best-Performing Cities','T3','annual')"
        )
        cur.execute(
            "INSERT INTO indicator_defs (indicator_id, label, unit, good_direction, description) "
            "VALUES ('total-nonfarm-employment','Employment','jobs','up','fixture'), "
            "('milken-bpc-rank','Milken rank','rank',NULL,'fixture')"
        )
    conn.commit()


def test_append_and_latest_round_trip(conn):
    _seed(conn)
    run_id = record_run(conn, source_key="fred-mphna")
    n = append(conn, "fred-mphna", run_id, tier="T1", observations=[
        Observation(indicator_id="total-nonfarm-employment", geography_id="memphis-msa",
                    period="2026-06", value=665800.0, vintage="FRED fixture"),
    ])
    finish_run(conn, run_id, row_count=n)

    rows = latest(conn, "total-nonfarm-employment", geography_id="memphis-msa")
    assert len(rows) == 1
    assert rows[0]["value"] == 665800.0
    assert rows[0]["period"] == "2026-06"


def test_revision_supersedes_but_raw_table_keeps_both(conn):
    _seed(conn)
    run_1 = record_run(conn, source_key="fred-mphna")
    append(conn, "fred-mphna", run_1, tier="T1", observations=[
        Observation(indicator_id="total-nonfarm-employment", geography_id="memphis-msa",
                    period="2026-06", value=665800.0, vintage="original"),
    ])
    run_2 = record_run(conn, source_key="fred-mphna")
    append(conn, "fred-mphna", run_2, tier="T1", observations=[
        Observation(indicator_id="total-nonfarm-employment", geography_id="memphis-msa",
                    period="2026-06", value=666100.0, vintage="revised"),
    ])

    current = latest(conn, "total-nonfarm-employment", geography_id="memphis-msa")
    assert len(current) == 1
    assert current[0]["value"] == 666100.0

    with conn.cursor() as cur:
        cur.execute(
            "SELECT count(*) FROM indicators WHERE indicator_id = 'total-nonfarm-employment'"
        )
        assert cur.fetchone()[0] == 2, "both rows must survive in the raw table for audit"


def test_dropped_metric_still_returns_retained_history(conn):
    """A metric a source stops publishing keeps its prior history visible,
    same guarantee toolkit.observations.py's SQLite store makes."""
    _seed(conn)
    run_1 = record_run(conn, source_key="fred-mphna")
    append(conn, "fred-mphna", run_1, tier="T1", observations=[
        Observation(indicator_id="total-nonfarm-employment", geography_id="memphis-msa",
                    period="2026-05", value=664200.0, vintage="fixture"),
        Observation(indicator_id="total-nonfarm-employment", geography_id="memphis-msa",
                    period="2026-06", value=665800.0, vintage="fixture"),
    ])
    # A later run only re-publishes one of the two periods (the other simply
    # wasn't in that month's release) -- both periods must still be visible.
    run_2 = record_run(conn, source_key="fred-mphna")
    append(conn, "fred-mphna", run_2, tier="T1", observations=[
        Observation(indicator_id="total-nonfarm-employment", geography_id="memphis-msa",
                    period="2026-06", value=666100.0, vintage="revised"),
    ])
    rows = latest(conn, "total-nonfarm-employment", geography_id="memphis-msa")
    periods = {r["period"]: r["value"] for r in rows}
    assert periods == {"2026-05": 664200.0, "2026-06": 666100.0}


def test_suppressed_value_stays_null_not_a_guess(conn):
    _seed(conn)
    run_id = record_run(conn, source_key="fred-mphna")
    append(conn, "fred-mphna", run_id, tier="T1", observations=[
        Observation(indicator_id="total-nonfarm-employment", geography_id="memphis-msa",
                    period="2026-06", value=None, vintage="fixture", suppressed=True),
    ])
    rows = latest(conn, "total-nonfarm-employment", geography_id="memphis-msa")
    assert rows[0]["value"] is None
    assert rows[0]["suppressed"] is True


def test_t3_pending_review_is_invisible_until_approved(conn):
    _seed(conn)
    run_id = record_run(
        conn, source_key="milken-bpc", status="pending_review",
        review_artifact={"extracted_rank": 214, "source_quote": "Memphis ranked 214th..."},
    )
    obs = [Observation(indicator_id="milken-bpc-rank", geography_id="memphis-msa",
                        period="2026", value=214.0, vintage="Milken fixture")]
    append(conn, "milken-bpc", run_id, tier="T3", observations=obs)

    assert latest(conn, "milken-bpc-rank", geography_id="memphis-msa") == []
    pending = pending_reviews(conn)
    assert len(pending) == 1
    assert pending[0]["run_id"] == run_id
    assert pending[0]["review_artifact"]["extracted_rank"] == 214

    approve_run(conn, run_id, reviewer="fixture-reviewer", payload_hash=compute_payload_hash(obs))
    rows = latest(conn, "milken-bpc-rank", geography_id="memphis-msa")
    assert len(rows) == 1 and rows[0]["value"] == 214.0
    assert pending_reviews(conn) == []


def test_t3_rejected_run_never_becomes_visible(conn):
    _seed(conn)
    run_id = record_run(conn, source_key="milken-bpc", status="pending_review",
                         review_artifact={"extracted_rank": 999})
    append(conn, "milken-bpc", run_id, tier="T3", observations=[
        Observation(indicator_id="milken-bpc-rank", geography_id="memphis-msa",
                    period="2026", value=999.0, vintage="fixture"),
    ])
    reject_run(conn, run_id, reviewer="fixture-reviewer",
               reason="mis-extracted", payload_hash="irrelevant-for-rejection")

    assert latest(conn, "milken-bpc-rank", geography_id="memphis-msa") == []
    assert pending_reviews(conn) == []

    with conn.cursor() as cur:
        cur.execute("SELECT decision, reason FROM approvals WHERE run_id = %s", (run_id,))
        assert cur.fetchone() == ("rejected", "mis-extracted")


def test_approvals_are_append_only(conn):
    """A 'revoked' decision is a new row, never an edit to the 'approved' one --
    the decision history must stay tamper-evident by construction."""
    _seed(conn)
    run_id = record_run(conn, source_key="milken-bpc", status="pending_review")
    obs = [Observation(indicator_id="milken-bpc-rank", geography_id="memphis-msa",
                        period="2026", value=214.0, vintage="fixture")]
    append(conn, "milken-bpc", run_id, tier="T3", observations=obs)
    phash = compute_payload_hash(obs)
    approve_run(conn, run_id, reviewer="fixture-reviewer", payload_hash=phash)

    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO approvals (run_id, decision, reviewer, reason, payload_hash) "
            "VALUES (%s, 'revoked', %s, %s, %s)",
            (run_id, "fixture-reviewer", "later found to be wrong", phash),
        )
    conn.commit()

    with conn.cursor() as cur:
        cur.execute("SELECT decision FROM approvals WHERE run_id = %s ORDER BY approval_id", (run_id,))
        decisions = [row[0] for row in cur.fetchall()]
    assert decisions == ["approved", "revoked"], "both decisions must coexist, neither overwritten"


# --- Optional finer grain (subject/grade/unit/row_key) -------------------------
#
# These four columns exist in 901education's `indicators` table and NOT in
# 901economy's. The pair of tests below is the actual contract: a batch that
# sets none of them must still work against a table that lacks them (economy,
# unchanged), and a batch that sets them must round-trip against a table that
# has them (education).

# `indicators_current` is defined as `SELECT DISTINCT ON (...) i.*`, and a view
# resolves `*` to a fixed column list when it is CREATEd -- adding a column to
# `indicators` afterwards does NOT appear in the view. So this fixture drops and
# recreates the view around the ALTER rather than only altering the table.
# 901education's real db/schema.sql creates the table with all columns before
# the view, so it never hits this; a later ALTER on the deployed database would.
WIDE_COLUMNS = """
DROP VIEW IF EXISTS indicators_current;
ALTER TABLE indicators ADD COLUMN IF NOT EXISTS unit       TEXT;
ALTER TABLE indicators ADD COLUMN IF NOT EXISTS row_key    TEXT;
ALTER TABLE indicators ADD COLUMN IF NOT EXISTS dimensions JSONB;
"""

NARROW_AGAIN = """
DROP VIEW IF EXISTS indicators_current;
ALTER TABLE indicators
    DROP COLUMN IF EXISTS unit, DROP COLUMN IF EXISTS row_key,
    DROP COLUMN IF EXISTS dimensions;
"""

# The view text, reused to rebuild it on both sides of the column change.
VIEW_SQL = SCHEMA[SCHEMA.index("CREATE OR REPLACE VIEW indicators_current"):]


@pytest.fixture()
def wide_conn(conn):
    """`conn`, with the four optional columns added -- 901education's shape."""
    with conn.cursor() as cur:
        cur.execute(WIDE_COLUMNS)
        cur.execute(VIEW_SQL)
    conn.commit()
    yield conn
    conn.rollback()
    with conn.cursor() as cur:
        cur.execute(NARROW_AGAIN)
        cur.execute(VIEW_SQL)
    conn.commit()


def test_legacy_table_without_optional_columns_still_accepts_appends(conn):
    """901economy's live table has none of the four columns. Setting none of
    them must emit SQL that never names them, or economy breaks on upgrade."""
    _seed(conn)
    run_id = record_run(conn, source_key="fred-mphna")
    n = append(conn, "fred-mphna", run_id, tier="T1", observations=[
        Observation(indicator_id="total-nonfarm-employment", geography_id="memphis-msa",
                    period="2026-06", value=665800.0, vintage="FRED fixture"),
        Observation(indicator_id="total-nonfarm-employment", geography_id="memphis-msa",
                    period="2026-07", value=666200.0, vintage="FRED fixture"),
    ])
    assert n == 2
    assert len(latest(conn, "total-nonfarm-employment", geography_id="memphis-msa")) == 2


def test_optional_columns_round_trip_when_the_table_has_them(wide_conn):
    _seed(wide_conn)
    run_id = record_run(wide_conn, source_key="fred-mphna")
    append(wide_conn, "fred-mphna", run_id, tier="T1", observations=[
        Observation(indicator_id="total-nonfarm-employment", geography_id="memphis-msa",
                    period="2018-19", value=20.6, vintage="TDOE fixture", unit="%",
                    row_key="tdoe-academic-outcomes|2018-19|proficiency",
                    dimensions={"grade": "all-grades"}),
    ])
    rows = latest(wide_conn, "total-nonfarm-employment", geography_id="memphis-msa")
    assert len(rows) == 1
    assert rows[0]["unit"] == "%"
    assert rows[0]["row_key"] == "tdoe-academic-outcomes|2018-19|proficiency"
    # Comes back as a dict, not a JSON string -- psycopg2 decodes JSONB natively.
    assert rows[0]["dimensions"] == {"grade": "all-grades"}


def test_dimensions_keys_are_the_dashboards_own_not_this_modules(wide_conn):
    """The whole point of an open dict: a domain this module has never heard of
    stores its axes without the toolkit learning that vocabulary."""
    _seed(wide_conn)
    run_id = record_run(wide_conn, source_key="fred-mphna")
    append(wide_conn, "fred-mphna", run_id, tier="T1", observations=[
        Observation(indicator_id="total-nonfarm-employment", geography_id="memphis-msa",
                    period="2024", value=1.0, vintage="fixture",
                    dimensions={"offense_type": "burglary", "disposition": "dismissed"}),
    ])
    row = latest(wide_conn, "total-nonfarm-employment", geography_id="memphis-msa")[0]
    assert row["dimensions"] == {"offense_type": "burglary", "disposition": "dismissed"}


def test_partially_set_optional_columns_leave_the_others_null(wide_conn):
    """A batch setting only row_key must not fail for want of unit/dimensions."""
    _seed(wide_conn)
    run_id = record_run(wide_conn, source_key="fred-mphna")
    append(wide_conn, "fred-mphna", run_id, tier="T1", observations=[
        Observation(indicator_id="total-nonfarm-employment", geography_id="memphis-msa",
                    period="2024-25", value=1234.0, vintage="TDOE fixture",
                    row_key="tdoe-district-snapshot|2024-25|enrollment"),
    ])
    row = latest(wide_conn, "total-nonfarm-employment", geography_id="memphis-msa")[0]
    assert row["row_key"] == "tdoe-district-snapshot|2024-25|enrollment"
    assert row["unit"] is None and row["dimensions"] is None


def test_mixed_batch_writes_null_for_observations_that_omit_a_set_column(wide_conn):
    """Education's real ledger mixes rows carrying a grade band with rows that
    have none (only 2 of its 26 metrics vary on grade). Both land in one
    append, and the ones without must not acquire an empty dict."""
    _seed(wide_conn)
    run_id = record_run(wide_conn, source_key="fred-mphna")
    append(wide_conn, "fred-mphna", run_id, tier="T1", observations=[
        Observation(indicator_id="total-nonfarm-employment", geography_id="memphis-msa",
                    period="2018-19", value=20.6, vintage="fixture",
                    dimensions={"grade": "3"}, row_key="with-dimensions"),
        Observation(indicator_id="total-nonfarm-employment", geography_id="memphis-msa",
                    period="2019-20", value=1234.0, vintage="fixture",
                    row_key="without-dimensions"),
    ])
    by_key = {r["row_key"]: r for r in latest(conn=wide_conn, indicator_id="total-nonfarm-employment")}
    assert by_key["with-dimensions"]["dimensions"] == {"grade": "3"}
    assert by_key["without-dimensions"]["dimensions"] is None


def test_setting_an_optional_column_against_a_legacy_table_is_a_hard_error(conn):
    """The value has nowhere to go, so failing loudly is the correct outcome --
    not silently dropping the column."""
    _seed(conn)
    run_id = record_run(conn, source_key="fred-mphna")
    with pytest.raises(psycopg2.errors.UndefinedColumn):
        append(conn, "fred-mphna", run_id, tier="T1", observations=[
            Observation(indicator_id="total-nonfarm-employment", geography_id="memphis-msa",
                        period="2026-06", value=1.0, vintage="fixture", row_key="nowhere"),
        ])
    conn.rollback()


# --- Optional run-level provenance --------------------------------------------
#
# 901education's NDJSON ledger records six fields per run that 901economy's
# `source_runs` table has no columns for. Same contract as the observation
# columns above: named only when supplied.

WIDE_RUN_COLUMNS = """
ALTER TABLE source_runs ADD COLUMN IF NOT EXISTS script         TEXT;
ALTER TABLE source_runs ADD COLUMN IF NOT EXISTS source_name    TEXT;
ALTER TABLE source_runs ADD COLUMN IF NOT EXISTS source_url     TEXT;
ALTER TABLE source_runs ADD COLUMN IF NOT EXISTS source_vintage TEXT;
ALTER TABLE source_runs ADD COLUMN IF NOT EXISTS fetched_at     TIMESTAMPTZ;
ALTER TABLE source_runs ADD COLUMN IF NOT EXISTS content_hash   TEXT;
"""


@pytest.fixture()
def run_conn(conn):
    """`conn`, with the six optional run-provenance columns -- education's shape."""
    with conn.cursor() as cur:
        cur.execute(WIDE_RUN_COLUMNS)
    conn.commit()
    yield conn
    conn.rollback()
    with conn.cursor() as cur:
        cur.execute(
            "ALTER TABLE source_runs "
            "DROP COLUMN IF EXISTS script, DROP COLUMN IF EXISTS source_name, "
            "DROP COLUMN IF EXISTS source_url, DROP COLUMN IF EXISTS source_vintage, "
            "DROP COLUMN IF EXISTS fetched_at, DROP COLUMN IF EXISTS content_hash"
        )
    conn.commit()


def _run_row(conn, run_id):
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute("SELECT * FROM source_runs WHERE run_id = %s", (run_id,))
        return dict(cur.fetchone())


def test_record_run_without_provenance_works_on_a_legacy_source_runs_table(conn):
    """901economy calls record_run with none of the six. Must not name them."""
    _seed(conn)
    run_id = record_run(conn, source_key="fred-mphna")
    assert _run_row(conn, run_id)["status"] == "success"


def test_record_run_stores_provenance_when_the_table_has_the_columns(run_conn):
    _seed(run_conn)
    run_id = record_run(
        run_conn,
        source_key="fred-mphna",
        script="scripts/fetch_tdoe_assessment.py",
        source_name="TDOE TCAP Assessment Files",
        source_url="https://example.invalid/district_assessment_file.xlsx",
        source_vintage="2025-26",
        fetched_at="2026-06-24T21:33:49+00:00",
        content_hash="a" * 64,
    )
    row = _run_row(run_conn, run_id)
    assert row["script"] == "scripts/fetch_tdoe_assessment.py"
    assert row["source_vintage"] == "2025-26"
    assert row["content_hash"] == "a" * 64
    # The whole point of accepting fetched_at: a backfilled historical run keeps
    # its real date rather than the migration's.
    assert row["fetched_at"].year == 2026 and row["fetched_at"].month == 6


def test_fetched_at_is_independent_of_started_at(run_conn):
    """`started_at` defaults to now(); a backfilled run's `fetched_at` is older.
    If these were conflated, backfilling would silently restamp history."""
    _seed(run_conn)
    run_id = record_run(run_conn, source_key="fred-mphna",
                        fetched_at="2025-09-05T16:44:10+00:00")
    row = _run_row(run_conn, run_id)
    assert row["fetched_at"] < row["started_at"]


def test_partial_provenance_leaves_the_rest_null(run_conn):
    _seed(run_conn)
    run_id = record_run(run_conn, source_key="fred-mphna", content_hash="b" * 64)
    row = _run_row(run_conn, run_id)
    assert row["content_hash"] == "b" * 64
    assert row["script"] is None and row["source_vintage"] is None


def test_provenance_against_a_legacy_table_is_a_hard_error(conn):
    _seed(conn)
    with pytest.raises(psycopg2.errors.UndefinedColumn):
        record_run(conn, source_key="fred-mphna", script="scripts/nowhere.py")
    conn.rollback()
