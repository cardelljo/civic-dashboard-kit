# civic-dashboard-kit Task Tracker

Living task list for the shared toolkit behind 901justice, 901education, and
901economy. Read `AGENTS.md` first, then `docs/ARCHITECTURE.md` for the why behind any
shared-infrastructure item. **Next Up** below is the entry point for "what should I
work on" — the rest of this file is a dated history of what shipped and why, kept for
context, not a queue to work top-to-bottom. Update checkboxes as you go, and add a
dated entry under "Done" when you finish anything nontrivial.

---

## Next Up

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
- 901education: Postgres migration — decided direction (confirmed 2026-08-23), not
  started. Tracked in 901education's own `docs/TASKS.md`, not duplicated here;
  `docs/prompts/store-migration-planning.md` is the planning prompt for it and for
  901justice's net-new build. **Do not plan education's NDJSON-history-backfill
  question without the user** — it's a data-integrity call (does losing the ledger's
  history silently break the append-only promise this project makes to readers), not
  a coding decision.
- 901justice: same migration planning prompt, net-new Postgres build (no existing
  store module to migrate). Unlike education, no history question blocks it — this
  half is ready to delegate for planning today.

---

## Done — dated log

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
