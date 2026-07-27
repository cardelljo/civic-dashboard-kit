"""
Append-only observations store: the source of truth ETL pipelines write to.

See docs/OBSERVATIONS_STORE_DESIGN.md for the full design and rationale. In
short: pipelines append `Observation` rows to a per-source NDJSON ledger under
data/observations/ (never rewritten — a re-fetch that revises a value just
appends a newer row; nothing is ever overwritten or deleted). `load()`
materializes every ledger into an in-memory sqlite3 database so callers get
real SQL without a runtime database server. `observations_current` is the
"latest known value per logical cell" view: it prefers the newest observation
for a given (metric, geography, period, group, subject, grade) while the
superseded rows remain in the ledger for audit.

This module has no knowledge of any dashboard's JSON shape. Scripts that
generate data/*.json read from `load()`/`latest()` and reshape the rows
themselves (see scripts/build_data_files.py).

Usage (in a fetch script, after computing the values it already writes to JSON):

    from toolkit.observations import Observation, record_run, append

    run_id = record_run(
        ROOT,
        source_key="tdoe-academic-outcomes",
        source_name="TDOE TCAP Assessment Files",
        script="scripts/fetch_tdoe_assessment.py",
        fetched_at=fetched_at,
        source_url=CURRENT_DISTRICT_URL,
        source_vintage=current_school_year,
    )
    append(ROOT, "tdoe-academic-outcomes", run_id, [
        Observation(metric_id="ela-proficiency", geography_id="792",
                    period="2025-26", value=23.8, subject="ela", grade="all-grades"),
        Observation(metric_id="ela-proficiency", geography_id="0",
                    period="2025-26", value=44.9, subject="ela", grade="all-grades"),
    ])
"""

from __future__ import annotations

import json
import sqlite3
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

OBSERVATIONS_DIR = "data/observations"
SOURCE_RUNS_FILE = "source_runs.ndjson"

SCHEMA = """
CREATE TABLE source_runs (
  run_id         TEXT PRIMARY KEY,
  source_key     TEXT NOT NULL,
  source_name    TEXT NOT NULL,
  script         TEXT NOT NULL,
  source_url     TEXT,
  source_vintage TEXT,
  fetched_at     TEXT NOT NULL,
  content_hash   TEXT,
  notes          TEXT
);

CREATE TABLE observations (
  obs_id        TEXT PRIMARY KEY,
  run_id        TEXT NOT NULL REFERENCES source_runs(run_id),
  metric_id     TEXT NOT NULL,
  geography_id  TEXT NOT NULL,
  period        TEXT NOT NULL,
  student_group TEXT NOT NULL DEFAULT 'all',
  subject       TEXT,
  grade         TEXT,
  value         REAL,
  suppressed    INTEGER NOT NULL DEFAULT 0,
  unit          TEXT,
  observed_at   TEXT NOT NULL,
  row_key       TEXT
);

CREATE INDEX idx_obs_cell   ON observations(metric_id, geography_id, period, student_group);
CREATE INDEX idx_obs_metric ON observations(metric_id);

CREATE VIEW observations_current AS
SELECT o.* FROM observations o
JOIN (
  SELECT metric_id, geography_id, period, student_group,
         COALESCE(subject,'') s, COALESCE(grade,'') g,
         MAX(observed_at) max_at
  FROM observations
  GROUP BY metric_id, geography_id, period, student_group, s, g
) latest
  ON  o.metric_id=latest.metric_id AND o.geography_id=latest.geography_id
  AND o.period=latest.period AND o.student_group=latest.student_group
  AND COALESCE(o.subject,'')=latest.s AND COALESCE(o.grade,'')=latest.g
  AND o.observed_at=latest.max_at;
"""


@dataclass(frozen=True)
class Observation:
    """One fact: a metric's value for a geography/period/group, as published.

    `suppressed=True` means the provider withheld the cell (e.g. TDOE's n<10
    or <1%/>99% rules) — `value` must be None in that case, never a guess.
    """

    metric_id: str
    geography_id: str
    period: str
    value: float | None
    student_group: str = "all"
    subject: str | None = None
    grade: str | None = None
    suppressed: bool = False
    unit: str | None = None
    row_key: str | None = None


def _obs_dir(root: Path) -> Path:
    directory = root / OBSERVATIONS_DIR
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def _append_line(path: Path, row: dict) -> None:
    with open(path, "a") as fh:
        fh.write(json.dumps(row, sort_keys=True))
        fh.write("\n")


def _read_ndjson(path: Path) -> list[dict]:
    if not path.exists():
        return []
    rows = []
    with open(path) as fh:
        for line in fh:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def record_run(
    root: Path,
    *,
    source_key: str,
    source_name: str,
    script: str,
    fetched_at: str,
    source_url: str | None = None,
    source_vintage: str | None = None,
    content_hash: str | None = None,
    notes: str | None = None,
) -> str:
    """Append a source_runs row (one per collection run) and return its run_id.

    `fetched_at` should be the real provider vintage (e.g. an HTTP
    Last-Modified header, ISO-8601), not "now" — this is what lets a later
    revision correctly supersede an earlier one in `observations_current`.
    """
    run_id = f"{source_key}@{fetched_at}"
    row = {
        "run_id": run_id,
        "source_key": source_key,
        "source_name": source_name,
        "script": script,
        "source_url": source_url,
        "source_vintage": source_vintage,
        "fetched_at": fetched_at,
        "content_hash": content_hash,
        "notes": notes,
        "recorded_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    _append_line(_obs_dir(root) / SOURCE_RUNS_FILE, row)
    return run_id


def append(root: Path, source_key: str, run_id: str, observations: Iterable[Observation]) -> int:
    """Append observations to the given source's ledger. Never rewrites existing lines."""
    path = _obs_dir(root) / f"{source_key}.ndjson"
    count = 0
    with open(path, "a") as fh:
        for obs in observations:
            row = asdict(obs)
            row["run_id"] = run_id
            row["obs_id"] = str(uuid.uuid4())
            fh.write(json.dumps(row, sort_keys=True))
            fh.write("\n")
            count += 1
    return count


def load(root: Path) -> sqlite3.Connection:
    """Materialize every NDJSON ledger under data/observations/ into an in-memory sqlite3 db."""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)

    obs_dir = root / OBSERVATIONS_DIR
    runs = _read_ndjson(obs_dir / SOURCE_RUNS_FILE)
    fetched_at_by_run = {r["run_id"]: r["fetched_at"] for r in runs}

    for run in runs:
        conn.execute(
            "INSERT OR REPLACE INTO source_runs "
            "(run_id, source_key, source_name, script, source_url, source_vintage, "
            " fetched_at, content_hash, notes) VALUES (?,?,?,?,?,?,?,?,?)",
            (
                run["run_id"], run["source_key"], run["source_name"], run["script"],
                run.get("source_url"), run.get("source_vintage"), run["fetched_at"],
                run.get("content_hash"), run.get("notes"),
            ),
        )

    if obs_dir.exists():
        for ndjson_path in sorted(obs_dir.glob("*.ndjson")):
            if ndjson_path.name == SOURCE_RUNS_FILE:
                continue
            for row in _read_ndjson(ndjson_path):
                # observed_at is denormalized from the owning run's fetched_at for
                # query convenience; it is never stored twice in the ledger itself.
                observed_at = fetched_at_by_run.get(row["run_id"])
                if observed_at is None:
                    raise ValueError(
                        f"{ndjson_path}: observation references unknown run_id {row['run_id']!r}"
                    )
                conn.execute(
                    "INSERT OR REPLACE INTO observations "
                    "(obs_id, run_id, metric_id, geography_id, period, student_group, "
                    " subject, grade, value, suppressed, unit, observed_at, row_key) "
                    "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (
                        row["obs_id"], row["run_id"], row["metric_id"], row["geography_id"],
                        row["period"], row.get("student_group", "all"), row.get("subject"),
                        row.get("grade"), row.get("value"), int(bool(row.get("suppressed"))),
                        row.get("unit"), observed_at, row.get("row_key"),
                    ),
                )
    conn.commit()
    return conn


def latest(
    conn: sqlite3.Connection,
    metric_id: str,
    *,
    geography_id: str | None = None,
    period: str | None = None,
    student_group: str | None = None,
    grade: str | None = None,
) -> list[sqlite3.Row]:
    """Query observations_current, optionally narrowed by geography/period/group/grade.

    `grade` matters whenever a metric_id is published at more than one grade
    aggregation (e.g. TDOE's grade-3-only ELA row vs. its grades-3-8 "All
    Grades" row are both `ela-proficiency`, distinguished only by `grade`).
    """
    clauses = ["metric_id = ?"]
    params: list[object] = [metric_id]
    if geography_id is not None:
        clauses.append("geography_id = ?")
        params.append(geography_id)
    if period is not None:
        clauses.append("period = ?")
        params.append(period)
    if student_group is not None:
        clauses.append("student_group = ?")
        params.append(student_group)
    if grade is not None:
        clauses.append("grade = ?")
        params.append(grade)
    sql = f"SELECT * FROM observations_current WHERE {' AND '.join(clauses)} ORDER BY period"
    return list(conn.execute(sql, params))
