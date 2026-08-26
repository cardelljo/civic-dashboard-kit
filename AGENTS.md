# Agent instructions — civic-dashboard-kit

The shared toolkit behind the 901 civic dashboard series (901justice, 901education,
901economy): Python data-acquisition clients, the `_meta` provenance contract, two
observation stores (`observations.py` NDJSON, `postgres_store.py` Postgres), the
shared `geo` schema and boundary loaders, and a TypeScript `ui/` package for the
data-status components. Every dashboard pins this repo to an immutable commit and
installs it via pip/npm — never `@main`.

## Starting a session

A new thread can start with something this short, because the files below carry the
context:

> Read AGENTS.md, then docs/TASKS.md's Next Up section, then docs/PROJECT_NOTES.md for
> background — then [pick up the next ticket / describe the task].

## Keeping these docs current

This only works if it stays accurate. One trigger, one place to update:

- Finish a ticket → a dated entry in `docs/TASKS.md`'s "Done" log.
- A ticket opens, closes, or gets superseded → sync `docs/TASKS.md`'s Next Up list.
- Learn something that spans multiple tickets, or isn't task-shaped at all → a
  `docs/PROJECT_NOTES.md` entry, not buried in one ticket's prose.
- Find a durable rule or gotcha that will bite again → a non-negotable rule below.
- **Write a deep-dive doc on a specific topic** (a data-source research note, an
  integration plan, a standalone review) **→ it gets linked from a `docs/TASKS.md`
  ticket, existing or new, in the same commit.** A plan or insight that isn't attached
  to a task doesn't stop being useful, but it does stop being findable — this project
  has already accumulated deep, well-researched standalone docs in sibling repos that
  no ticket points at, which is indistinguishable from work nobody knows exists. If
  the doc doesn't fit an existing ticket, it gets a new one — even a one-line ticket
  whose body is "see `<doc>`" is enough to make it discoverable from Next Up.
- New work that doesn't fit an existing ticket → its own ticket, not folded into an
  unrelated one.

(Considered a skill for this instead of an `AGENTS.md` section — rejected because a
skill only fires when invoked or its trigger matches, and the point is a convention
that applies automatically, every session, with nobody needing to remember to invoke
it.)

## Read before writing code

- `docs/TASKS.md` — the living task list. Read its **Next Up** section first, not the
  file top-to-bottom — the rest is a dated history kept for context. Update checkboxes
  as you go; add a dated entry under "Done" when you finish anything nontrivial.
- `docs/PROJECT_NOTES.md` — durable findings that aren't a decision or a task: a
  sibling dashboard's actual state as last checked, precedent for a judgment call,
  things worth knowing before making a call. Add to it; don't duplicate its contents
  into a ticket, and don't re-derive something it already answers.
- `docs/ARCHITECTURE.md` — decisions that bind more than one dashboard: the shared
  Postgres instance, schema layout, PostGIS, `geo.boundaries`, the delivery mechanism.
  Cite the section you're contradicting rather than re-deriving it.
- `CONTRIBUTING.md` — setup, the Postgres dev harness, conventions for adding a client
  or a store backend, testing conventions, the PR checklist.
- `README.md` — the module reference table and "choosing a store" guidance
  (`observations.py` vs. `postgres_store.py`).
- The `civic-dashboard-dev` skill, if your session has it loaded — cross-repo process:
  where a decision belongs, delegation practice, token discipline. This file is the
  repo-local complement to it, not a replacement; the skill's own "who owns what"
  section explains the split.

## Non-negotiable rules

- **Rule-of-three before extracting.** Don't add toolkit code for a pattern only one
  dashboard uses yet. `docs/ARCHITECTURE.md` §7.2 holds `KpiCard`/`TrendChart` out on
  this basis even after conceding sharing would clearly pay off eventually. A pattern
  one dashboard has built — economy's `publish_site.py`, `jobs.py`/`runner.py` — is a
  **reference implementation** for the next dashboard to copy, not toolkit code, until
  a second one actually needs it. See `docs/PROJECT_NOTES.md` for current examples.
- **A skipped test is not a passing test.** `pytest` exits 0 when every Postgres test
  skips for want of `TOOLKIT_TEST_DATABASE_URL` — check the count, not the exit code.
  `tests/test_ci_guards.py` fails the job outright if `CI=true` with no database, so
  CI itself can't go green on an all-skipped run — but a local check still has to look
  at the number.
- **Real Postgres before claiming anything about `postgres_store` or `boundaries`
  works.** `scripts/dev-postgres.sh` builds one matching the deployed image (Postgres
  18 + PostGIS 3.6) on port 5433. It doesn't always survive between sessions in this
  environment — `pg_isready -h localhost -p 5433` before assuming it's up; rerun the
  script if not (idempotent).
- **Use `python3 -m pytest`, not a bare `pytest` invocation, when in doubt.** In some
  sandboxed sessions the `pytest` on `PATH` resolves to an isolated `uv tool`
  installation with none of this repo's dependencies, and fails on collection with
  `ModuleNotFoundError` for `psycopg2`/`requests` even though `pip install -e` just
  succeeded. `python3 -m pytest` always uses the environment you actually installed
  into.
- **A geometry claim gets checked against real PostGIS, not just at the GeoJSON
  level.** `ST_IsValid` on a loaded geometry has caught a real bug `toolkit.geo` gave
  no other sign of — `parse_shp` mishandling enclaves, found via `ST_IsValid` reporting
  "nested shells" (fixed, PR #17; see `docs/PROJECT_NOTES.md`). "The converter ran
  without error" and "it produced valid geometry" are different claims.
- **Pushing a git tag from this environment 403s** on `refs/tags` specifically
  (branches and commits push fine) — confirmed independently from more than one
  sandboxed session. If a tag needs pushing, say so and hand it to a normal machine
  rather than retrying.
- **This repo is public.** No hostnames, credentials, or connection strings in any
  committed file — `docs/ARCHITECTURE.md` included.

## Before calling a task done

**Never claim something works that you have not executed.** Report verified and
pending separately — a confident summary of untested work ends the review that would
have caught the problem.

- `python3 -m pytest -q` — against a real Postgres (above) if you touched
  `postgres_store.py`, `boundaries.py`, or anything in `toolkit.geo`; check the skip
  count, not just the exit code.
- `npm run typecheck && npm test` for `ui/` changes.
- Update `README.md`'s module reference table if you add or rename a module
  (`CONTRIBUTING.md`'s PR checklist has the rest).
- `CHANGELOG.md` under `[Unreleased]` for a shared-infrastructure change — not every
  internal addition gets an entry; check recent history for the actual bar rather than
  assuming every PR needs one.

## CI

`.github/workflows/test.yml` runs two independent jobs on every PR — `python` (pytest
against a real `postgis/postgis:18-3.6-alpine` service, matching the deployed image
exactly, not just the same family) and `typescript` (`npm run typecheck && npm test`).
Both gate every PR regardless of which half of the package a change touches —
`tests/test_data_status_union.py` in the Python job reads `ui/types.ts`, so the two
halves aren't independent even when a diff touches only one language.
