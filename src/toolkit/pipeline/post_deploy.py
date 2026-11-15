"""Everything a pipeline redeploy needs, for every dashboard the container serves.

Meant as Coolify's **Post-deployment command** for the shared pipeline container:

    python3 -m toolkit.pipeline.post_deploy                    # every dashboard in PIPELINE_DASHBOARDS
    python3 -m toolkit.pipeline.post_deploy --dashboard justice

For each dashboard, in its own checkout and with its own interpreter and database:

1. `seed` from its `pipeline.json` -- schema and seed rows, both idempotent. A new
   job's geographies, sources and indicator definitions must exist before its first
   run, so a failure here stops *that dashboard*.
2. `python3 -m toolkit.pipeline.migrate --apply` -- every pending migration, each in
   one transaction that rolls back on any failed check. A failure stops that
   dashboard: its jobs below would write into the wrong shape, and the runner
   refuses its scheduled jobs until a later apply succeeds.
3. Each `run_once` job whose token this database has not run yet. The token is
   recorded only when the job succeeds, so a failure is retried on the next deploy.
   A PR that adds a job, or changes what one writes, adds a `run_once` line saying
   exactly what to run (education's rule, kept: nothing guesses which jobs are new).

One dashboard failing does not stop the others (one container is one failure domain,
ARCHITECTURE §1.3 -- this keeps a bad seed in one repo from blocking another's
migration). The exit code is non-zero if anything failed, and the output says which
dashboard and which step.

Not here yet: syncing n8n workflows and publishing a server-built site. Both are the
next pieces of docs/TASKS.md Next Up item 1; until then a dashboard that needs them
runs its own (`pipeline.sync_n8n`, `publish_site.py`) as before.
"""

from __future__ import annotations

import argparse
import sys

from toolkit.pipeline.registry import Dashboard, Registry, RunOnce, env_suffix, load_registry

RUN_TABLE = """CREATE TABLE IF NOT EXISTS post_deploy_runs (
    job TEXT NOT NULL, token TEXT NOT NULL, ran_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (job, token))"""

TAIL = 4000  # characters of a step's output to log


def _log(line: str) -> None:
    print(line, flush=True)


def _run(dashboard: Dashboard, cmd: list[str], *, timeout: int) -> tuple[bool, str]:
    try:
        result = dashboard.run(cmd, timeout=timeout)
    except Exception as exc:  # noqa: BLE001 -- a timeout or a missing interpreter is a failed step
        return False, f"could not run {' '.join(cmd)}: {exc}"
    return result.returncode == 0, (result.stdout + result.stderr).strip()


def done_tokens(conn) -> set[tuple[str, str]]:
    with conn.cursor() as cur:
        cur.execute(RUN_TABLE)
        cur.execute("SELECT job, token FROM post_deploy_runs")
        rows = {(job, token) for job, token in cur.fetchall()}
    conn.commit()
    return rows


def record_token(conn, job: str, token: str) -> None:
    with conn.cursor() as cur:
        cur.execute(RUN_TABLE)
        cur.execute("INSERT INTO post_deploy_runs (job, token) VALUES (%s, %s) ON CONFLICT DO NOTHING", (job, token))
    conn.commit()


def due(done: set[tuple[str, str]], run_once: tuple[RunOnce, ...]) -> list[RunOnce]:
    return [r for r in run_once if (r.job, r.token) not in done]


def open_db(dashboard: Dashboard):
    """A connection checked to resolve to this dashboard's own schema."""
    from toolkit.pipeline.migrate import connect, schema_problem

    dsn = dashboard.dsn()
    if not dsn:
        raise RuntimeError(f"no database for {dashboard.key}: set DATABASE_URL_{env_suffix(dashboard.key)} or DATABASE_URL")
    conn = connect(dsn)
    problem = schema_problem(conn, dashboard)
    if problem:
        conn.close()
        raise RuntimeError(problem)
    return conn


def deploy_one(dashboard: Dashboard) -> list[str]:
    """Run the three steps for one dashboard. Returns its problems (empty = all good)."""
    _log(f"== {dashboard.key} ({dashboard.root})")
    py = dashboard.python()

    if dashboard.seed:
        ok, out = _run(dashboard, [py, *dashboard.seed], timeout=600)
        _log(out[-TAIL:])
        if not ok:
            _log(f"{dashboard.key}: seed failed; skipping its migrations and jobs")
            return [f"{dashboard.key}: seed failed"]
    else:
        _log(f"{dashboard.key}: no seed step declared")

    ok, out = _run(dashboard, [py, "-m", "toolkit.pipeline.migrate", "--apply", "--root", str(dashboard.root)],
                   timeout=1800)
    _log(out[-TAIL:])
    if not ok:
        _log(f"{dashboard.key}: migrations failed and were rolled back; skipping its jobs. Its scheduled jobs "
             "are refused until `python3 -m toolkit.pipeline.migrate --apply` succeeds in its checkout.")
        return [f"{dashboard.key}: migrations failed"]

    if not dashboard.run_once:
        _log(f"{dashboard.key}: no one-time jobs declared")
        return []

    problems: list[str] = []
    try:
        conn = open_db(dashboard)
    except Exception as exc:  # noqa: BLE001
        _log(f"{dashboard.key}: {exc}")
        return [f"{dashboard.key}: could not read one-time job tokens"]
    try:
        jobs = due(done_tokens(conn), dashboard.run_once)
        if not jobs:
            _log(f"{dashboard.key}: no one-time jobs due")
        for item in jobs:
            _log(f"{dashboard.key}: running {item.job} ({item.token})")
            ok, out = _run(dashboard, dashboard.command(item.job, item.args), timeout=dashboard.job(item.job).timeout)
            _log(out[-TAIL:])
            if ok:
                record_token(conn, item.job, item.token)
            else:
                problems.append(f"{dashboard.key}: {item.job} failed (retried next deploy)")
    finally:
        conn.close()
    return problems


def main(argv: list[str] | None = None, registry: Registry | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--dashboard", action="append", help="only this dashboard (repeatable)")
    args = parser.parse_args(argv)

    registry = load_registry() if registry is None else registry
    if not len(registry):
        _log("no dashboards registered: set PIPELINE_DASHBOARDS to the checkouts this container serves")
        return 1
    targets = [registry.get(key) for key in args.dashboard] if args.dashboard else list(registry)

    problems: list[str] = []
    for dashboard in targets:
        problems += deploy_one(dashboard)
    if problems:
        _log("PROBLEMS:\n  " + "\n  ".join(problems))
        return 1
    _log("post_deploy done")
    return 0


if __name__ == "__main__":
    # Run the imported module, not this __main__ copy, so a dashboard's
    # `from toolkit.pipeline.post_deploy import ...` names the same classes.
    from toolkit.pipeline.post_deploy import main as _main

    sys.exit(_main())
