#!/usr/bin/env python3
"""
Publication eligibility gate.

Encodes a guardrail every dashboard using this toolkit should apply before a
figure leaves the dashboard as a standalone persuasive claim:

    No sample, estimated, or unresolved-gap metric is packaged as a
    persuasive standalone claim.

Every comms artifact (brief, share card, social copy) should run each figure
through `is_publishable()` before quoting it. A metric that fails the gate is
not silently dropped from the dashboard — it stays visible there as a labeled
gap. It is only barred from being packaged as a standalone persuasive claim
outside the dashboard.

Status vocabulary matches the `DataStatus` union used by this toolkit's
frontend consumers:
    live | mixed | sample | gap | manual | report-backed

This module never assumes where a consuming repo keeps its data — pass your
own `data/` directory in.

Usage:
    from pathlib import Path
    from toolkit.eligibility import is_publishable, load_meta

    data_dir = Path("data")
    verdict = is_publishable(load_meta(data_dir, "jail.json"), value=2970)
    if verdict.eligible:
        ...
"""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# Statuses that may never be packaged as a standalone persuasive claim.
BLOCKED_STATUSES = {"sample", "gap"}

# Statuses that may be published but must carry a qualifying label in the artifact.
CAVEAT_STATUSES = {
    "mixed": "mixed-source data — state the sources and note comparability limits",
    "manual": "manually collected — state the collection date and method",
    "report-backed": "from a published report, not live data — state the report period",
}

# Statuses that publish cleanly with a normal source line.
CLEAN_STATUSES = {"live"}

# Distinguishes "no value passed" from "value is explicitly None (suppressed)".
_SENTINEL = object()


@dataclass
class Verdict:
    """Result of an eligibility check."""

    eligible: bool
    reason: str
    status: str | None = None
    caveats: list[str] = field(default_factory=list)

    def __bool__(self) -> bool:
        return self.eligible


def load_meta(data_dir: Path, filename: str) -> dict[str, Any]:
    """Load a data file's _meta block. Returns {} when the file is missing."""
    path = data_dir / filename
    if not path.exists():
        return {}
    with open(path) as fh:
        return json.load(fh).get("_meta", {}) or {}


def is_publishable(
    meta: dict[str, Any],
    value: Any = _SENTINEL,
    *,
    label: str = "metric",
) -> Verdict:
    """
    Decide whether a figure may be quoted in a public comms artifact.

    Rejects when the source is sample data, an unresolved gap, or when the value
    itself is absent (a suppression pattern: an unsourced value should render as
    suppressed, not filled in or rounded to zero).
    """
    status = meta.get("status")

    if meta.get("isSample") is True:
        return Verdict(False, f"{label}: source is sample/estimated data", status)

    if status in BLOCKED_STATUSES:
        return Verdict(False, f"{label}: source status is '{status}'", status)

    # An absent value is a suppressed value. Never fill it in or round it to zero.
    if value is not _SENTINEL and value is None:
        return Verdict(False, f"{label}: value is unsourced/suppressed", status)

    if status in CLEAN_STATUSES:
        return Verdict(True, f"{label}: publishable", status)

    if status in CAVEAT_STATUSES:
        return Verdict(True, f"{label}: publishable with caveat", status, [CAVEAT_STATUSES[status]])

    # Unknown status: fail closed rather than guess.
    return Verdict(False, f"{label}: unrecognized status {status!r}", status)


def source_line(data_dir: Path, filename: str) -> str:
    """Build a citation line for a data file from its own metadata."""
    path = data_dir / filename
    if not path.exists():
        return "Source unavailable."
    with open(path) as fh:
        data = json.load(fh)
    meta = data.get("_meta", {}) or {}
    run = meta.get("collectionRun", {}) or {}

    name = data.get("source") or run.get("sourceName") or filename
    url = data.get("sourceUrl") or run.get("sourceUrl")
    through = data.get("dataThrough") or data.get("reportMonth")
    fetched = (meta.get("lastFetched") or "")[:10]

    parts = [str(name)]
    if through:
        parts.append(f"data through {through}")
    if fetched:
        parts.append(f"retrieved {fetched}")
    line = "; ".join(parts)
    return f"{line}. {url}" if url else f"{line}."


def audit_all(data_dir: Path, *, skip: set[str] = frozenset({"summary.json"})) -> list[tuple[str, Verdict]]:
    """Run the gate over every data file in `data_dir`. Used by the CLI and by tests.

    `skip` excludes derived files whose parts are audited individually elsewhere
    (a dashboard's own summary.json, for example) — pass an empty set to include
    everything.
    """
    results = []
    for path in sorted(data_dir.glob("*.json")):
        if path.name in skip:
            continue
        results.append((path.name, is_publishable(load_meta(data_dir, path.name), label=path.name)))
    return results


def _main(argv: list[str]) -> None:
    data_dir = Path(argv[1]) if len(argv) > 1 else Path("data")
    print(f"Publication eligibility audit — {data_dir}\n")
    eligible, blocked = [], []
    for name, verdict in audit_all(data_dir):
        bucket = eligible if verdict.eligible else blocked
        bucket.append((name, verdict))

    print(f"Publishable ({len(eligible)}):")
    for name, v in eligible:
        note = f"  [caveat: {'; '.join(v.caveats)}]" if v.caveats else ""
        print(f"  PASS  {name:<28} status={v.status}{note}")

    print(f"\nNot publishable as standalone claims ({len(blocked)}):")
    for name, v in blocked:
        print(f"  BLOCK {name:<28} {v.reason}")
    print("\nBlocked sources remain visible on the dashboard as labeled gaps.")


if __name__ == "__main__":
    _main(sys.argv)
