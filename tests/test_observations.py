from toolkit.observations import Observation, append, latest, load, record_run


def test_append_and_load_round_trip(tmp_path):
    run_id = record_run(
        tmp_path, source_key="fixture", source_name="Fixture Source",
        script="scripts/fixture.py", fetched_at="2026-01-01T00:00:00+00:00",
    )
    append(tmp_path, "fixture", run_id, [
        Observation(metric_id="widget-count", geography_id="792", period="2024-25", value=10.0),
    ])
    rows = latest(load(tmp_path), "widget-count", geography_id="792")
    assert len(rows) == 1
    assert rows[0]["value"] == 10.0
    assert rows[0]["period"] == "2024-25"


def test_revision_supersedes_but_ledger_keeps_both(tmp_path):
    original_run = record_run(
        tmp_path, source_key="fixture", source_name="Fixture Source",
        script="scripts/fixture.py", fetched_at="2026-01-01T00:00:00+00:00",
    )
    append(tmp_path, "fixture", original_run, [
        Observation(metric_id="widget-count", geography_id="792", period="2024-25", value=10.0),
    ])
    revised_run = record_run(
        tmp_path, source_key="fixture", source_name="Fixture Source",
        script="scripts/fixture.py", fetched_at="2026-02-01T00:00:00+00:00",
    )
    append(tmp_path, "fixture", revised_run, [
        Observation(metric_id="widget-count", geography_id="792", period="2024-25", value=12.0),
    ])

    conn = load(tmp_path)
    current = latest(conn, "widget-count", geography_id="792", period="2024-25")
    assert len(current) == 1
    assert current[0]["value"] == 12.0  # the revision wins ...

    all_rows = conn.execute(
        "SELECT value FROM observations WHERE metric_id='widget-count' ORDER BY value"
    ).fetchall()
    assert [r["value"] for r in all_rows] == [10.0, 12.0]  # ... but nothing was deleted


def test_suppressed_value_stays_null_not_estimated(tmp_path):
    run_id = record_run(
        tmp_path, source_key="fixture", source_name="Fixture Source",
        script="scripts/fixture.py", fetched_at="2026-01-01T00:00:00+00:00",
    )
    append(tmp_path, "fixture", run_id, [
        Observation(metric_id="widget-count", geography_id="792", period="2024-25",
                    value=None, suppressed=True),
    ])
    rows = latest(load(tmp_path), "widget-count", geography_id="792")
    assert rows[0]["value"] is None
    assert bool(rows[0]["suppressed"]) is True


def test_metric_absent_from_a_later_run_still_returns_its_retained_history(tmp_path):
    """A provider dropping a metric in a new release must not erase its prior history."""
    run_2024 = record_run(
        tmp_path, source_key="fixture", source_name="Fixture Source",
        script="scripts/fixture.py", fetched_at="2026-01-01T00:00:00+00:00",
    )
    append(tmp_path, "fixture", run_2024, [
        Observation(metric_id="widget-count", geography_id="792", period="2023-24", value=8.0),
        Observation(metric_id="retired-metric", geography_id="792", period="2023-24", value=99.0),
    ])
    run_2025 = record_run(
        tmp_path, source_key="fixture", source_name="Fixture Source",
        script="scripts/fixture.py", fetched_at="2027-01-01T00:00:00+00:00",
    )
    # The provider's new release no longer publishes "retired-metric" at all.
    append(tmp_path, "fixture", run_2025, [
        Observation(metric_id="widget-count", geography_id="792", period="2024-25", value=9.0),
    ])

    conn = load(tmp_path)
    assert len(latest(conn, "widget-count", geography_id="792")) == 2  # both periods retained
    retired = latest(conn, "retired-metric", geography_id="792")
    assert len(retired) == 1 and retired[0]["value"] == 99.0  # still queryable, not lost
