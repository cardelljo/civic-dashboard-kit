# Planning prompt: move 901education and 901justice onto Postgres

Paste this into a new planning thread. Its **output is tasks for each dashboard's
own `PLAN.md`** — not new architecture. The decision is already made and recorded
in [`docs/ARCHITECTURE.md`](../ARCHITECTURE.md) §1; do not relitigate it, and do
not record per-dashboard tasks in the shared file.

---

## The prompt

> You are planning the migration of **901education** and **901justice** onto the
> shared Postgres instance. The decision to move every dashboard off
> git-committed files and into Postgres is already made and recorded in
> `civic-dashboard-kit/docs/ARCHITECTURE.md` §1 — the reason is removing GitHub
> from the data layer's operational dependencies, not data volume. Your job is to
> produce **ordered, verifiable tasks** for each repo's `PLAN.md`, not to
> re-decide the direction.
>
> **Read first**, and treat them as binding:
> - `civic-dashboard-kit/docs/ARCHITECTURE.md` — §1 (the decision), §2 (schema per
>   dashboard), §3.1 (`db/bootstrap.sql`: the schemas and roles already exist,
>   `education_app` and `justice_app` are created and their `search_path` set)
> - `civic-dashboard-kit/README.md` — `postgres_store` is generic and must not be
>   forked or reimplemented per dashboard
> - `901economy/db/schema.sql`, `901economy/pipeline/db.py`, and any
>   `901economy/pipeline/fetch_*.py` — **the reference implementation.** Economy
>   has already done this end to end; the shape of these tasks is "do what economy
>   did," not "invent an approach."
> - each target repo's own `AGENTS.md` and `PLAN.md`
>
> **Answer these before writing tasks**, because they change the task list:
>
> 1. **901education's existing NDJSON history — backfill or start fresh?** Its
>    ledger holds real observations. This project promises readers an append-only
>    record, so silently dropping history would break that promise. If backfilling:
>    what maps `Observation` rows in the ledger to `indicators` rows, and what
>    `vintage` / `source_runs` entry do historical rows get, given the original
>    fetch timestamps are what the ledger recorded rather than the migration date?
> 2. **901justice has no store module at all** — it writes static JSON directly.
>    So this is a net-new build, not a migration. Does its existing
>    `data/*.json` output have history worth preserving, or is each file a current
>    snapshot only?
> 3. **What happens to `toolkit.observations` consumers during the transition?**
>    Can education run both stores briefly, or is it a hard cutover?
> 4. **Does the daily justice cron keep working throughout?** It is a live site.
>    Any task that can break it needs an explicit rollback step.
>
> **For each repo, produce tasks that:**
> - name one source or one concern each
> - state **runnable** acceptance criteria — a row count, an exit code, a specific
>   query returning a specific thing. Not "looks right."
> - include a test that would fail if the task regressed. Note that a skipped test
>   is not a passing test: `pytest` exits 0 when every database test skips for want
>   of `TOOLKIT_TEST_DATABASE_URL`, so check the skip count. Use
>   `civic-dashboard-kit/scripts/dev-postgres.sh` for a real local Postgres 18.
> - say explicitly what is **out of scope**, so a delegate doesn't discover it
>   halfway
>
> **Sequencing constraints to respect:**
> - Nothing here is blocked on the shared instance — `db/bootstrap.sql` has
>   already created both schemas and roles.
> - Each dashboard needs its own pipeline execution path inside the Coolify
>   network, because Postgres is internal-only and external CI cannot reach it.
> - Do the repo with a real verification gate before the one without: education
>   runs pytest on PRs, justice builds with type *and* lint errors ignored.
>
> **Delivery is already decided — §1.1.** Public pages stay a static export, but
> generated into a volume nginx serves rather than committed to git. So a
> migration task must **not** add a commit step to any publish path, and any
> existing "diff and commit the built JSON" step it inherits should be flagged as
> superseded rather than reproduced. The T3 admin queue is the one dynamic
> surface. If a task seems to need dynamic public rendering, say so and stop
> rather than deciding it.

---

## Why this is a separate thread

Migration tasks are per-dashboard work, and the cross-repo thread's own rule is
that a decision binding a sibling repo is recorded in the shared file first and
summarized locally after. §1 is now recorded. What remains is execution planning,
which belongs where the code lives.
