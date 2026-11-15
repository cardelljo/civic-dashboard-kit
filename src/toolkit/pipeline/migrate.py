"""Database migrations for one dashboard: one command, safe to rerun.

Promoted from 901education's `pipeline/migrate.py` (its Nashville school-key change,
2026-11) so every dashboard gets the same guarantees instead of its own copy. Run it
from the dashboard's checkout, where `pipeline.json` says which schema to expect and
where its migrations live:

    python3 -m toolkit.pipeline.migrate            # status + full rehearsal, then ROLL BACK
    python3 -m toolkit.pipeline.migrate --apply    # apply every pending migration
    python3 -m toolkit.pipeline.migrate --status   # list applied / pending
    python3 -m toolkit.pipeline.migrate --check    # exit 3 if anything is pending (the runner's guard)
    python3 -m toolkit.pipeline.migrate --restore 2026-11-11-school-keys

`--root DIR` points at another checkout; `--dsn` overrides the database (default:
`DATABASE_URL_<KEY>`, else `DATABASE_URL`). Every mode first checks that the
connection resolves to the dashboard's own schema and refuses (exit 2) otherwise, so
one dashboard's migration can never land in another's tables on the shared instance.

How each migration is applied, unchanged from education's:

- The rehearsal (the default) does everything `--apply` does, every check included,
  then rolls back. If the rehearsal passes, `--apply` will pass on the same data.
- `--apply` takes a transaction-scoped advisory lock (two runs for the same dashboard
  cannot overlap; different dashboards do not block each other), runs the migration,
  and records it in `schema_migrations`, all in ONE transaction. Any failed check rolls
  all of it back.
- A migration already recorded is skipped, so rerunning is a no-op. A migration that
  finds nothing to do (a fresh database built by the new code) is recorded as applied.

Writing a migration: a function `(conn, *, log, backup_prefix) -> dict` that neither
commits nor rolls back, raises on any failed check, is a no-op on a database already in
the new shape, and returns `{"applied": True, ...}` when it changed something (then
`backup_prefix` names where it copied what it changed, for `restore`). Add a
`Migration` to the list `pipeline.json`'s `migrations` names; ids sort by date and a
shipped id is never renumbered. Idempotent schema changes (`CREATE ... IF NOT EXISTS`,
`ADD COLUMN IF NOT EXISTS`) belong in the dashboard's `db/schema.sql` instead, which
its seed step applies on every deploy.

The `schema_migrations` table is education's, column for column, so a dashboard that
already has one keeps its history when it moves to this module.
"""

from __future__ import annotations

import argparse
import importlib
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from toolkit.pipeline.registry import Dashboard, RegistryError, env_suffix, load_dashboard

EXIT_FAILED = 1
EXIT_WRONG_SCHEMA = 2
EXIT_PENDING = 3

TABLE_SQL = """CREATE TABLE IF NOT EXISTS schema_migrations (
    id          TEXT PRIMARY KEY,
    summary     TEXT NOT NULL,
    applied_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    report      JSONB,
    backup_prefix TEXT
)"""


@dataclass(frozen=True)
class Migration:
    id: str
    summary: str
    run: Callable[..., dict]
    restore: Callable[..., dict] | None = None

    @property
    def backup_prefix(self) -> str:
        # A Postgres identifier: premig_2026_11_11_school_keys
        return "premig_" + re.sub(r"[^a-z0-9]+", "_", self.id.lower())


def _lock(cur, dashboard: str) -> None:
    # Keyed by dashboard: one shared instance, so a fixed key would make every
    # dashboard's deploy wait on every other's.
    cur.execute("SELECT pg_advisory_xact_lock(hashtext(%s))", (f"toolkit.pipeline.migrate:{dashboard}",))


# --------------------------------------------------------------------------- bookkeeping

def applied_ids(conn) -> set[str]:
    """Read-only: never creates the table, so a status check or the runner guard writes nothing."""
    with conn.cursor() as cur:
        cur.execute("SELECT to_regclass('schema_migrations')")
        if cur.fetchone()[0] is None:
            return set()
        cur.execute("SELECT id FROM schema_migrations")
        return {row[0] for row in cur.fetchall()}


def pending(conn, migrations: list[Migration]) -> list[Migration]:
    done = applied_ids(conn)
    return [m for m in sorted(migrations, key=lambda m: m.id) if m.id not in done]


def check_unique(migrations: list[Migration]) -> None:
    ids = [m.id for m in migrations]
    dupes = sorted({i for i in ids if ids.count(i) > 1})
    if dupes:
        raise ValueError(f"duplicate migration id(s): {', '.join(dupes)}")


def describe_target(conn) -> str:
    dsn = conn.get_dsn_parameters()
    return f"database {dsn.get('dbname')!r} on {dsn.get('host')}:{dsn.get('port')} as {dsn.get('user')!r}"


def _run_one(conn, migration: Migration, *, dashboard: str, log) -> dict:
    """Inside the caller's transaction: lock, re-check it is still pending, run, record."""
    with conn.cursor() as cur:
        _lock(cur, dashboard)
        cur.execute(TABLE_SQL)
        cur.execute("SELECT 1 FROM schema_migrations WHERE id = %s", (migration.id,))
        if cur.fetchone():
            log(f"{migration.id}: already applied by another run; skipping")
            return {"skipped": True}
    report = migration.run(conn, log=log, backup_prefix=migration.backup_prefix) or {}
    with conn.cursor() as cur:
        cur.execute("INSERT INTO schema_migrations (id, summary, report, backup_prefix) VALUES (%s, %s, %s, %s)",
                    (migration.id, migration.summary, json.dumps(report, default=str),
                     migration.backup_prefix if report.get("applied") else None))
    return report


def run(conn, migrations: list[Migration], *, dashboard: str, apply: bool, log=print) -> bool:
    """Rehearse (apply=False) or apply every pending migration. Returns True if all passed."""
    check_unique(migrations)
    todo = pending(conn, migrations)
    conn.rollback()  # end the read transaction pending() opened
    if not todo:
        log("no pending migrations")
        return True
    for migration in todo:
        if apply:
            log(f"applying {migration.id}: {migration.summary}")
        else:
            log(f"rehearsing {migration.id} (everything below is rolled back at the end): {migration.summary}")
        try:
            report = _run_one(conn, migration, dashboard=dashboard, log=log)
        except Exception as exc:  # noqa: BLE001 -- any failure rolls back and stops
            conn.rollback()
            log(f"FAILED {migration.id} (rolled back, nothing changed): {exc}")
            return False
        if apply:
            conn.commit()
            log(f"applied {migration.id}" + (f"; backup copy in {migration.backup_prefix}_*" if report.get("applied") else
                                             " (nothing to change; recorded as applied)"))
        else:
            conn.rollback()
            log(f"rehearsal of {migration.id} passed every check; rolled back, nothing changed")
            # Later migrations may depend on this one, so a rehearsal stops at the first.
            remaining = todo[todo.index(migration) + 1:]
            if remaining:
                log(f"not rehearsed (they build on {migration.id}): {', '.join(m.id for m in remaining)}")
            break
    if not apply:
        log("to apply: python3 -m toolkit.pipeline.migrate --apply")
    return True


def restore(conn, migration_id: str, migrations: list[Migration], *, dashboard: str, log=print) -> bool:
    by_id = {m.id: m for m in migrations}
    if migration_id not in by_id:
        log(f"unknown migration {migration_id!r}; known: {', '.join(sorted(by_id)) or 'none'}")
        return False
    migration = by_id[migration_id]
    if migration.restore is None:
        log(f"{migration_id} has no in-place restore; use the database backup")
        return False
    try:
        with conn.cursor() as cur:
            _lock(cur, dashboard)
            cur.execute("SELECT to_regclass('schema_migrations')")
            recorded = None
            if cur.fetchone()[0] is not None:
                cur.execute("SELECT backup_prefix FROM schema_migrations WHERE id = %s", (migration_id,))
                recorded = cur.fetchone()
        if recorded is None:
            raise RuntimeError(f"{migration_id} is not recorded as applied; nothing to restore")
        if recorded[0] is None:
            raise RuntimeError(f"{migration_id} changed nothing when it was applied, so there is nothing to restore")
        migration.restore(conn, log=log, backup_prefix=recorded[0])
        with conn.cursor() as cur:
            cur.execute("DELETE FROM schema_migrations WHERE id = %s", (migration_id,))
        conn.commit()
    except Exception as exc:  # noqa: BLE001
        conn.rollback()
        log(f"RESTORE FAILED (rolled back, nothing changed): {exc}")
        return False
    log(f"restored {migration_id}; it is pending again, so pipeline jobs will refuse to run until it is "
        "re-applied or the previous code is deployed")
    return True


def status(conn, migrations: list[Migration], *, log=print) -> None:
    done = applied_ids(conn)
    conn.rollback()
    if not migrations:
        log("  (no migrations declared)")
    for m in sorted(migrations, key=lambda m: m.id):
        log(f"  {'applied' if m.id in done else 'PENDING'}  {m.id}  {m.summary}")


# --------------------------------------------------------------------------- loading

def load_migrations(dashboard: Dashboard) -> list[Migration]:
    """Import the list `pipeline.json` names, with the checkout on sys.path. Runs inside
    the dashboard's own process (its cwd, its interpreter), never the runner's."""
    if not dashboard.migrations:
        return []
    module_name, attr = dashboard.migrations.split(":")
    root = str(dashboard.root)
    if root not in sys.path:
        sys.path.insert(0, root)
    migrations = getattr(importlib.import_module(module_name), attr)
    if not all(isinstance(m, Migration) for m in migrations):
        raise RegistryError(f"{dashboard.migrations} must be a list of toolkit.pipeline.migrate.Migration")
    check_unique(list(migrations))
    return list(migrations)


def connect(dsn: str):
    import psycopg2  # the postgres extra; imported here so --help works without it

    conn = psycopg2.connect(dsn)
    conn.set_client_encoding("UTF8")
    return conn


def current_schema(conn) -> str | None:
    with conn.cursor() as cur:
        cur.execute("SELECT current_schema()")
        value = cur.fetchone()[0]
    conn.rollback()
    return value


def schema_problem(conn, dashboard: Dashboard) -> str | None:
    found = current_schema(conn)
    if found != dashboard.schema:
        return (f"connection resolves to schema {found!r}, not {dashboard.schema!r}; refusing to touch it. "
                f"Use {dashboard.key}'s own role (its search_path starts with {dashboard.schema}) "
                f"via DATABASE_URL_{env_suffix(dashboard.key)} or --dsn.")
    return None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--apply", action="store_true", help="apply pending migrations (default: rehearse and roll back)")
    mode.add_argument("--status", action="store_true", help="list applied and pending migrations only")
    mode.add_argument("--check", action="store_true", help=f"exit {EXIT_PENDING} if any migration is pending")
    mode.add_argument("--restore", metavar="ID", help="undo one applied migration from its backup copy")
    parser.add_argument("--root", default=".", help="the dashboard checkout (default: the current directory)")
    parser.add_argument("--dsn", help="Postgres DSN (default: DATABASE_URL_<KEY>, else DATABASE_URL)")
    args = parser.parse_args(argv)
    log = lambda line: print(line, flush=True)  # noqa: E731

    try:
        dashboard = load_dashboard(Path(args.root))
        migrations = load_migrations(dashboard)
    except Exception as exc:  # noqa: BLE001
        log(f"could not load migrations: {exc}")
        return EXIT_FAILED
    dsn = args.dsn or dashboard.dsn()
    if not dsn:
        log(f"no database: set DATABASE_URL_{env_suffix(dashboard.key)} or DATABASE_URL, or pass --dsn")
        return EXIT_FAILED

    conn = connect(dsn)
    try:
        log(f"{dashboard.key}: connected to {describe_target(conn)}")
        problem = schema_problem(conn, dashboard)
        if problem:
            log(problem)
            return EXIT_WRONG_SCHEMA
        if args.check:
            ids = [m.id for m in pending(conn, migrations)]
            conn.rollback()
            if ids:
                log(f"pending: {', '.join(ids)}")
                return EXIT_PENDING
            log("no pending migrations")
            return 0
        if args.status:
            status(conn, migrations, log=log)
            return 0
        if args.restore:
            return 0 if restore(conn, args.restore, migrations, dashboard=dashboard.key, log=log) else EXIT_FAILED
        status(conn, migrations, log=log)
        return 0 if run(conn, migrations, dashboard=dashboard.key, apply=args.apply, log=log) else EXIT_FAILED
    finally:
        conn.close()


if __name__ == "__main__":
    # Run the imported module, not this __main__ copy, so a dashboard's
    # `from toolkit.pipeline.migrate import ...` names the same classes.
    from toolkit.pipeline.migrate import main as _main

    sys.exit(_main())
