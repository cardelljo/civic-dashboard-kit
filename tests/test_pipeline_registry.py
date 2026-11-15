"""toolkit.pipeline.registry: reading each dashboard's pipeline.json. Offline."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from toolkit.pipeline.registry import (
    DEFAULT_TIMEOUT,
    RegistryError,
    UnknownDashboard,
    UnknownJob,
    load_dashboard,
    load_registry,
    parse_dashboard,
)

SRC = str(Path(__file__).resolve().parent.parent / "src")


def write(root: Path, config: dict) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    (root / "pipeline.json").write_text(json.dumps(config))
    return root


def justice_like(**overrides) -> dict:
    config = {
        "dashboard": "justice",
        "schema": "justice",
        "command_template": ["scripts/{job}.py"],
        "jobs": {
            "fetch_crime_data": {},
            "fetch_tract_context": {"timeout": 3600},
            "parse_jail_pdf": {"manual": True, "description": "no review gate yet"},
        },
        "seed": ["scripts/seed_foundation.py"],
        "migrations": "scripts.migrations:MIGRATIONS",
        "run_once": {"fetch_crime_data": {"token": "2026-11-15-first", "args": ["--from-dir", "data"]}},
    }
    config.update(overrides)
    return config


def test_template_jobs_explicit_commands_and_flags(tmp_path):
    d = load_dashboard(write(tmp_path, justice_like()))
    assert d.key == "justice" and d.schema == "justice" and d.root == tmp_path.resolve()
    assert d.job("fetch_crime_data").command == ("scripts/fetch_crime_data.py",)
    assert d.job("fetch_crime_data").timeout == DEFAULT_TIMEOUT
    assert d.job("fetch_tract_context").timeout == 3600
    assert d.job("parse_jail_pdf").manual and not d.job("fetch_crime_data").manual
    assert d.seed == ("scripts/seed_foundation.py",)
    assert d.run_once[0].job == "fetch_crime_data" and d.run_once[0].args == ("--from-dir", "data")


def test_both_existing_layouts_are_expressible(tmp_path):
    # education: scripts/<job>.py; economy: -m pipeline.<job>
    economy = parse_dashboard({"dashboard": "economy", "schema": "economy",
                               "command_template": ["-m", "pipeline.{job}"], "jobs": ["fetch_fred", "fetch_bds"]},
                              tmp_path)
    assert economy.job("fetch_fred").command == ("-m", "pipeline.fetch_fred")
    mixed = parse_dashboard({"dashboard": "x", "schema": "x", "jobs": {
        "a": "scripts/a.py", "b": ["-m", "pipeline.b", "--flag"], "c": {"command": ["scripts/c.py", "--all"]}}}, tmp_path)
    assert mixed.job("a").command == ("scripts/a.py",)
    assert mixed.job("b").command == ("-m", "pipeline.b", "--flag")
    assert mixed.job("c").script() == "scripts/c.py" and mixed.job("b").script() is None


def test_command_runs_with_the_dashboards_interpreter(tmp_path):
    d = load_dashboard(write(tmp_path, justice_like()))
    assert d.command("fetch_crime_data", ["--x"], env={}) == [sys.executable, "scripts/fetch_crime_data.py", "--x"]
    assert d.command("fetch_crime_data", env={"PIPELINE_PYTHON_JUSTICE": "/opt/j/bin/python"})[0] == "/opt/j/bin/python"
    venv = tmp_path / ".venv" / "bin"
    venv.mkdir(parents=True)
    (venv / "python").write_text("")
    assert d.python(env={}) == str(venv / "python")


def test_each_dashboard_gets_its_own_database(tmp_path):
    d = load_dashboard(write(tmp_path, justice_like()))
    env = {"DATABASE_URL": "postgresql://shared", "DATABASE_URL_JUSTICE": "postgresql://justice_app"}
    assert d.dsn(env) == "postgresql://justice_app"
    assert d.subprocess_env(env)["DATABASE_URL"] == "postgresql://justice_app"
    assert d.subprocess_env(env)["PIPELINE_DASHBOARD"] == "justice"
    assert d.dsn({"DATABASE_URL": "postgresql://shared"}) == "postgresql://shared"
    hyphen = parse_dashboard({"dashboard": "north-shore", "schema": "north_shore", "jobs": {"a": "a.py"}}, tmp_path)
    assert hyphen.dsn({"DATABASE_URL_NORTH_SHORE": "y"}) == "y"


def test_run_executes_in_the_checkout(tmp_path):
    root = write(tmp_path, {"dashboard": "t", "schema": "t", "jobs": {"where": "where.py"}})
    (root / "where.py").write_text("import os, sys; print(os.getcwd()); print(os.environ['DATABASE_URL']); "
                                   "print(sys.argv[1:])")
    d = load_dashboard(root)
    out = d.run_job("where", ["--a"], env={"DATABASE_URL_T": "dsn-t", "PATH": ""}).stdout.splitlines()
    assert out == [str(root.resolve()), "dsn-t", "['--a']"]


def test_unknowns_are_distinguishable(tmp_path):
    registry = load_registry([write(tmp_path / "j", justice_like())])
    with pytest.raises(UnknownDashboard):
        registry.get("transit")
    with pytest.raises(UnknownJob):
        registry.get("justice").job("fetch_nothing")


def test_registry_from_env_and_duplicate_keys(tmp_path):
    a = write(tmp_path / "a", justice_like())
    b = write(tmp_path / "b", justice_like(dashboard="economy", schema="economy"))
    registry = load_registry(env={"PIPELINE_DASHBOARDS": f"{a}:{b}"})
    assert [d.key for d in registry] == ["economy", "justice"]
    assert len(load_registry(env={"PIPELINE_DASHBOARDS": f"{a},{b}"})) == 2
    with pytest.raises(RegistryError, match="twice"):
        load_registry([a, write(tmp_path / "c", justice_like())])


def test_missing_scripts_reported_not_fatal(tmp_path):
    root = write(tmp_path, justice_like())
    (root / "scripts").mkdir()
    (root / "scripts" / "fetch_crime_data.py").write_text("")
    assert load_dashboard(root).missing_scripts() == ["fetch_tract_context", "parse_jail_pdf"]


@pytest.mark.parametrize("bad, match", [
    ({"dashboard": "Justice"}, "lowercase key"),
    ({"schema": "justice; drop"}, "schema"),
    ({"jobs": {}}, "at least one job"),
    ({"jobs": {"a/b": {}}}, "URL-safe"),
    ({"jobs": {"a": {"command": ["/usr/bin/python", "x.py"]}}}, "stay inside"),
    ({"jobs": {"a": {"command": ["../other/x.py"]}}}, "stay inside"),
    ({"jobs": {"a": {"command": ["--flag"]}}}, "script path or '-m'"),
    ({"jobs": {"a": {"timeout": 0}}}, "positive"),
    ({"jobs": {"a": {"manual": "yes"}}}, "true or false"),
    ({"jobs": {"a": {"shell": True}}}, "unknown job field"),
    ({"command_template": ["scripts/x.py"]}, "must contain"),
    ({"command_template": None, "jobs": {"a": {}}}, "no command"),
    ({"migrations": "scripts.migrations"}, "package.module:ATTRIBUTE"),
    ({"run_once": {"not_a_job": "t"}}, "not a registered job"),
    ({"run_once": {"fetch_crime_data": {"token": ""}}}, "token"),
    ({"extra": 1}, "unknown field"),
])
def test_malformed_configs_fail_loudly(tmp_path, bad, match):
    config = justice_like(**bad)
    if config.get("command_template") is None:
        config.pop("command_template")
    with pytest.raises(RegistryError, match=match):
        parse_dashboard(config, tmp_path)


def test_missing_or_broken_file(tmp_path):
    with pytest.raises(RegistryError, match="not found"):
        load_dashboard(tmp_path)
    (tmp_path / "pipeline.json").write_text("{nope")
    with pytest.raises(RegistryError, match="not valid JSON"):
        load_dashboard(tmp_path)


def test_registry_never_imports_a_web_framework_or_driver():
    # The n8n-agreement test in each dashboard imports this; `.[test]` installs neither.
    code = ("import sys, toolkit.pipeline.registry, toolkit.pipeline.migrate, toolkit.pipeline.post_deploy; "
            "bad = [m for m in ('fastapi', 'uvicorn', 'psycopg2', 'starlette') if m in sys.modules]; "
            "print(','.join(bad))")
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True,
                         env={"PYTHONPATH": SRC, "PATH": ""}, check=True).stdout.strip()
    assert out == ""
