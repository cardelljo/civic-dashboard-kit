import json

from toolkit.eligibility import audit_all, is_publishable, load_meta, source_line


def write(data_dir, filename, meta, **extra):
    (data_dir / filename).write_text(json.dumps({"_meta": meta, **extra}))


def test_live_status_is_clean_publishable():
    verdict = is_publishable({"status": "live"}, value=2970)
    assert verdict.eligible
    assert verdict.caveats == []


def test_sample_status_is_blocked_even_with_a_value():
    verdict = is_publishable({"status": "sample"}, value=2970)
    assert not verdict.eligible
    assert "sample" in verdict.reason


def test_is_sample_flag_blocks_regardless_of_status():
    # A status can lag its own isSample flag; the flag wins.
    verdict = is_publishable({"status": "live", "isSample": True}, value=1)
    assert not verdict.eligible


def test_gap_status_is_blocked():
    verdict = is_publishable({"status": "gap"})
    assert not verdict.eligible


def test_suppressed_value_is_blocked_but_absent_value_is_not_checked():
    # Passing value=None (explicit suppression) blocks even a live status.
    assert not is_publishable({"status": "live"}, value=None).eligible
    # Not passing a value at all means "not checking a value" — only status matters.
    assert is_publishable({"status": "live"}).eligible


def test_caveat_statuses_publish_with_a_caveat_message():
    verdict = is_publishable({"status": "manual"}, value=5)
    assert verdict.eligible
    assert verdict.caveats and "manually collected" in verdict.caveats[0]


def test_unrecognized_status_fails_closed():
    verdict = is_publishable({"status": "unknown-status"})
    assert not verdict.eligible


def test_load_meta_missing_file_returns_empty_dict(tmp_path):
    assert load_meta(tmp_path, "missing.json") == {}


def test_load_meta_round_trips_the_meta_block(tmp_path):
    write(tmp_path, "jail.json", {"status": "live"})
    assert load_meta(tmp_path, "jail.json") == {"status": "live"}


def test_source_line_includes_name_period_and_url(tmp_path):
    (tmp_path / "jail.json").write_text(json.dumps({
        "source": "Shelby County Jail Report Card",
        "sourceUrl": "https://example.com/report",
        "dataThrough": "2026-07",
        "_meta": {"lastFetched": "2026-08-01T00:00:00"},
    }))
    line = source_line(tmp_path, "jail.json")
    assert "Shelby County Jail Report Card" in line
    assert "data through 2026-07" in line
    assert "retrieved 2026-08-01" in line
    assert line.endswith("https://example.com/report")


def test_source_line_missing_file(tmp_path):
    assert source_line(tmp_path, "missing.json") == "Source unavailable."


def test_audit_all_buckets_by_eligibility_and_skips_summary(tmp_path):
    write(tmp_path, "jail.json", {"status": "live"})
    write(tmp_path, "crime.json", {"status": "sample"})
    write(tmp_path, "summary.json", {"status": "live"})  # derived; excluded by default

    results = dict(audit_all(tmp_path))
    assert set(results) == {"jail.json", "crime.json"}
    assert results["jail.json"].eligible
    assert not results["crime.json"].eligible


def test_audit_all_skip_set_is_overridable(tmp_path):
    write(tmp_path, "summary.json", {"status": "live"})
    results = dict(audit_all(tmp_path, skip=set()))
    assert "summary.json" in results
