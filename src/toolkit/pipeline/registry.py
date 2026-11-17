"""Which jobs each dashboard can run, and how to run them.

Standard library only: this is the contract a dashboard's `n8n/*.json` workflows and
the runner both have to agree on, and the test that checks that agreement must not
need FastAPI (901economy's `pipeline/jobs.py` records that it broke once when it did).

Nothing in the kit names a dashboard's jobs. Each dashboard declares them in a
`pipeline.json` at the root of its own checkout:

    {
      "dashboard": "justice",
      "schema": "justice",
      "command_template": ["scripts/{job}.py"],
      "jobs": {
        "fetch_crime_data": {},
        "fetch_tract_context": {"timeout": 3600},
        "parse_jail_pdf": {"manual": true,
                           "description": "AI extraction with no review gate yet"},
        "fetch_fred": ["-m", "pipeline.fetch_fred"]
      },
      "seed": ["scripts/seed_foundation.py"],
      "migrations": "scripts.migrations:MIGRATIONS",
      "run_once": {"backfill_from_snapshots": {"token": "2026-11-15-first-load"}}
    }

- `dashboard` is the key in `/run/{dashboard}/{job}`; `schema` is the Postgres schema
  that dashboard's role must resolve to (`migrate` and `post_deploy` refuse to write
  anywhere else).
- A job is `{}` (use `command_template`), a list (its exact command), a string (a
  script path), or an object with `command`, `manual`, `timeout` and `description`.
  `jobs` may also be a plain list of names that all use the template. Both existing
  layouts fit: education's `scripts/{job}.py` and economy's `-m pipeline.{job}`.
- `manual: true` jobs never run over HTTP, so no schedule can start them. They run
  from the container's terminal with `python3 -m toolkit.pipeline.runner run ...`.
  901justice's jail-PDF extraction is the case this exists for (its AGENTS.md: no
  review gate yet, so it is not scheduled).
- `seed` runs before migrations on every deploy; `migrations` names a list of
  `toolkit.pipeline.migrate.Migration` inside the dashboard's own code; `run_once`
  maps a job to a token (and optional `args`) that runs once per database.

The container lists the checkouts it serves in `PIPELINE_DASHBOARDS`, separated by
`:` or `,`. Per dashboard it reads `DATABASE_URL_<KEY>` (falling back to
`DATABASE_URL`) and runs `PIPELINE_PYTHON_<KEY>`, else `<root>/.venv/bin/python`,
else the container's own interpreter -- so each dashboard keeps its own kit pin.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Mapping

CONFIG_FILE = "pipeline.json"
DEFAULT_TIMEOUT = 1800

# Never passed to a job's process (see Dashboard.subprocess_env).
WITHHELD_FROM_JOBS = frozenset({"GITHUB_TOKEN", "GH_TOKEN", "GITHUB_PAT", "GH_ENTERPRISE_TOKEN",
                                "PIPELINE_RUNNER_TOKEN"})
KEY_RE = re.compile(r"^[a-z][a-z0-9_-]*$")
JOB_RE = re.compile(r"^[A-Za-z0-9_][A-Za-z0-9_.-]*$")


class RegistryError(ValueError):
    """A `pipeline.json` (or the container's dashboard list) is malformed."""


class UnknownDashboard(LookupError):
    pass


class UnknownJob(LookupError):
    pass


def env_suffix(key: str) -> str:
    """`justice` -> `JUSTICE`, `north-shore` -> `NORTH_SHORE`."""
    return re.sub(r"[^A-Z0-9]", "_", key.upper())


@dataclass(frozen=True)
class Job:
    name: str
    command: tuple[str, ...]
    manual: bool = False
    timeout: int = DEFAULT_TIMEOUT
    description: str = ""

    def script(self) -> str | None:
        """The script path this job runs, or None for a `-m module` command."""
        if self.command and self.command[0] != "-m" and self.command[0].endswith(".py"):
            return self.command[0]
        return None


@dataclass(frozen=True)
class RunOnce:
    job: str
    token: str
    args: tuple[str, ...] = ()


@dataclass(frozen=True)
class Dashboard:
    key: str
    root: Path
    schema: str
    jobs: Mapping[str, Job]
    seed: tuple[str, ...] | None = None
    migrations: str | None = None
    run_once: tuple[RunOnce, ...] = ()

    def job(self, name: str) -> Job:
        try:
            return self.jobs[name]
        except KeyError:
            raise UnknownJob(f"{self.key} has no job {name!r}") from None

    def python(self, env: Mapping[str, str] | None = None) -> str:
        env = os.environ if env is None else env
        explicit = env.get(f"PIPELINE_PYTHON_{env_suffix(self.key)}")
        if explicit:
            return explicit
        venv = self.root / ".venv" / "bin" / "python"
        return str(venv) if venv.exists() else sys.executable

    def dsn(self, env: Mapping[str, str] | None = None) -> str | None:
        env = os.environ if env is None else env
        return env.get(f"DATABASE_URL_{env_suffix(self.key)}") or env.get("DATABASE_URL")

    def subprocess_env(self, env: Mapping[str, str] | None = None) -> dict[str, str]:
        """The parent's environment with this dashboard's database as `DATABASE_URL`,
        which is the name every dashboard's own `scripts/db.py` already reads.

        Every `DATABASE_URL_<KEY>` is removed, so a job sees only its own database and
        never another dashboard's login, and so are the GitHub tokens in
        `WITHHELD_FROM_JOBS`: a job's fetchers and their third-party packages have no
        use for them."""
        parent = dict(os.environ if env is None else env)
        dsn = self.dsn(parent)
        out = {k: v for k, v in parent.items()
               if not k.startswith("DATABASE_URL_") and k not in WITHHELD_FROM_JOBS}
        if dsn:
            out["DATABASE_URL"] = dsn
        out["PIPELINE_DASHBOARD"] = self.key
        return out

    def command(self, job: str, args: tuple[str, ...] | list[str] = (), env: Mapping[str, str] | None = None) -> list[str]:
        return [self.python(env), *self.job(job).command, *args]

    def run(self, cmd: list[str], *, timeout: int = DEFAULT_TIMEOUT, capture: bool = True,
            env: Mapping[str, str] | None = None) -> subprocess.CompletedProcess:
        """Run an already-built command in this dashboard's checkout and environment."""
        return subprocess.run(cmd, cwd=self.root, env=self.subprocess_env(env), timeout=timeout,
                              capture_output=capture, text=True)

    def run_job(self, job: str, args: tuple[str, ...] | list[str] = (), *, capture: bool = True,
                env: Mapping[str, str] | None = None) -> subprocess.CompletedProcess:
        return self.run(self.command(job, args, env), timeout=self.job(job).timeout, capture=capture, env=env)

    def missing_scripts(self) -> list[str]:
        """Jobs whose script file is not in the checkout. Not a load error -- a job can
        be registered before its extractor is built -- but worth a test in each repo."""
        return sorted(name for name, job in self.jobs.items()
                      if job.script() and not (self.root / job.script()).is_file())


@dataclass
class Registry:
    dashboards: dict[str, Dashboard] = field(default_factory=dict)

    def get(self, key: str) -> Dashboard:
        try:
            return self.dashboards[key]
        except KeyError:
            raise UnknownDashboard(f"no dashboard {key!r}; registered: {', '.join(sorted(self.dashboards)) or 'none'}") from None

    def __iter__(self):
        return iter(self.dashboards[key] for key in sorted(self.dashboards))

    def __len__(self) -> int:
        return len(self.dashboards)


# --------------------------------------------------------------------------- loading

def _command(raw, where: str) -> tuple[str, ...]:
    if isinstance(raw, str):
        raw = [raw]
    if not isinstance(raw, list) or not raw or not all(isinstance(part, str) and part for part in raw):
        raise RegistryError(f"{where}: a command is a non-empty list of strings")
    first = raw[0]
    if first == "-m":
        if len(raw) < 2:
            raise RegistryError(f"{where}: '-m' needs a module name")
    elif first.startswith("-"):
        raise RegistryError(f"{where}: a command starts with a script path or '-m', not {first!r}")
    elif Path(first).is_absolute() or ".." in Path(first).parts:
        raise RegistryError(f"{where}: script paths are relative to the checkout and stay inside it ({first!r})")
    return tuple(raw)


def _job(name: str, raw, template: list[str] | None, where: str) -> Job:
    if not JOB_RE.match(name):
        raise RegistryError(f"{where}: job name {name!r} is not URL-safe")
    spec: dict = {}
    if isinstance(raw, (str, list)):
        spec = {"command": raw}
    elif isinstance(raw, dict):
        unknown = set(raw) - {"command", "manual", "timeout", "description"}
        if unknown:
            raise RegistryError(f"{where}: unknown job field(s) {sorted(unknown)}")
        spec = raw
    else:
        raise RegistryError(f"{where}: a job is {{}}, a command list, a script path, or an object")
    if "command" in spec:
        command = _command(spec["command"], where)
    elif template:
        command = _command([part.replace("{job}", name) for part in template], where)
    else:
        raise RegistryError(f"{where}: no command and no command_template")
    timeout = spec.get("timeout", DEFAULT_TIMEOUT)
    if not isinstance(timeout, int) or isinstance(timeout, bool) or timeout <= 0:
        raise RegistryError(f"{where}: timeout is a positive number of seconds")
    manual = spec.get("manual", False)
    if not isinstance(manual, bool):
        raise RegistryError(f"{where}: manual is true or false")
    return Job(name=name, command=command, manual=manual, timeout=timeout,
               description=str(spec.get("description", "")))


def parse_dashboard(config: dict, root: Path | str, *, source: str = CONFIG_FILE) -> Dashboard:
    root = Path(root).resolve()
    if not isinstance(config, dict):
        raise RegistryError(f"{source}: expected a JSON object")
    unknown = set(config) - {"dashboard", "schema", "command_template", "jobs", "seed", "migrations",
                             "run_once", "$comment"}
    if unknown:
        raise RegistryError(f"{source}: unknown field(s) {sorted(unknown)}")
    key = config.get("dashboard")
    if not isinstance(key, str) or not KEY_RE.match(key):
        raise RegistryError(f"{source}: 'dashboard' must be a lowercase key like 'justice'")
    schema = config.get("schema")
    if not isinstance(schema, str) or not re.match(r"^[a-z_][a-z0-9_]*$", schema):
        raise RegistryError(f"{source}: 'schema' must be the dashboard's Postgres schema name")

    template = config.get("command_template")
    if template is not None:
        _command(template, f"{source} command_template")
        if not any("{job}" in part for part in template):
            raise RegistryError(f"{source}: command_template must contain {{job}}")

    raw_jobs = config.get("jobs")
    if isinstance(raw_jobs, list):
        raw_jobs = {name: {} for name in raw_jobs}
    if not isinstance(raw_jobs, dict) or not raw_jobs:
        raise RegistryError(f"{source}: 'jobs' must list at least one job")
    jobs = {name: _job(name, raw, template, f"{source} jobs.{name}") for name, raw in raw_jobs.items()}

    seed = config.get("seed")
    seed_cmd = _command(seed, f"{source} seed") if seed is not None else None

    migrations = config.get("migrations")
    if migrations is not None and not (isinstance(migrations, str) and re.match(r"^[\w.]+:\w+$", migrations)):
        raise RegistryError(f"{source}: 'migrations' is 'package.module:ATTRIBUTE'")

    run_once = []
    for job, spec in (config.get("run_once") or {}).items():
        where = f"{source} run_once.{job}"
        if job not in jobs:
            raise RegistryError(f"{where}: not a registered job")
        if isinstance(spec, str):
            spec = {"token": spec}
        if not isinstance(spec, dict) or not isinstance(spec.get("token"), str) or not spec["token"]:
            raise RegistryError(f"{where}: needs a non-empty 'token'")
        args = spec.get("args", [])
        if not isinstance(args, list) or not all(isinstance(a, str) for a in args):
            raise RegistryError(f"{where}: 'args' is a list of strings")
        run_once.append(RunOnce(job=job, token=spec["token"], args=tuple(args)))

    return Dashboard(key=key, root=root, schema=schema, jobs=jobs, seed=seed_cmd,
                     migrations=migrations, run_once=tuple(sorted(run_once, key=lambda r: r.job)))


def load_dashboard(root: Path | str) -> Dashboard:
    path = Path(root) / CONFIG_FILE
    try:
        config = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise RegistryError(f"{path}: not found (each dashboard checkout declares its jobs here)") from None
    except json.JSONDecodeError as exc:
        raise RegistryError(f"{path}: not valid JSON ({exc})") from None
    return parse_dashboard(config, root, source=str(path))


def dashboard_roots(env: Mapping[str, str] | None = None) -> list[str]:
    env = os.environ if env is None else env
    raw = env.get("PIPELINE_DASHBOARDS", "")
    return [part.strip() for part in re.split(r"[:,]", raw) if part.strip()]


def load_registry(roots: list[Path | str] | None = None, env: Mapping[str, str] | None = None) -> Registry:
    roots = dashboard_roots(env) if roots is None else roots
    registry = Registry()
    for root in roots:
        dashboard = load_dashboard(root)
        if dashboard.key in registry.dashboards:
            raise RegistryError(f"dashboard {dashboard.key!r} is registered twice "
                                f"({registry.dashboards[dashboard.key].root} and {dashboard.root})")
        registry.dashboards[dashboard.key] = dashboard
    return registry
