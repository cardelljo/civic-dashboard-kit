"""The shared pipeline container's internal HTTP runner (ARCHITECTURE §1.1, §1.3).

Internal Docker network only, never published. n8n's HTTP Request node POSTs here,
because its Execute Command node runs in n8n's own container and cannot reach the
pipeline's scripts. This process dispatches the named job as a subprocess in that
dashboard's checkout and reports success or failure -- it is a dispatcher, not a
transformer, and no data logic lives here.

    POST /run/{dashboard}/{job}   run one job (404 unknown dashboard / unknown job,
                                  403 manual-only job, 409 migration pending,
                                  502 job failed, 200 ok)
    POST /run/{job}               the old single-dashboard route, only when
                                  PIPELINE_LEGACY_DASHBOARD names the dashboard it
                                  means -- so one repo's n8n workflows keep working
                                  while it moves over
    GET  /jobs                    every registered dashboard and its jobs
    GET  /healthz

Serve with `python3 -m toolkit.pipeline.runner serve` (or
`uvicorn --factory toolkit.pipeline.runner:create_app`). Run one job by hand,
manual-only jobs included, with
`python3 -m toolkit.pipeline.runner run justice parse_jail_pdf [args...]`.

A job is refused while its dashboard has a pending migration, so a fetch can never
write new-format rows into an old-format database (or the reverse) between a deploy
and its migration. The check runs `toolkit.pipeline.migrate --check` in the
dashboard's own process; a dashboard that declares no migrations skips it.

Needs the `server` extra (FastAPI, uvicorn). The registry it reads does not.
"""

from __future__ import annotations

import argparse
import logging
import os
import subprocess
import sys

from toolkit.pipeline.migrate import EXIT_PENDING
from toolkit.pipeline.registry import Dashboard, Registry, UnknownDashboard, UnknownJob, load_registry

LOG = logging.getLogger(__name__)


def migration_block(dashboard: Dashboard) -> str | None:
    """A reason to refuse this dashboard's jobs, or None."""
    if not dashboard.migrations:
        return None
    cmd = [dashboard.python(), "-m", "toolkit.pipeline.migrate", "--check", "--root", str(dashboard.root)]
    try:
        result = dashboard.run(cmd, timeout=120)
    except Exception as exc:  # noqa: BLE001 -- can't tell, so don't write
        return f"could not check for pending database migrations: {exc}"
    out = (result.stdout + result.stderr).strip()
    if result.returncode == 0:
        return None
    if result.returncode == EXIT_PENDING:
        return (f"database migration pending for {dashboard.key} ({out.splitlines()[-1] if out else 'see log'}); "
                "the post-deploy command applies it, or run `python3 -m toolkit.pipeline.migrate --apply` "
                "in its checkout")
    return f"could not check for pending database migrations: {out[-500:] or result.returncode}"


def create_app(registry: Registry | None = None, *, legacy_dashboard: str | None = None):
    from fastapi import FastAPI, HTTPException

    registry = load_registry() if registry is None else registry
    legacy_dashboard = os.environ.get("PIPELINE_LEGACY_DASHBOARD") if legacy_dashboard is None else legacy_dashboard
    app = FastAPI(title="Civic dashboard pipeline runner")

    @app.get("/healthz")
    def healthz():
        return {"status": "ok", "dashboards": sorted(registry.dashboards)}

    @app.get("/jobs")
    def jobs():
        return {d.key: {name: {"manual": job.manual, "description": job.description}
                        for name, job in sorted(d.jobs.items())} for d in registry}

    def dispatch(dashboard_key: str, job_name: str):
        try:
            dashboard = registry.get(dashboard_key)
        except UnknownDashboard as exc:
            raise HTTPException(status_code=404, detail={"error": "unknown_dashboard", "message": str(exc)})
        try:
            job = dashboard.job(job_name)
        except UnknownJob as exc:
            raise HTTPException(status_code=404, detail={"error": "unknown_job", "message": str(exc)})
        if job.manual:
            raise HTTPException(status_code=403, detail={
                "error": "manual_only", "message": f"{dashboard.key}/{job.name} runs only by hand "
                f"(python3 -m toolkit.pipeline.runner run {dashboard.key} {job.name}). {job.description}".strip()})
        blocked = migration_block(dashboard)
        if blocked:
            LOG.error("Refusing %s/%s: %s", dashboard.key, job.name, blocked)
            raise HTTPException(status_code=409, detail={"error": "migration_pending", "job": job.name,
                                                         "dashboard": dashboard.key, "refused": blocked})
        LOG.info("Starting %s/%s", dashboard.key, job.name)
        try:
            result = dashboard.run_job(job.name)
        except subprocess.TimeoutExpired:
            LOG.error("%s/%s timed out after %ss", dashboard.key, job.name, job.timeout)
            raise HTTPException(status_code=504, detail={"error": "timeout", "job": job.name,
                                                         "dashboard": dashboard.key, "timeout": job.timeout})
        if result.returncode != 0:
            LOG.error("%s/%s failed with code %d:\nstdout: %s\nstderr: %s",
                      dashboard.key, job.name, result.returncode, result.stdout, result.stderr)
            raise HTTPException(status_code=502, detail={"error": "job_failed", "job": job.name,
                                                         "dashboard": dashboard.key, "stdout": result.stdout,
                                                         "stderr": result.stderr})
        LOG.info("%s/%s succeeded", dashboard.key, job.name)
        return {"dashboard": dashboard.key, "job": job.name, "status": "success", "stdout": result.stdout}

    @app.post("/run/{dashboard_key}/{job_name}")
    def run_job(dashboard_key: str, job_name: str):
        return dispatch(dashboard_key, job_name)

    @app.post("/run/{job_name}")
    def run_legacy(job_name: str):
        if not legacy_dashboard:
            raise HTTPException(status_code=404, detail={
                "error": "unknown_dashboard",
                "message": "this runner serves several dashboards; POST /run/{dashboard}/{job}"})
        return dispatch(legacy_dashboard, job_name)

    return app


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Shared pipeline runner")
    sub = parser.add_subparsers(dest="command", required=True)
    serve = sub.add_parser("serve", help="serve the HTTP runner")
    serve.add_argument("--host", default="0.0.0.0")
    serve.add_argument("--port", type=int, default=8000)
    once = sub.add_parser("run", help="run one job now and exit (manual-only jobs included)")
    once.add_argument("dashboard")
    once.add_argument("job")
    once.add_argument("args", nargs=argparse.REMAINDER, help="extra arguments passed to the job")
    sub.add_parser("list", help="list registered dashboards and jobs")
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    registry = load_registry()

    if args.command == "list":
        for dashboard in registry:
            print(f"{dashboard.key}  ({dashboard.root}, schema {dashboard.schema})")
            for name, job in sorted(dashboard.jobs.items()):
                print(f"  {name}{'  [manual]' if job.manual else ''}  {' '.join(job.command)}")
        return 0
    if args.command == "run":
        try:
            dashboard = registry.get(args.dashboard)
            dashboard.job(args.job)
        except (UnknownDashboard, UnknownJob) as exc:
            print(exc, file=sys.stderr)
            return 1
        blocked = migration_block(dashboard)
        if blocked:
            print(f"Refusing {dashboard.key}/{args.job}: {blocked}", file=sys.stderr)
            return 1
        return dashboard.run_job(args.job, args.args, capture=False).returncode

    import uvicorn

    uvicorn.run(create_app(registry), host=args.host, port=args.port)
    return 0


if __name__ == "__main__":
    # Run the imported module, not this __main__ copy, so a dashboard's
    # `from toolkit.pipeline.runner import ...` names the same classes.
    from toolkit.pipeline.runner import main as _main

    sys.exit(_main())
