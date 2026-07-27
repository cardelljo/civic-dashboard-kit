from toolkit.snapshot import build_meta, validate_meta


def test_snapshot_meta_is_contract_compliant():
    meta = build_meta("fixture", "Fixture", "scripts/fixture.py", "row", "Run fixture", "fixture note", fetched_at="2026-01-01T00:00:00")
    validate_meta("fixture.json", {"_meta": meta}, "fixture", "row")


def test_tier_is_optional_and_additive():
    # No tier passed: unaffected, still contract-compliant (existing callers
    # written before the tier field existed must keep working untouched).
    meta_without_tier = build_meta("fixture", "Fixture", "scripts/fixture.py", "row",
                                    "Run fixture", "fixture note", fetched_at="2026-01-01T00:00:00")
    assert "tier" not in meta_without_tier["collectionRun"]
    validate_meta("fixture.json", {"_meta": meta_without_tier}, "fixture", "row")

    # Tier passed: lands in collectionRun, still contract-compliant.
    meta_with_tier = build_meta("fixture", "Fixture", "scripts/fixture.py", "row",
                                 "Run fixture", "fixture note", fetched_at="2026-01-01T00:00:00",
                                 tier="T1")
    assert meta_with_tier["collectionRun"]["tier"] == "T1"
    validate_meta("fixture.json", {"_meta": meta_with_tier}, "fixture", "row")
