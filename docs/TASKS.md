# civic-dashboard-kit Task Tracker

Living task list for the shared toolkit behind 901justice, 901education, and
901economy. Read `AGENTS.md` first, then `docs/ARCHITECTURE.md` for the why behind any
shared-infrastructure item. **Next Up** below is the entry point for "what should I
work on" — the rest of this file is a dated history of what shipped and why, kept for
context, not a queue to work top-to-bottom. Update checkboxes as you go, and add a
dated entry under "Done" when you finish anything nontrivial.

---

## Next Up

**Container consolidation (`docs/ARCHITECTURE.md` §1.3, decided 2026-09-21) — two
containers for the series instead of two per dashboard. Items 1 then 2, in that order;
both should land before 901justice's Postgres + admin step so the review queue gets
built once rather than per dashboard. Item 3 runs in parallel — it is a content-model
question the justice migration raised, not container work, and it is paced by that
migration rather than by these two.**

**Read `docs/ARCHITECTURE.md` §1.3's "justice is the lens" subsection before promoting
anything here.** Economy's and education's copies already agree with each other;
abstracting from that agreement produces a toolkit that fits two repos and fights the
third, and the third is the most developed dashboard in the series.

1. [ ] **Promote the pipeline dispatcher into the kit as `toolkit.pipeline`, namespaced
   by dashboard.** §1.3's first half: one pipeline container running every dashboard's
   jobs.

   *Rule-of-three: satisfied, not exempted.* An earlier draft of this ticket argued an
   exemption — that §1.3's single container means there is no pattern to share, only
   two copies of one service to consolidate. That still holds, but it is the weaker
   argument and it is not needed: **901justice adopting Postgres brings a third
   consumer**, which satisfies the rule on its own terms. `docs/PROJECT_NOTES.md`'s
   "Rule-of-three, applied" entry listed `runner.py`/`jobs.py` as reference
   implementations rather than extraction candidates; it is updated for this.
   Per §1.3's "justice is the lens" subsection, check the registry design against
   justice's actual job inventory before landing it — the extraction is justified now,
   but the *shape* should be answerable to the repo that hasn't been accommodated yet.

   *What moves, and what it has to reconcile.* Two drifted copies exist
   (`901economy/pipeline/`, `901education/pipeline/`), and they disagree on real
   things, not just style:

   | Module | Reconciliation needed |
   |---|---|
   | `runner.py` (51 vs 85 lines) | Education's `logging` and `argparse`/`--job`/`--run-now` CLI are strictly more useful than economy's bare app — take education's shape. Keep the dispatcher-not-transformer rule in the docstring. |
   | `jobs.py` → `registry.py` | **The actual design problem.** Economy runs `-m pipeline.<job>`; education resolves `scripts/<job>.py` via `get_job_command()`. The registry must map job name → command, not just hold a name set, with both layouts expressible. Education's `get_job_command` is the more general of the two and the better base. |
   | `publish_site.py` | Exists only in economy. Generalize `SITE_ROOT/releases/<ts>/` + `current` to `SITE_ROOT/<dashboard>/releases/<ts>/` + `<dashboard>/current`. Keep the `os.replace()` symlink swap and the atomic-write rule (§1.1) exactly as they are. |
   | `sync_n8n.py` (53 vs 55 lines) | Near-identical; one copy, dashboard-parameterized. |

   *Explicitly out of scope.* Each dashboard's `fetch_*.py`, `build_data_files.py`,
   `db.py`, and `validate_snapshots.py` stay in their own repos — those are
   dashboard-specific data logic, and `validate_snapshots.py` validates that
   dashboard's own snapshot contract. Folding them in would be a different and much
   larger decision than §1.3 made.

   *Acceptance.*
   - Route is `POST /run/{dashboard}/{job}`; unknown dashboard and unknown job both
     404, distinguishably.
   - A dashboard registers its jobs and their commands through one documented entry
     point; nothing in the kit enumerates dashboard-specific job names.
   - `publish()` takes a dashboard key and writes under `SITE_ROOT/<dashboard>/`.
     Port `901Economy/tests/test_publish_site.py` alongside it.
   - Both repos' `tests/test_n8n_workflows.py` (registry ↔ `n8n/*.json` agreement)
     keep passing against the kit registry rather than a local `jobs.py`. Keep the
     registry importable without FastAPI — economy's `jobs.py` docstring records that
     pulling the web framework into that test broke it once, since `.[test]` does not
     install the `server` extra.
   - `python3 -m pytest -q` with a real Postgres (check the skip count), plus
     `npm run typecheck && npm test` if anything in `ui/` is touched (it should not be).
   - `README.md` module table + `CHANGELOG.md` `[Unreleased]` — this one is a code
     change, so unlike §1.3 itself it does get an entry.

   *Cutover risk — 901economy is live.* The `/run/<job>` → `/run/<dashboard>/<job>`
   change rewrites every `n8n/*.json` URL. `sync_n8n.py` upserts those by workflow
   name, so the workflow JSONs and the route change have to ship together, and the
   old unnamespaced route should keep working until all three repos are cut over.
   Per `AGENTS.md`'s pinning rule, the kit merges first, then each dashboard bumps
   `requirements*.txt` to the real merge SHA — three separate follow-up commits in
   three repos, not one.

   *Consequence worth naming:* this closes education's publish gap as a side effect.
   §1.3's table records that education has a pipeline container and a runner but no
   `publish_site.py` and an image-only `nginx.conf`, so it cannot serve a server-built
   release at all. It is not a separate ticket; it is what "one pipeline container"
   means.

2. [ ] **One nginx container serving every dashboard** (§1.3's second half). Companion
   to the above, separate PR — one logical change each. Economy's `nginx.conf` is the
   only one that implements §1.1 (volume root, image fallback, `/data/` block); it
   becomes the shared base, with a documented per-site include for anything genuinely
   dashboard-specific rather than a quietly edited per-repo copy. Needs the host check
   §1.1 already flagged and never resolved: whether separate Coolify resources can
   share the volume, or whether the builder has to write to a host bind mount. Confirm
   before building either half.

3. [ ] **Decide how kind-3 "document findings" surfaces are stored** — see
   `docs/DASHBOARD_SURFACES.md`, which has the measured grounding (justice's 18
   datasets: 10 trend, 3 finding-shaped), the four-kind surface taxonomy, a schema
   sketch, and the two open decisions. Raised by the justice migration because
   `doj_findings.json` and `juvenile_doj_monitor.json` cannot go in `indicators`
   (`NUMERIC value`, required `period`, and editorial fields with no source). **Blocks
   nothing in this repo yet** — it gates how justice's `doj-report` and `youth-justice`
   pages get rebuilt, so it wants deciding alongside the migration rather than after.
   The two questions: whether kind 3 lives in Postgres at all (D3's PR-gate reasoning
   may cover it at justice's volume), and whether milestones are their own table. No
   `ui/` extraction yet — two consumers, per §7.2; the doc says what to diff when the
   third arrives.


**Civic Engagement Suite & AI Story Engine (Parallel Track — see \`docs/CIVIC_ENGAGEMENT_SUITE.md\` for full 5-track WBS):**
- [ ] **Track 1:** Shared Type Definitions (\`src/types/engagement.ts\`, \`src/types/crossDomain.ts\`, \`src/types/storyboard.ts\`).
- [ ] **Track 2:** Core Action & Advocacy Components (\`AdvocacyDrawer.tsx\`, \`PrintFactSheet.tsx\` 1-pager generator, \`ToraRequestGenerator.tsx\`, \`CivicCalendarSync.tsx\`).
- [ ] **Track 3:** Scrollytelling Visualizers (\`StoryboardModal.tsx\`, \`SystemFunnelVisualizer.tsx\`, \`NeighborhoodCompositeLens.tsx\`).
- [ ] **Track 4:** AI Storyboard Generation Engine (\`contextAggregator.ts\`, \`storyboardEngine.ts\`, Next.js Edge route template).
- [ ] **Track 5:** Multi-Dashboard Integration across \`901education\`, \`901justice\`, and \`901economy\`.


**Self-contained, no blockers (found while working in 901education, 2026-08-28,
verified against this repo's own source — sequence 1 then 2, both gate
901education's planned `scripts/fetch_mscs_charter_report.py`):**
1. Split a `[pdf]` extra out of `[ai]` in `pyproject.toml`. `ai = [...]` currently
   bundles `pymupdf` with all three LLM SDKs (`anthropic`, `openai`,
   `google-generativeai`) plus `langextract`, unsplit — but `ai_extract.py` already
   selects exactly one provider at runtime (`AI_PROVIDER` or first available key,
   Anthropic → OpenAI → Google) and returns `{}` if none is configured. A consumer
   who only wants deterministic PDF text (`pymupdf`, no LLM, no API key) shouldn't
   have to install three unused SDKs to get it. Fix: `[pdf]` = pymupdf alone;
   per-provider `[anthropic]` / `[openai]` / `[google]` extras; keep `[ai]` as a
   convenience meta-extra pulling all of them. No new dependency, unblocks anything
   needing only deterministic PDF text.
2. Add table/repeating-row extraction to `toolkit/pdf_report.py`. Verified directly:
   `apply_regex_extractors()` runs one `re.search` per field (first match only) and
   `extract_metrics()` (regex-first, AI-fallback) both return exactly one value per
   schema field — there's no function returning a list of rows. Fine for scalar
   report fields, but blocks extracting a repeating table (901education's MSCS
   charter authorizer report: ~55 schools × 4 scorecard/rate columns). Needs a
   table extractor that returns a list of records, not a flat dict.

**Blocked on something outside this repo:**
- Push the `v0.2.0` tag — `git tag -a v0.2.0 351a0bbd -m "0.2.0" && git push origin
  v0.2.0`. Needs a normal machine; this environment's git proxy 403s on `refs/tags`
  specifically (confirmed from two independent sandboxed sessions — see
  `docs/PROJECT_NOTES.md`). Nothing depends on it: both current consumers pin the SHA
  directly, which is what actually guarantees immutability.

**Cross-dashboard follow-ups (work that lives in a sibling repo, tracked here so it
isn't lost — see `docs/PROJECT_NOTES.md` for the grounding on each):**
- 901justice, 901education: backport the `ui/` package (`DataStatusPanel`,
  `SampleBadge`, the `DataStatus`/`resolveStatus` pair) now that 901economy has
  adopted it and run a real publish cycle on it — `docs/ARCHITECTURE.md` §7.2's own
  sequencing gate just cleared. Economy's adoption PR is the worked exemplar: add the
  npm dependency pinned to an immutable commit, `transpilePackages:
  ['civic-dashboard-kit']` in `next.config.js`, repoint import sites, delete the local
  `components/data-status/` copy. `SourceLine` stays out (§7.1 — an editorial change,
  not a mechanical dedup); chart/map primitives stay out (rule-of-three not met).
- 901economy: CI's Postgres service is `postgres:16`; the real instance (and this
  repo's own CI) is `postgis/postgis:18-3.6-alpine` (`docs/ARCHITECTURE.md` §8, item
  3). Small, mechanical — bump the service image, confirm the existing suite still
  passes unchanged. Not yet done as of 2026-08-22.
- 901justice: Bundle A (LangExtract-grounded extraction + a review gate for
  `parse_jail_pdf.py`) — a live gap per 901economy's own tracker (daily AI extraction
  auto-commits with no review today). **Not actionable yet** — gated on 901economy's
  own T3/LangExtract integration landing first (economy's Phase C, still open).
- 901education: Postgres migration — **in progress, started 2026-09-01.** Tracked in
  901education's own `docs/TASKS.md`, not duplicated here;
  `docs/prompts/store-migration-planning.md` is the planning prompt for it and for
  901justice's net-new build. The history question that gated planning is **answered
  by the user (2026-09-01): backfill the full ledger** — all 56,274 observations and
  22 `source_runs`, preserving each run's original `fetched_at` rather than stamping
  the migration date. Collapsing to current values or starting fresh were both
  rejected as breaking the append-only promise.
  - This repo's side of it: `postgres_store.Observation` gained optional
    `unit`/`row_key`/`dimensions` so education's finer grain fits one shared
    store module (see `CHANGELOG.md`). Its dedup policy
    (`observations_utils.record_run_deduped`) stays in education — one
    dashboard's rule, not toolkit code.
  - **Design correction worth remembering.** The first draft added `subject` and
    `grade` as named columns, justified on rule-of-three. That justification did
    not hold: rule-of-three covers *finer grain as a concept* (education is the
    second consumer of that), but education is the ONLY consumer of `subject`
    and `grade`, so by this repo's own rule those did not belong here. Left
    alone, `indicators` would accrete the union of three domains' vocabularies.
    Replaced with an open `dimensions` JSONB. `subject` was dropped entirely —
    checked against all 56,274 rows, it is uniquely determined by `indicator_id`
    and carries no information. The general rule: **anything derivable from the
    indicator id is not an observation field.**
  - `record_run()` likewise gained those six run-level provenance arguments,
    with `fetched_at` kept distinct from `started_at` so a backfilled run keeps
    its real date. Both halves of this repo's side are done; what remains is in
    901education.
- 901justice: same migration planning prompt, net-new Postgres build (no existing
  store module to migrate). Unlike education, no history question blocks it — this
  half is ready to delegate for planning today.

---

## Parked — tracked but not Next Up

Real, wanted work that isn't a priority queue entry — usually because a repo
convention (like rule-of-three) holds it out on purpose. Move an item up to Next Up
when its gate clears or the user asks for it directly.

- **Address points (individual locations) in the shared `geo` schema.**
  `geo.boundaries` (`docs/ARCHITECTURE.md` §4) is polygon-only: the schema column is
  `geometry(MultiPolygon, 4326)` and `toolkit.boundaries.load_geojson`'s insert
  hardcodes `ST_Multi(ST_GeomFromGeoJSON(...))` — verified directly, no point-geometry
  table or loader exists anywhere in `toolkit.geo`/`toolkit.boundaries` today.
  901education needs individual school locations (address points) plotted on a map,
  which no existing boundary layer captures — a school is a point, not a polygon.
  Only one dashboard has this need so far (checked `docs/PROJECT_NOTES.md` and this
  file for any other mention of point/address layers — none), so this is exactly the
  situation `AGENTS.md`'s rule-of-three convention normally holds out; kept here
  rather than in Next Up for that reason, not because the work isn't wanted. Needs a
  design decision when picked up: a new `geo.points` table paralleling
  `geo.boundaries`'s `(layer, geo_key, name, vintage)` shape with
  `geometry(Point, 4326)`, vs. some other structure — not decided here.

---

## Done — dated log

### 2026-09 — Civic Storyboard & Scrollytelling Engine shipped in `ui/storyboard/`
- `StoryboardPresenter.tsx` and `StoryboardModal.tsx` added to shared UI package.
- Standardized 4-slide arc (`StorySlideHumanContext`, `StorySlideIntersections`, `StorySlideRootCauses`, `StorySlideCivicAction`).
- Persona switcher (`resident`, `organizer`, `journalist`, `policymaker`) dynamically adjusts narrative depth and framing.
- Full keyboard (arrow keys/Escape) and mobile touch swipe navigation support.
- Vitest suite in `tests/ui/storyboard.test.tsx` (4 tests, all passing alongside data-status/source-line).


### 2026-08-27 — Doc fix: §6.1's zip `ST_IsValid` finding revisited in light of §6.2
- `docs/ARCHITECTURE.md` §6.1 stated the 2-of-31 self-intersecting zip polygons as a
  flat source-data-quality issue. §6.2 later found the same "nested shells" symptom on
  the municipality layer was actually a `toolkit.geo.parse_shp` ring-nesting bug (fixed
  in PR #17), not bad source data — and a donut-shaped zip is exactly the shape that
  bug mishandles. Reworded §6.1 to flag that plausibility and point to §6.2, without
  claiming it's confirmed: re-verifying needs 901justice's original shapefiles, which
  this repo doesn't have. Doc-only change, no code touched.

### 2026-08 — `geo.boundaries`: the shareable-layer loaders
- `toolkit/boundaries.py` + `scripts/load_boundaries.py` (PR #12) — loads a GeoJSON
  `FeatureCollection` into `geo.boundaries`, upserting on `(layer, geo_key, vintage)`
  per the table's `UNIQUE` constraint. Loads 901justice's six shareable
  district/zip layers. MPD ward/station layers deliberately left unloaded — parked,
  see `docs/PROJECT_NOTES.md`.
- `scripts/fetch_municipalities.py` + `toolkit.geo.filter_by_name` (PR #13) —
  converts Census TIGER Places and loads all seven Shelby County municipalities
  (`docs/ARCHITECTURE.md` §5/§6.2). TIGER has no county-level cut, so this converts
  the statewide file and filters by name; refuses to write a partial result if any of
  the seven is missing.
- `toolkit.geo.nest_rings`/`signed_area`/`point_in_ring` (PR #17) — fixed `parse_shp`
  not nesting interior rings as holes, so an enclave rendered as a separate solid
  polygon instead of a hole in its parent. Found by cross-referencing 901economy's
  independent discovery of the same bug; corrected §6.2's earlier mischaracterization
  of the symptom as source-data noise. `parse_shp`'s return shape is unchanged.

### 2026-08 — Shared infrastructure decisions recorded in `docs/ARCHITECTURE.md`
(Not all done in this repo's own sessions — some landed via 901economy's
architecture-review PRs against this file. Listed here as the record of what's
decided, not a claim of authorship.)
- §1 — every dashboard's store is Postgres; §1's "what selects Postgres specifically"
  subsection records the four reasons that actually justify it over server-side
  SQLite (PostGIS, a shared `geo` across repos, concurrent writers, transactional
  approvals) rather than leaving "volume" as the stated reason.
- §1.1 — delivery is a volume-generated static export, not committed to git; the
  mechanism is spelled out concretely (`build_data_files.py` →
  `validate_snapshots.py --strict` → `next build` → atomic swap) after an external
  review read an earlier draft as "fetch JSON in the browser," which it is not.
- §1.2 — the container boundary between a dashboard's public site and the pipeline
  container is audience (public artifact vs. internal application), not language.
- §7.2 — the `ui/` package was extracted but not adopted anywhere for a while; records
  the actual byte-diff measurement and the adoption sequencing rule (economy first,
  alone, before any backport).
- Housekeeping this repo's own AGENTS.md/TASKS.md/PROJECT_NOTES.md (this file) now
  exist; see the skill's "who owns what" section for the split.

---

## Older items, pre-dating this file's Next Up convention

See `docs/ARCHITECTURE.md`'s own section numbering for anything not listed above — it
is the canonical record of shared-infrastructure decisions and is kept current
independently of this task list.
