"""toolkit.pipeline.runner: the HTTP contract n8n depends on.

Real subprocesses, tiny job scripts in a temporary checkout. Needs the `server`
extra plus httpx (FastAPI's TestClient); skips without them, and
tests/test_ci_guards.py fails CI if that happens there.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("httpx")

from fastapi.testclient import TestClient  # noqa: E402

from toolkit.pipeline import runner  # noqa: E402
from toolkit.pipeline.registry import load_registry  # noqa: E402


def checkout(tmp_path: Path, key: str = "justice", migrations: str | None = None) -> Path:
    root = tmp_path / key
    (root / "scripts").mkdir(parents=True)
    config = {"dashboard": key, "schema": key, "command_template": ["scripts/{job}.py"], "jobs": {
        "ok": {}, "boom": {}, "slow": {"timeout": 1},
        "parse_jail_pdf": {"manual": True, "description": "No review gate yet."}}}
    if migrations:
        config["migrations"] = migrations
    (root / "pipeline.json").write_text(json.dumps(config))
    (root / "scripts" / "ok.py").write_text(f"import os; print('{key} ok in', os.path.basename(os.getcwd()))")
    (root / "scripts" / "boom.py").write_text("import sys; print('partial'); sys.exit('fetch failed')")
    (root / "scripts" / "slow.py").write_text("import time; time.sleep(5)")
    (root / "scripts" / "parse_jail_pdf.py").write_text("print('ran')")
    return root


@pytest.fixture
def client(tmp_path):
    registry = load_registry([checkout(tmp_path, "justice"), checkout(tmp_path, "economy")])
    return TestClient(runner.create_app(registry, legacy_dashboard=""))


def test_runs_the_job_in_its_own_checkout(client):
    res = client.post("/run/justice/ok")
    assert res.status_code == 200
    assert res.json()["stdout"].strip() == "justice ok in justice"
    assert client.post("/run/economy/ok").json()["stdout"].strip() == "economy ok in economy"


def test_unknown_dashboard_and_unknown_job_are_distinguishable_404s(client):
    a = client.post("/run/transit/ok")
    b = client.post("/run/justice/nope")
    assert a.status_code == b.status_code == 404
    assert a.json()["detail"]["error"] == "unknown_dashboard"
    assert b.json()["detail"]["error"] == "unknown_job"


def test_a_failed_job_is_a_502_with_its_output(client):
    res = client.post("/run/justice/boom")
    assert res.status_code == 502
    detail = res.json()["detail"]
    assert detail["error"] == "job_failed" and "partial" in detail["stdout"] and "fetch failed" in detail["stderr"]


def test_a_job_past_its_timeout_is_a_504(client):
    res = client.post("/run/justice/slow")
    assert res.status_code == 504 and res.json()["detail"]["timeout"] == 1


def test_manual_jobs_never_run_over_http(client, tmp_path):
    res = client.post("/run/justice/parse_jail_pdf")
    assert res.status_code == 403
    assert res.json()["detail"]["error"] == "manual_only"
    assert "No review gate yet." in res.json()["detail"]["message"]


def test_pending_migration_refuses_with_409(client, monkeypatch):
    monkeypatch.setattr(runner, "migration_block", lambda d: "database migration pending for justice (x)")
    res = client.post("/run/justice/ok")
    assert res.status_code == 409 and res.json()["detail"]["error"] == "migration_pending"


def test_migration_check_runs_in_the_dashboards_process(tmp_path, monkeypatch):
    """With migrations declared and no database reachable, the guard refuses rather than guessing."""
    root = checkout(tmp_path, "justice", migrations="scripts.migrations:MIGRATIONS")
    (root / "scripts" / "__init__.py").write_text("")
    (root / "scripts" / "migrations.py").write_text("MIGRATIONS = []")
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("DATABASE_URL_JUSTICE", raising=False)
    monkeypatch.setenv("PYTHONPATH", str(Path(runner.__file__).resolve().parents[2]))
    blocked = runner.migration_block(load_registry([root]).get("justice"))
    assert blocked and "could not check" in blocked and "no database" in blocked


def test_no_migrations_declared_means_no_check(tmp_path):
    assert runner.migration_block(load_registry([checkout(tmp_path)]).get("justice")) is None


def test_legacy_route_only_when_configured(tmp_path):
    registry = load_registry([checkout(tmp_path, "economy")])
    off = TestClient(runner.create_app(registry, legacy_dashboard=""))
    assert off.post("/run/ok").status_code == 404
    on = TestClient(runner.create_app(registry, legacy_dashboard="economy"))
    assert on.post("/run/ok").json()["dashboard"] == "economy"
    assert on.post("/run/parse_jail_pdf").status_code == 403


def test_jobs_and_health(client):
    assert client.get("/healthz").json() == {"status": "ok", "dashboards": ["economy", "justice"]}
    jobs = client.get("/jobs").json()
    assert jobs["justice"]["parse_jail_pdf"]["manual"] is True and jobs["economy"]["ok"]["manual"] is False


def test_cli_runs_manual_jobs_by_hand(tmp_path, monkeypatch, capfd):
    root = checkout(tmp_path)
    monkeypatch.setenv("PIPELINE_DASHBOARDS", str(root))
    assert runner.main(["run", "justice", "parse_jail_pdf"]) == 0
    assert "ran" in capfd.readouterr().out
    assert runner.main(["run", "justice", "nope"]) == 1
    assert runner.main(["run", "justice", "boom"]) != 0
