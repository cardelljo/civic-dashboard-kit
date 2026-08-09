"""
The two halves of this package must agree on `DataStatus`.

docs/ARCHITECTURE.md §7 justifies shipping a Python distribution and a
TypeScript package from one repo partly on the grounds that it keeps the
`DataStatus` union next to the Python that reasons about the same values. This
test is what makes that a mechanism rather than an intention: adding a status to
`ui/types.ts` without adding it to `snapshot.DATA_STATUSES` (or the reverse)
fails here, in the Python job, which runs on every PR.

It parses the TypeScript source as text rather than running `tsc`, so it works
in the Python job with no node toolchain installed -- the union is a flat list
of string literals, which regex reads reliably.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from toolkit.snapshot import DATA_STATUSES, SnapshotError, build_meta, validate_meta

TYPES_TS = Path(__file__).resolve().parent.parent / "ui" / "types.ts"


def _typescript_union() -> list[str]:
    """The string literals of `export type DataStatus = ...` in ui/types.ts."""
    source = TYPES_TS.read_text()
    match = re.search(
        r"export type DataStatus\s*=\s*(?P<body>[^;]+);", source, re.DOTALL
    )
    assert match, f"no `export type DataStatus` declaration in {TYPES_TS}"
    return re.findall(r"'([^']+)'", match.group("body"))


def test_types_ts_exists():
    """A missing ui/types.ts must fail loudly, not silently pass the test below."""
    assert TYPES_TS.is_file(), f"{TYPES_TS} is missing"


def test_python_and_typescript_unions_match_exactly():
    assert _typescript_union() == list(DATA_STATUSES)


def test_union_parse_finds_every_member():
    """Guard the regex itself: a parse that returned [] would make the
    comparison above vacuous if DATA_STATUSES were ever also emptied."""
    parsed = _typescript_union()
    assert len(parsed) == 6, parsed
    assert "report-backed" in parsed  # the one with a hyphen


def test_build_meta_rejects_an_unknown_status():
    with pytest.raises(SnapshotError, match="unknown status"):
        build_meta(
            source_key="k", source_name="n", script="s.py",
            record_grain="g", how_to_update="u", notes="x",
            status="livee",
        )


@pytest.mark.parametrize("status", DATA_STATUSES)
def test_build_meta_accepts_every_declared_status(status):
    meta = build_meta(
        source_key="k", source_name="n", script="s.py",
        record_grain="g", how_to_update="u", notes="x",
        status=status,
    )
    assert meta["status"] == status


def test_validate_meta_rejects_an_unknown_status_in_a_file():
    data = {
        "_meta": build_meta(
            source_key="k", source_name="n", script="s.py",
            record_grain="g", how_to_update="u", notes="x",
            is_sample=True, status="sample",
        )
    }
    data["_meta"]["status"] = "definitely-not-a-status"
    with pytest.raises(SnapshotError, match="unknown _meta.status"):
        validate_meta("f.json", data, "k", "g", allow_sample=True)
