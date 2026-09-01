"""
Postgres-backed indicators store for 901economy (or any future higher-volume dashboard).

Same design as toolkit/observations.py -- append-only, "newest row wins per
logical cell" -- ported to a live Postgres connection instead of git-committed
NDJSON materialized into an in-memory sqlite3 db at build time. The schema
this module reads and writes is defined once in 901economy's db/schema.sql,
not here: this module has no CREATE TABLE statements of its own and assumes
the schema already exists on whatever connection it's given.

Requires psycopg2 (the `postgres` extra):
    pip install "civic-dashboard-kit[postgres] @ git+https://github.com/cardelljo/civic-dashboard-kit.git@main"

Instance and schema layout (one instance, one schema per dashboard, plus a
shared `geo` schema with PostGIS) is recorded in docs/ARCHITECTURE.md.

Usage (in a pipeline extractor, after computing the values it would otherwise
write to JSON):

    from toolkit.postgres_store import Observation, record_run, append

    run_id = record_run(conn, source_key="fred-mphna")
    append(conn, "fred-mphna", run_id, tier="T1", observations=[
        Observation(indicator_id="total-nonfarm-employment", geography_id="memphis-msa",
                    period="2026-06", value=665800.0, vintage="FRED, retrieved 2026-07-20"),
    ])

T3 (AI-extracted) runs stop at `pending_review` and are approved or rejected
through the `/admin` Review Queue -- there is no GitHub PR in this loop
(PLAN.md §0.3):

    run_id = record_run(conn, source_key="milken-bpc", status="pending_review",
                         review_artifact={"extracted": [...], "source_offsets": [...]})
    append(conn, "milken-bpc", run_id, tier="T3", observations=[...])
    # ... later, from the Review Queue page:
    approve_run(conn, run_id, reviewer="cardell", payload_hash=compute_payload_hash(observations))
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Iterable

try:
    import psycopg2
    import psycopg2.extras
except ImportError as exc:  # pragma: no cover - exercised only when the extra is missing
    raise ImportError(
        "toolkit.postgres_store requires the 'postgres' extra: "
        'pip install "civic-dashboard-kit[postgres] @ '
        'git+https://github.com/cardelljo/civic-dashboard-kit.git@main"'
    ) from exc


@dataclass(frozen=True)
class Observation:
    """One fact: an indicator's value for a geography/period/group, as published.

    `suppressed=True` means the source withheld the cell -- `value` must be
    None in that case, never a guess. Mirrors toolkit.observations.Observation;
    the field *names* differ to match a dashboard's `indicators` table
    (`indicator_id` not `metric_id`, `demographic_group` not `student_group`).

    The last four fields are optional and default to None. 901economy sets
    none of them -- it encodes those dimensions in the `indicator_id` slug
    itself, e.g. 'employment-tdl' (PLAN.md §3) -- while 901education carries
    them as real columns because its build step queries `row_key` directly.
    """

    indicator_id: str
    geography_id: str
    period: str
    value: float | None
    vintage: str
    demographic_group: str = "all"
    source_url: str | None = None
    suppressed: bool = False
    # Optional finer grain, added for 901education (the second consumer). A
    # dashboard whose `indicators` table lacks these columns is unaffected:
    # `append()` only names a column when some observation in the batch sets
    # it, so a batch that leaves all four None emits exactly the SQL it always
    # did. 901economy encodes these dimensions in the `indicator_id` slug
    # instead and sets none of them.
    subject: str | None = None
    grade: str | None = None
    unit: str | None = None
    row_key: str | None = None


# The Observation fields that map to `indicators` columns a consuming schema may
# or may not define. Order is the column order used in INSERTs; keep it stable.
OPTIONAL_COLUMNS = ("subject", "grade", "unit", "row_key")


# Run-level provenance columns a consuming `source_runs` table may or may not
# define, in INSERT order. Same optional-column contract as OPTIONAL_COLUMNS:
# named only when the caller supplies a value. 901economy's table has none of
# them; 901education's ledger records all six per run.
OPTIONAL_RUN_COLUMNS = (
    "script", "source_name", "source_url", "source_vintage", "fetched_at", "content_hash",
)


def record_run(
    conn,
    *,
    source_key: str,
    status: str = "success",
    row_count: int | None = None,
    review_artifact: dict | None = None,
    notes: str | None = None,
    script: str | None = None,
    source_name: str | None = None,
    source_url: str | None = None,
    source_vintage: str | None = None,
    fetched_at: str | None = None,
    content_hash: str | None = None,
) -> int:
    """Insert a source_runs row and return its run_id.

    `status='pending_review'` for a T3 extraction -- `append()` still attaches
    its rows to this run_id, but `indicators_current` won't surface them until
    a Review Queue approval flips this row to 'success' (see `approve_run`).

    The six trailing arguments are optional run-level provenance, mirroring
    what toolkit.observations records per run. A column is named only when its
    argument is supplied, so a `source_runs` table without them is unaffected.

    `fetched_at` should be the provider's own vintage (an HTTP Last-Modified,
    say), not "now" -- it is what lets a backfilled historical run keep its
    real date instead of the migration's, and what makes a later revision
    correctly supersede an earlier one.
    """
    supplied = {
        "script": script,
        "source_name": source_name,
        "source_url": source_url,
        "source_vintage": source_vintage,
        "fetched_at": fetched_at,
        "content_hash": content_hash,
    }
    extra = [name for name in OPTIONAL_RUN_COLUMNS if supplied[name] is not None]

    columns = ["source_key", "status", "row_count", "review_artifact", "notes"] + extra
    values = [
        source_key,
        status,
        row_count,
        psycopg2.extras.Json(review_artifact) if review_artifact else None,
        notes,
        *(supplied[name] for name in extra),
    ]
    placeholders = ", ".join(["%s"] * len(columns))
    with conn.cursor() as cur:
        cur.execute(
            f"INSERT INTO source_runs ({', '.join(columns)}) "
            f"VALUES ({placeholders}) RETURNING run_id",
            values,
        )
        run_id = cur.fetchone()[0]
    conn.commit()
    return run_id


def finish_run(conn, run_id: int, *, row_count: int | None = None) -> None:
    """Set a run's finished_at (and optionally row_count) once its append() calls are done."""
    with conn.cursor() as cur:
        cur.execute(
            "UPDATE source_runs SET finished_at = now(), "
            "row_count = COALESCE(%s, row_count) WHERE run_id = %s",
            (row_count, run_id),
        )
    conn.commit()


def append(
    conn,
    source_key: str,
    run_id: int,
    observations: Iterable[Observation],
    *,
    tier: str,
) -> int:
    """Batch-insert observations into `indicators`, tagged to the given run.

    Never rewrites existing rows -- a revision is a new row from a new run_id,
    exactly like toolkit.observations.append()'s NDJSON ledger.
    """
    observations = list(observations)
    if not observations:
        return 0

    # A column from OPTIONAL_COLUMNS is named only when some observation in
    # this batch actually sets it. That is what lets one store module serve
    # both an `indicators` table that has these columns (901education) and one
    # that does not (901economy's live table): a batch setting none of them
    # emits byte-for-byte the statement this function has always emitted.
    # Setting one against a table lacking the column is a hard error, which is
    # the correct outcome -- the value has nowhere to go.
    extra = [name for name in OPTIONAL_COLUMNS if any(getattr(obs, name) is not None for obs in observations)]
    columns = [
        "indicator_id", "geography_id", "period", "value", "demographic_group",
        "source_key", "source_url", "vintage", "tier", "suppressed", "run_id",
    ] + extra

    rows = [
        (
            obs.indicator_id,
            obs.geography_id,
            obs.period,
            obs.value,
            obs.demographic_group,
            source_key,
            obs.source_url,
            obs.vintage,
            tier,
            obs.suppressed,
            run_id,
            *(getattr(obs, name) for name in extra),
        )
        for obs in observations
    ]
    with conn.cursor() as cur:
        psycopg2.extras.execute_values(
            cur,
            f"INSERT INTO indicators ({', '.join(columns)}) VALUES %s",
            rows,
        )
    conn.commit()
    return len(rows)


def latest(
    conn,
    indicator_id: str,
    *,
    geography_id: str | None = None,
    period: str | None = None,
    demographic_group: str | None = None,
) -> list[dict]:
    """Query indicators_current, optionally narrowed by geography/period/group.

    Only returns rows from `success` runs -- unreviewed T3 extractions are
    invisible here by construction (the view enforces it, not this function).
    """
    clauses = ["indicator_id = %s"]
    params: list[object] = [indicator_id]
    if geography_id is not None:
        clauses.append("geography_id = %s")
        params.append(geography_id)
    if period is not None:
        clauses.append("period = %s")
        params.append(period)
    if demographic_group is not None:
        clauses.append("demographic_group = %s")
        params.append(demographic_group)
    sql = f"SELECT * FROM indicators_current WHERE {' AND '.join(clauses)} ORDER BY period"
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(sql, params)
        return [dict(row) for row in cur.fetchall()]


def compute_payload_hash(observations: Iterable[Observation]) -> str:
    """Deterministic hash of a set of observations, for `approvals.payload_hash` --
    lets a later, unnoticed change to an already-approved value be detected."""
    canonical = json.dumps([obs.__dict__ for obs in observations], sort_keys=True, default=str)
    return hashlib.sha256(canonical.encode()).hexdigest()


def approve_run(conn, run_id: int, *, reviewer: str, payload_hash: str) -> None:
    """Record an approval and flip the run to 'success' -- the single path to
    publication (PLAN.md §0.3 T3 gate). No GitHub PR is involved."""
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO approvals (run_id, decision, reviewer, payload_hash) "
            "VALUES (%s, 'approved', %s, %s)",
            (run_id, reviewer, payload_hash),
        )
        cur.execute("UPDATE source_runs SET status = 'success' WHERE run_id = %s", (run_id,))
    conn.commit()


def reject_run(conn, run_id: int, *, reviewer: str, reason: str, payload_hash: str) -> None:
    """Record a rejection and flip the run to 'rejected' -- its rows never
    reach `indicators_current`."""
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO approvals (run_id, decision, reviewer, reason, payload_hash) "
            "VALUES (%s, 'rejected', %s, %s, %s)",
            (run_id, reviewer, reason, payload_hash),
        )
        cur.execute("UPDATE source_runs SET status = 'rejected' WHERE run_id = %s", (run_id,))
    conn.commit()


def pending_reviews(conn) -> list[dict]:
    """List T3 runs awaiting review, for the /admin Review Queue page."""
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(
            """
            SELECT r.run_id, r.source_key, s.source_name, r.started_at, r.review_artifact
            FROM source_runs r
            JOIN sources s ON s.source_key = r.source_key
            WHERE r.status = 'pending_review'
            ORDER BY r.started_at
            """
        )
        return [dict(row) for row in cur.fetchall()]
