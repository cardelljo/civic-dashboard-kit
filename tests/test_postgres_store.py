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
