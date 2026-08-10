"""
Data snapshot contract helpers: the `_meta` provenance block.

Implements the writer and validator side of DATA_SNAPSHOT_CONTRACT.md. Every
data/*.json the dashboard publishes carries a `_meta` block declaring where the
data came from, when, by which script, and whether it is live or sample data.
The frontend's DataStatusPanel and SampleBadge render directly off these fields,
so honesty about data status is enforced structurally, not by convention.

Usage (in a fetch script):
    from toolkit.snapshot import build_meta, validate_meta, validate_unique_ids

    data["_meta"] = build_meta(
        source_key="tdoe-tcap-district",
        source_name="TDOE TCAP Assessment File",
        script="scripts/fetch_tdoe_assessment.py",
        record_grain="district-year-subject-grade-group",
        how_to_update="Run: python3 scripts/fetch_tdoe_assessment.py",
        notes="Filtered to District 792 (MSCS) from the statewide file.",
        source_url="https://www.tn.gov/education/.../data-downloads.html",
    )
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

SCHEMA_VERSION = 1

#: The valid `_meta.status` values, and the Python half of the canonical
#: `DataStatus` union. The TypeScript half is `ui/types.ts`, and
#: `tests/test_data_status_union.py` fails if the two stop agreeing -- that
#: test is the mechanism docs/ARCHITECTURE.md §7 claims when it justifies
#: shipping both halves from one repo. Before it existed, `status` was an
#: unconstrained `str` here, so there was nothing for the TypeScript union to
#: drift *from*.
#:
#: Order matches ui/types.ts, which the union test relies on.
DATA_STATUSES = (
    "live",
    "mixed",
    "sample",
    "gap",
    "manual",
    "report-backed",
)


class SnapshotError(Exception):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SnapshotError(message)


def build_meta(
    source_key: str,
    source_name: str,
    script: str,
    record_grain: str,
    how_to_update: str,
    notes: str,
    source_url: str | None = None,
    is_sample: bool = False,
    status: str = "live",
    snapshot_ready: bool = True,
    fetched_at: str | None = None,
    tier: str | None = None,
    **extra_run_fields: Any,
) -> dict:
    """Build a contract-compliant _meta block. Timestamps default to now.

    `tier` is the automation-tier label ('T1' full API automation, 'T2'
    scheduled file pull, 'T3' AI-assisted extraction, 'T4' static one-time
    load -- see 901economy's PLAN.md §4) so the frontend can render a tier
    badge alongside the existing live/sample/gap status badge. Optional and
    additive: existing callers that don't pass it are unaffected, and
    `validate_meta` does not require it, so 901justice/901education's current
    data files stay contract-compliant without being touched.
    """
    require(status in DATA_STATUSES,
            f"unknown status {status!r}; expected one of {', '.join(DATA_STATUSES)}")
    fetched_at = fetched_at or datetime.now().isoformat(timespec="seconds")
    run: dict[str, Any] = {
        "sourceKey": source_key,
        "sourceName": source_name,
        "script": script,
        "fetchedAt": fetched_at,
        "recordGrain": record_grain,
        "snapshotReady": snapshot_ready,
    }
    if source_url:
        run["sourceUrl"] = source_url
    if tier:
        run["tier"] = tier
    run.update(extra_run_fields)
    return {
        "schemaVersion": SCHEMA_VERSION,
        "isSample": is_sample,
        "status": status,
        "lastFetched": fetched_at,
        "fetchedBy": script.split("/")[-1],
        "howToUpdate": how_to_update,
        "collectionRun": run,
        "notes": notes,
    }


def upsert_composite_source_meta(
    data: dict[str, Any],
    *,
    source_id: str,
    source_meta: dict[str, Any],
    composite_source_key: str,
    composite_source_name: str,
    composite_script: str,
    composite_record_grain: str,
    expected_sources: tuple[str, ...],
    how_to_update: str,
    notes: str,
) -> None:
    """Merge one verified source run into a multi-pipeline data file's metadata."""
    existing_meta = data.get("_meta") or {}
    source_runs = dict(existing_meta.get("sourceRuns") or {})
    source_runs[source_id] = source_meta["collectionRun"]

    fetched_values = [
        run.get("fetchedAt") for run in source_runs.values() if run.get("fetchedAt")
    ]
    latest_fetched = max(fetched_values)
    completed = set(source_runs)
    is_complete = set(expected_sources).issubset(completed)
    latest_school_year = max(
        (
            run.get("schoolYear")
            for run in source_runs.values()
            if run.get("schoolYear")
        ),
        default=None,
    )

    composite_meta = build_meta(
        source_key=composite_source_key,
        source_name=composite_source_name,
        script=composite_script,
        record_grain=composite_record_grain,
        how_to_update=how_to_update,
        notes=(
            notes
            + f" Verified source pipelines: {', '.join(sorted(completed))}."
            + ("" if is_complete else " Remaining fields retain their prior status until their dedicated pipelines run.")
        ),
        is_sample=False,
        status="live" if is_complete else "mixed",
        fetched_at=latest_fetched,
        schoolYear=latest_school_year,
    )
    composite_meta["sourceRuns"] = {
        key: source_runs[key] for key in sorted(source_runs)
    }
    data["_meta"] = composite_meta


def validate_meta(path: str, data: dict[str, Any], expected_source_key: str,
                  expected_grain: str, allow_sample: bool = False) -> None:
    """
    Validate a file's _meta block against the contract.

    allow_sample=True accepts scaffold-phase sample files (isSample true,
    status 'sample'); production validation should leave it False so sample
    data can never masquerade as a live snapshot.
    """
    meta = data.get("_meta") or {}
    run = meta.get("collectionRun") or {}

    require(meta.get("schemaVersion") == SCHEMA_VERSION,
            f"{path}: _meta.schemaVersion must be {SCHEMA_VERSION}")
    if not allow_sample:
        require(meta.get("isSample") is False,
                f"{path}: snapshot-ready source cannot be sample data")
        require(meta.get("status") == "live",
                f"{path}: snapshot-ready source must have live status")
    else:
        require(isinstance(meta.get("isSample"), bool),
                f"{path}: _meta.isSample must be a boolean")
        require(bool(meta.get("status")), f"{path}: missing _meta.status")
        # Membership, not just presence: a typo'd or invented status renders as
        # 'sample' in the frontend's fallback path, which is the one direction
        # this contract must never fail silently in.
        require(meta.get("status") in DATA_STATUSES,
                f"{path}: unknown _meta.status {meta.get('status')!r}; "
                f"expected one of {', '.join(DATA_STATUSES)}")
    require(bool(meta.get("lastFetched")), f"{path}: missing _meta.lastFetched")
    require(bool(meta.get("fetchedBy")), f"{path}: missing _meta.fetchedBy")
    require(bool(meta.get("howToUpdate")), f"{path}: missing _meta.howToUpdate")
    require(bool(meta.get("notes")), f"{path}: missing _meta.notes")
    require(run.get("snapshotReady") is True,
            f"{path}: collectionRun.snapshotReady must be true")
    require(run.get("sourceKey") == expected_source_key,
            f"{path}: unexpected collectionRun.sourceKey")
    require(run.get("recordGrain") == expected_grain,
            f"{path}: unexpected collectionRun.recordGrain")
    require(bool(run.get("script")), f"{path}: missing collectionRun.script")
    require(bool(run.get("fetchedAt")), f"{path}: missing collectionRun.fetchedAt")


def validate_unique_ids(path: str, rows: list[dict[str, Any]], prefix: str) -> None:
    """Rows that could become database records need stable, unique, prefixed IDs."""
    seen: set[str] = set()
    for index, row in enumerate(rows):
        row_id = row.get("id")
        require(isinstance(row_id, str) and bool(row_id),
                f"{path}: row {index} missing id")
        require(row_id.startswith(prefix),
                f"{path}: row {index} id has wrong prefix: {row_id}")
        require(row_id not in seen, f"{path}: duplicate row id: {row_id}")
        seen.add(row_id)


def load_json(root: Path, rel_path: str) -> dict[str, Any]:
    with open(root / rel_path) as fh:
        return json.load(fh)


def write_json(root: Path, rel_path: str, data: dict[str, Any]) -> None:
    target = root / rel_path
    target.parent.mkdir(parents=True, exist_ok=True)
    with open(target, "w") as fh:
        json.dump(data, fh, indent=2)
        fh.write("\n")
