"""toolkit.pipeline.post_deploy: the order of steps, what a failure stops (and what it
doesn't), and that a one-time job's token is recorded only on success.

The ordering tests fake the subprocess and need nothing; the token round trip needs
TOOLKIT_TEST_DATABASE_URL.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from urllib.parse import quote

import pytest

from toolkit.pipeline import post_deploy
from toolkit.pipeline.registry import RunOnce, load_registry

DATABASE_URL = os.environ.get("TOOLKIT_TEST_DATABASE_URL")


def dashboard_dir(tmp_path: Path, key: str, *, run_once=None, seed=True) -> Path:
    root = tmp_path / key
    root.mkdir()
    config = {"dashboard": key, "schema": key, "command_template": ["scripts/{job}.py"],
              "jobs": {"fetch_a": {}, "fetch_b": {}}}
    if seed:
        config["seed"] = ["scripts/seed_foundation.py"]
    if run_once:
        config["run_once"] = run_once
    (root / "pipeline.json").write_text(json.dumps(config))
    return root


class _Conn:
    def close(self):
        pass


@pytest.fixture
def fake(monkeypatch):
    """Records every command; fails any whose text contains a string in `failing`."""
    state = {"ran": [], "failing": set(), "recorded": [], "done": set()}

    def fake_run(dashboard, cmd, *, timeout):
        text = " ".join(cmd)
        state["ran"].append((dashboard.key, cmd[1:]))
        return not any(f in text for f in state["failing"]), f"out of {text}"

    monkeypatch.setattr(post_deploy, "_run", fake_run)
    monkeypatch.setattr(post_deploy, "open_db", lambda d: _Conn())
    monkeypatch.setattr(post_deploy, "done_tokens", lambda conn: set(state["done"]))
    monkeypatch.setattr(post_deploy, "record_token", lambda conn, job, token: state["recorded"].append((job, token)))
    return state


def test_seed_then_migrations_then_one_time_jobs(tmp_path, fake):
    root = dashboard_dir(tmp_path, "justice", run_once={"fetch_b": {"token": "t1", "args": ["--from-dir", "d"]}})
    assert post_deploy.main([], registry=load_registry([root])) == 0
    assert fake["ran"] == [
        ("justice", ["scripts/seed_foundation.py"]),
        ("justice", ["-m", "toolkit.pipeline.migrate", "--apply", "--root", str(root.resolve())]),
        ("justice", ["scripts/fetch_b.py", "--from-dir", "d"]),
    ]
    assert fake["recorded"] == [("fetch_b", "t1")]


def test_a_token_already_run_is_skipped_and_a_new_token_runs(tmp_path, fake):
    root = dashboard_dir(tmp_path, "justice", run_once={"fetch_a": "t2", "fetch_b": "t1"})
    fake["done"] = {("fetch_a", "t1"), ("fetch_b", "t1")}
    assert post_deploy.main([], registry=load_registry([root])) == 0
    assert [cmd for _, cmd in fake["ran"]][-1] == ["scripts/fetch_a.py"]
    assert fake["recorded"] == [("fetch_a", "t2")]


def test_a_failed_job_is_not_recorded_so_it_retries(tmp_path, fake):
    root = dashboard_dir(tmp_path, "justice", run_once={"fetch_a": "t1"})
    fake["failing"] = {"fetch_a"}
    assert post_deploy.main([], registry=load_registry([root])) == 1
    assert fake["recorded"] == []


@pytest.mark.parametrize("failing", ["seed_foundation", "toolkit.pipeline.migrate"])
def test_seed_or_migration_failure_stops_that_dashboard_only(tmp_path, fake, monkeypatch, failing):
    justice = dashboard_dir(tmp_path, "justice", run_once={"fetch_a": "t1"})
    economy = dashboard_dir(tmp_path, "economy", run_once={"fetch_a": "t1"})

    def fake_run(dashboard, cmd, *, timeout):  # the step fails for justice only
        fake["ran"].append((dashboard.key, cmd[1:]))
        return not (dashboard.key == "justice" and failing in " ".join(cmd)), "out"

    monkeypatch.setattr(post_deploy, "_run", fake_run)
    assert post_deploy.main([], registry=load_registry([justice, economy])) == 1
    justice_steps = [" ".join(cmd) for key, cmd in fake["ran"] if key == "justice"]
    assert not any("fetch_a" in step for step in justice_steps)
    if failing == "seed_foundation":
        assert len(justice_steps) == 1  # no migration after a failed seed
    economy_steps = [cmd for key, cmd in fake["ran"] if key == "economy"]
    assert economy_steps[-1] == ["scripts/fetch_a.py"]
    assert fake["recorded"] == [("fetch_a", "t1")]  # economy's, not justice's


def test_only_named_dashboards(tmp_path, fake):
    registry = load_registry([dashboard_dir(tmp_path, "justice"), dashboard_dir(tmp_path, "economy")])
    assert post_deploy.main(["--dashboard", "economy"], registry=registry) == 0
    assert {key for key, _ in fake["ran"]} == {"economy"}


def test_no_dashboards_is_a_failure_not_a_silent_pass(fake):
    assert post_deploy.main([], registry=load_registry([])) == 1


def test_due():
    once = (RunOnce("a", "t1"), RunOnce("b", "t1", ("--x",)))
    assert post_deploy.due(set(), once) == list(once)
    assert post_deploy.due({("a", "t1")}, once) == [once[1]]
    assert post_deploy.due({("a", "t0")}, (RunOnce("a", "t1"),)) == [RunOnce("a", "t1")]


@pytest.mark.skipif(not DATABASE_URL, reason="TOOLKIT_TEST_DATABASE_URL not set -- no Postgres available")
def test_tokens_round_trip_in_the_dashboards_schema(tmp_path, monkeypatch):
    import psycopg2

    admin = psycopg2.connect(DATABASE_URL)
    admin.autocommit = True
    with admin.cursor() as cur:
        cur.execute("DROP SCHEMA IF EXISTS pipetest_tok CASCADE; CREATE SCHEMA pipetest_tok")
    try:
        root = dashboard_dir(tmp_path, "pipetest_tok")
        dashboard = load_registry([root]).get("pipetest_tok")
        sep = "&" if "?" in DATABASE_URL else "?"
        monkeypatch.setenv("DATABASE_URL_PIPETEST_TOK", f"{DATABASE_URL}{sep}options={quote('-c search_path=pipetest_tok')}")
        conn = post_deploy.open_db(dashboard)
        try:
            assert post_deploy.done_tokens(conn) == set()
            post_deploy.record_token(conn, "fetch_a", "t1")
            post_deploy.record_token(conn, "fetch_a", "t1")
            assert post_deploy.done_tokens(conn) == {("fetch_a", "t1")}
        finally:
            conn.close()
        with admin.cursor() as cur:
            cur.execute("SELECT count(*) FROM pipetest_tok.post_deploy_runs")
            assert cur.fetchone()[0] == 1

        monkeypatch.setenv("DATABASE_URL_PIPETEST_TOK", DATABASE_URL)  # resolves to public, not its schema
        with pytest.raises(RuntimeError, match="refusing"):
            post_deploy.open_db(dashboard)
    finally:
        with admin.cursor() as cur:
            cur.execute("DROP SCHEMA IF EXISTS pipetest_tok CASCADE")
        admin.close()
