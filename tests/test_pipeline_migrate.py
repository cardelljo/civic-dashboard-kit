"""toolkit.pipeline.migrate against a real Postgres: rehearse, apply once, record,
restore, refuse the wrong schema, and the --check exit code the runner relies on.

Each test gets two fresh schemas standing in for two dashboards on the shared
instance, reached the way production reaches them: a connection whose search_path
starts with that dashboard's schema.
"""

from __future__ import annotations

import itertools
import json
import os
import subprocess
import sys
from pathlib import Path
from urllib.parse import quote

import pytest

from toolkit.pipeline import migrate
from toolkit.pipeline.migrate import Migration
from toolkit.pipeline.registry import load_dashboard

DATABASE_URL = os.environ.get("TOOLKIT_TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(not DATABASE_URL, reason="TOOLKIT_TEST_DATABASE_URL not set -- no Postgres available")

SRC = str(Path(__file__).resolve().parent.parent / "src")
_names = itertools.count()


def dsn_for(schema: str) -> str:
    sep = "&" if "?" in DATABASE_URL else "?"
    return f"{DATABASE_URL}{sep}options={quote(f'-c search_path={schema}')}"


@pytest.fixture
def schemas():
    import psycopg2

    conn = psycopg2.connect(DATABASE_URL)
    conn.autocommit = True
    with conn.cursor() as cur:
        for schema in ("pipetest_a", "pipetest_b"):
            cur.execute(f"DROP SCHEMA IF EXISTS {schema} CASCADE; CREATE SCHEMA {schema}")
    yield
    with conn.cursor() as cur:
        cur.execute("DROP SCHEMA IF EXISTS pipetest_a CASCADE; DROP SCHEMA IF EXISTS pipetest_b CASCADE")
    conn.close()


@pytest.fixture
def conn(schemas):
    connection = migrate.connect(dsn_for("pipetest_a"))
    yield connection
    connection.close()


# --------------------------------------------------------------------------- sample migrations

def _add_widgets(conn, *, log, backup_prefix):
    with conn.cursor() as cur:
        cur.execute("SELECT to_regclass('widgets')")
        if cur.fetchone()[0] is not None:
            return {"applied": False}
        cur.execute("CREATE TABLE widgets (id INT PRIMARY KEY, name TEXT)")
        cur.execute("INSERT INTO widgets VALUES (1, 'one'), (2, 'two')")
    return {"applied": True, "rows": 2}


def _rename_widgets(conn, *, log, backup_prefix):
    with conn.cursor() as cur:
        cur.execute(f"CREATE TABLE {backup_prefix}_widgets AS SELECT * FROM widgets")
        cur.execute("UPDATE widgets SET name = upper(name)")
        cur.execute("SELECT count(*) FROM widgets WHERE name <> upper(name)")
        if cur.fetchone()[0]:
            raise RuntimeError("check failed: a name is still lower case")
    return {"applied": True}


def _rename_widgets_restore(conn, *, log, backup_prefix):
    with conn.cursor() as cur:
        cur.execute(f"UPDATE widgets w SET name = b.name FROM {backup_prefix}_widgets b WHERE b.id = w.id")
        cur.execute(f"DROP TABLE {backup_prefix}_widgets")
    return {}


def _always_fails(conn, *, log, backup_prefix):
    with conn.cursor() as cur:
        cur.execute("CREATE TABLE half_done (x INT)")
    raise RuntimeError("check failed: totals do not match")


ADD = Migration("2026-11-01-widgets", "add widgets", _add_widgets)
RENAME = Migration("2026-11-02-upper", "upper-case names", _rename_widgets, _rename_widgets_restore)
FAILS = Migration("2026-11-03-broken", "fails its check", _always_fails)


def tables(conn) -> set[str]:
    with conn.cursor() as cur:
        cur.execute("SELECT tablename FROM pg_tables WHERE schemaname = current_schema()")
        names = {row[0] for row in cur.fetchall()}
    conn.rollback()
    return names


def names(conn) -> list[str]:
    with conn.cursor() as cur:
        cur.execute("SELECT name FROM widgets ORDER BY id")
        rows = [row[0] for row in cur.fetchall()]
    conn.rollback()
    return rows


# --------------------------------------------------------------------------- the engine

def test_rehearsal_changes_nothing(conn):
    log = []
    assert migrate.run(conn, [ADD, RENAME], dashboard="a", apply=False, log=log.append)
    assert tables(conn) == set()  # not even schema_migrations
    assert any("not rehearsed" in line and RENAME.id in line for line in log)


def test_apply_records_and_rerun_is_a_noop(conn):
    assert migrate.run(conn, [ADD, RENAME], dashboard="a", apply=True, log=lambda _: None)
    assert names(conn) == ["ONE", "TWO"]
    assert migrate.applied_ids(conn) == {ADD.id, RENAME.id}
    log = []
    assert migrate.run(conn, [ADD, RENAME], dashboard="a", apply=True, log=log.append)
    assert log == ["no pending migrations"]
    with conn.cursor() as cur:
        cur.execute("SELECT id, backup_prefix, report FROM schema_migrations ORDER BY id")
        rows = cur.fetchall()
    conn.rollback()
    assert rows[0][1] == ADD.backup_prefix and rows[0][2]["rows"] == 2


def test_a_failed_check_rolls_everything_back(conn):
    log = []
    assert not migrate.run(conn, [ADD, FAILS], dashboard="a", apply=True, log=log.append)
    assert ADD.id in migrate.applied_ids(conn)  # the one before it committed on its own
    assert FAILS.id not in migrate.applied_ids(conn)
    assert "half_done" not in tables(conn)
    assert any(line.startswith(f"FAILED {FAILS.id}") for line in log)


def test_nothing_to_change_is_recorded_without_a_backup(conn):
    with conn.cursor() as cur:
        cur.execute("CREATE TABLE widgets (id INT PRIMARY KEY, name TEXT)")  # fresh database, new shape
    conn.commit()
    assert migrate.run(conn, [ADD], dashboard="a", apply=True, log=lambda _: None)
    with conn.cursor() as cur:
        cur.execute("SELECT backup_prefix FROM schema_migrations")
        assert cur.fetchone()[0] is None
    conn.rollback()
    assert not migrate.restore(conn, ADD.id, [ADD], dashboard="a", log=lambda _: None)


def test_restore_undoes_one_and_makes_it_pending_again(conn):
    migrate.run(conn, [ADD, RENAME], dashboard="a", apply=True, log=lambda _: None)
    assert migrate.restore(conn, RENAME.id, [ADD, RENAME], dashboard="a", log=lambda _: None)
    assert names(conn) == ["one", "two"]
    assert [m.id for m in migrate.pending(conn, [ADD, RENAME])] == [RENAME.id]
    conn.rollback()
    assert not migrate.restore(conn, RENAME.id, [ADD, RENAME], dashboard="a", log=lambda _: None)  # not applied now
    assert not migrate.restore(conn, ADD.id, [ADD], dashboard="a", log=lambda _: None)  # no restore function


def test_duplicate_ids_are_refused(conn):
    with pytest.raises(ValueError, match="duplicate"):
        migrate.run(conn, [ADD, Migration(ADD.id, "again", _add_widgets)], dashboard="a", apply=True)


def test_dashboards_do_not_share_a_lock(schemas):
    """Holding dashboard a's lock must not block dashboard b's migration."""
    a = migrate.connect(dsn_for("pipetest_a"))
    b = migrate.connect(dsn_for("pipetest_b"))
    try:
        with a.cursor() as cur:
            migrate._lock(cur, "a")  # held until a's transaction ends
        with b.cursor() as cur:
            cur.execute("SET lock_timeout = '2s'")
        b.commit()
        assert migrate.run(b, [ADD], dashboard="b", apply=True, log=lambda _: None)
        assert "widgets" in tables(b)
    finally:
        a.rollback()
        a.close()
        b.close()


# --------------------------------------------------------------------------- the CLI

def checkout(tmp_path: Path, migrations: list[str], schema: str = "pipetest_a") -> Path:
    """A dashboard checkout whose migrations module re-exports this file's samples."""
    module = f"tmig_{next(_names)}"
    (tmp_path / "pipeline.json").write_text(json.dumps({
        "dashboard": "a", "schema": schema, "jobs": {"noop": "noop.py"}, "migrations": f"{module}:MIGRATIONS"}))
    (tmp_path / f"{module}.py").write_text(
        "import sys\n"
        f"sys.path.insert(0, {str(Path(__file__).resolve().parent)!r})\n"
        "import test_pipeline_migrate as t\n"
        f"MIGRATIONS = [{', '.join('t.' + m for m in migrations)}]\n")
    return tmp_path


def test_cli_check_status_apply(tmp_path, conn, capsys):
    root = checkout(tmp_path, ["ADD", "RENAME"])
    dsn = dsn_for("pipetest_a")
    assert migrate.main(["--check", "--root", str(root), "--dsn", dsn]) == migrate.EXIT_PENDING
    assert migrate.main(["--root", str(root), "--dsn", dsn]) == 0  # rehearsal
    assert tables(conn) == set()
    assert migrate.main(["--apply", "--root", str(root), "--dsn", dsn]) == 0
    assert migrate.main(["--check", "--root", str(root), "--dsn", dsn]) == 0
    assert migrate.main(["--status", "--root", str(root), "--dsn", dsn]) == 0
    assert f"applied  {RENAME.id}" in capsys.readouterr().out


def test_cli_refuses_another_dashboards_schema(tmp_path, schemas, capsys):
    root = checkout(tmp_path, ["ADD"], schema="pipetest_a")
    assert migrate.main(["--apply", "--root", str(root), "--dsn", dsn_for("pipetest_b")]) == migrate.EXIT_WRONG_SCHEMA
    assert "not 'pipetest_a'" in capsys.readouterr().out
    check = migrate.connect(dsn_for("pipetest_b"))
    try:
        assert tables(check) == set()
    finally:
        check.close()


def test_cli_with_no_migrations_declared(tmp_path, schemas):
    (tmp_path / "pipeline.json").write_text(json.dumps({"dashboard": "a", "schema": "pipetest_a",
                                                        "jobs": {"noop": "noop.py"}}))
    assert migrate.main(["--check", "--root", str(tmp_path), "--dsn", dsn_for("pipetest_a")]) == 0


def test_cli_reads_the_dashboards_own_database_variable(tmp_path, schemas):
    """As a subprocess, the way post_deploy and the runner call it."""
    root = checkout(tmp_path, ["ADD"])
    env = {"PYTHONPATH": SRC, "PATH": os.environ.get("PATH", ""), "DATABASE_URL_A": dsn_for("pipetest_a"),
           "DATABASE_URL": dsn_for("pipetest_b")}
    result = subprocess.run([sys.executable, "-m", "toolkit.pipeline.migrate", "--check", "--root", str(root)],
                            env=env, capture_output=True, text=True)
    assert result.returncode == migrate.EXIT_PENDING, result.stdout + result.stderr
    assert load_dashboard(root).dsn(env) == dsn_for("pipetest_a")
