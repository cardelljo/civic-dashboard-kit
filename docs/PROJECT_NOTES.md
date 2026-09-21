# Project Notes

Durable background for civic-dashboard-kit that spans multiple tickets or isn't
task-shaped at all: sibling-dashboard facts as last checked, precedent for judgment
calls, things worth knowing before making a call. Three-file split, same shape this
series' dashboards use:

- `AGENTS.md` (root, symlinked as `CLAUDE.md`) — non-negotiable rules and gotchas.
  Short, stable, read every session.
- `docs/TASKS.md` — the task list and a dated history of what shipped and why. Read
  its **Next Up** section first.
- `docs/PROJECT_NOTES.md` (this file) — everything durable that isn't a decision
  (`docs/ARCHITECTURE.md`) or a task. Add to it; don't duplicate its contents into a
  ticket, and don't re-derive something it already answers.

## Sibling dashboards — state as last checked

Each dashboard makes its own store and rigor calls; nothing here is copied into
another repo without checking first. Dates matter — these are snapshots, not standing
facts, and will go stale exactly like the things they're here to prevent going stale.

### 901economy (checked 2026-08-22/23)

- **Running Postgres in production, not just code-complete** — confirmed directly by
  the user, 2026-08-23. Its own `docs/TASKS.md` task 1 checkbox was still unchecked as
  of commit `c435c4b` ("external / server-side — not codeable from a dev session")
  when checked; that's tracker drift in economy's repo, not a correction to the
  deployment claim. Worth fixing there if you're picking up work in that repo.
- **`db/schema.sql` is a flat, unqualified schema** — no `CREATE SCHEMA`, relies on the
  connecting role's `search_path` (matches this repo's `db/bootstrap.sql`: namespacing
  comes from `search_path`, not table prefixes). Confirmed independently by
  901education's own check of the same file (`901education/docs/PROJECT_NOTES.md`,
  2026-08-25). The "Postgres role per dashboard, role-scoped tables" shape is not yet a
  solved pattern with more than one real example — treat it as a reference
  implementation to read, not a template to copy blind.
- **Publish mechanism is real and matches `docs/ARCHITECTURE.md` §1.1 exactly**:
  `pipeline/publish_site.py` — `validate_snapshots.py --strict` → `next build` →
  atomic `releases/<timestamp>/` + symlink swap, no git in the data path. First real
  implementation anywhere in the series. Not toolkit code yet (rule-of-three,
  `AGENTS.md`) — it's the reference for education/justice to copy when they build
  their own delivery mechanism. `pipeline/jobs.py`/`runner.py` (job registry + FastAPI
  dispatcher) is the same kind of reference, relevant to 901justice's on-server
  pipeline decision.
- **First real adopter of this repo's `ui/` package** (`docs/ARCHITECTURE.md` §7.2).
  The sequencing rule there — economy runs on it through a real publish cycle before
  any backport — is now satisfied, which unblocks backporting to justice/education.
- **`git tag` pushes 403 from economy's own dev sandbox too** — not specific to this
  repo's environment; a general property of these sandboxed sessions' git proxy.

### 901education (checked 2026-08-25, via their own `docs/PROJECT_NOTES.md`)

- Adopted the same `AGENTS.md`/`docs/TASKS.md` Next Up/`docs/PROJECT_NOTES.md` split
  this file is part of, independently, in response to the same kind of prompt — a
  reasonable signal it's the right shape and not just this repo's house style.
- Postgres migration direction confirmed 2026-08-23, not started. Their own notes
  explicitly warn not to assume 901economy's schema is a solved reference to copy
  verbatim — see the economy entry above; they found the same thing independently.
- Cloned 901economy read-only to check for reusable ALICE/Census work relevant to its
  own Early Childhood / Community Conditions gap tiles: ALICE Household Survival
  Budgets are Shelby-specific, live, and include a Child Care cost line.

### 901justice

- Still the only dashboard with real boundary polygons on disk
  (`data/boundaries/*.json`). Six of its layers are now also in the shared
  `geo.boundaries` (PR #12); MPD ward/station layers deliberately left justice-only —
  parked by the user 2026-08, not a decision to revisit without being asked.
  `docs/ARCHITECTURE.md` §6.
- `typescript.ignoreBuildErrors`/`eslint.ignoreDuringBuilds` both on — a deliberate,
  undecided call about a live site (`docs/ARCHITECTURE.md` §8, item 2). Don't flip it
  without a decision from the user.
- No store module; a net-new Postgres build when it happens, not a migration
  (`docs/ARCHITECTURE.md` §1). **Migration scoping began 2026-09-21 in a separate
  thread.**
- **Its data vocabulary is the widest in the series, and part of it does not fit the
  shared schema** (measured 2026-09-21 across its 18 committed datasets). Ten carry
  trend series, most carry scalar KPIs — both fit `indicators`. Three do not:
  `doj_findings`, `juvenile_doj_monitor`, and `tbi_tops` hold *finding* records
  (headline, narrative detail, a string `valueLabel`, editorial `publicMeaning` /
  `dashboardGap`, quotes with page cites) and dated *milestone* timelines. `indicators`
  has a `NUMERIC value` and a required `period`; a DOJ finding has neither. Full
  analysis, the four-kind surface taxonomy, and the open decisions:
  `docs/DASHBOARD_SURFACES.md`. This is the concrete instance of why
  `docs/ARCHITECTURE.md` §1.3 makes justice the lens for the abstraction rather than
  its last consumer.
- Its daily AI (jail-roster) extraction auto-commits with no review gate today — a
  live gap per 901economy's own tracker, which calls backporting a review gate the
  highest-priority cross-dashboard item once economy's own T3/LangExtract work lands.

## Rule-of-three, applied

A recurring judgment call, worth having precedent for instead of re-deciding it each
time: extraction happens when a *second* dashboard actually needs a pattern, not when
the first dashboard's version would obviously be reusable. `docs/ARCHITECTURE.md` §7.2
held `KpiCard`/`TrendChart` out on this basis even after conceding sharing would
clearly pay off eventually.

**Updated 2026-09-21 — `publish_site.py` and `jobs.py`/`runner.py` have graduated.**
This entry previously listed them as reference implementations for the next dashboard
to copy, not extraction candidates. Two things changed. 901education copied them, so
there are two implementations and they have already drifted (`runner.py` 51 vs 85
lines; education has no `publish_site.py` at all and an `nginx.conf` that cannot serve
a server-built release — `docs/ARCHITECTURE.md` §1.3's table). And 901justice's
Postgres adoption brings the third consumer, which is the rule met on its own terms.
`docs/TASKS.md` Next Up item 1 is the extraction.

Worth keeping from the old wording: "copy it and see" was the right call at the time.
The drift is the cost of having been right — two copies is what the rule asks you to
wait for, and waiting means they diverge in the meantime. The lesson is not to extract
earlier, it is to diff at the moment the second copy appears rather than at the third
(see the `SampleBadge` 57/58/58 case, and `docs/DASHBOARD_SURFACES.md`'s template
section applying it one step earlier).

## Things that looked like a bug in the data and weren't (or vice versa)

`ST_IsValid` flagging a loaded boundary as invalid is not self-evidently "the source
data is bad." `toolkit.geo.parse_shp` mishandled enclaves — a ring wholly inside
another ring of the same shapefile record rendered as a separate solid polygon
instead of a hole — until PR #17, and that produces exactly the symptom
("nested shells") a genuinely corrupt shapefile would too. `docs/ARCHITECTURE.md` §6.2
got this wrong once already, attributing the symptom to TIGER's source geometry
before the real cause turned up (independently, in 901economy's
`pipeline/fetch_boundaries.py`, building the same municipality layer from the same
source). Check the converter before blaming the source.
