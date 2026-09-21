# Dashboard surfaces: what the fact table holds, and what the off-shoot pages need

**Status: open question with a recommendation. Not adopted.** Tracked from
`docs/TASKS.md` Next Up. Raised by the 901justice Postgres migration (2026-09-21);
`docs/ARCHITECTURE.md` §1.3's "justice is the lens" subsection is why it is being
answered now rather than after the migration.

## Why this exists

The schema every dashboard runs — 901economy's `db/schema.sql`, copied by
901education — is six tables, and all six describe a **numeric observation**:
`geographies`, `sources`, `indicator_defs`, `source_runs`, `approvals`, `indicators`.

Nothing has tested that assumption yet, because every page economy and education have
built is either the main dashboard or a filtered view of the same fact table.
901justice tests it immediately.

## Measured, 2026-09-21 — 901justice's 18 committed datasets

| Shape | Where |
|---|---|
| Trend series (arrays of dated points) | 10 datasets — `jail.trend`, `crime.monthlyTrend`/`yearlyComparison`, `traffic_stops.monthlyTrend`, `traffic_citations.monthlyTrend`, `911_performance.monthlyTrend`, `community.monthlyMentalHealthCalls`/`blsUnemploymentTrend`, `school_crime.yearlyGroupAOffenses`, `fbi_cde_benchmarks.rows` |
| Scalar / point values | `summary`, `equity`, `court_aoc`, `da_prosecution`, `tract_context`, `accountability` |
| **Finding / milestone records** | **3 datasets** — `doj_findings` (`findings`, `responseMilestones`), `juvenile_doj_monitor` (`relativeRateFindings`, `milestones`, `reports`), `tbi_tops` (`themes`) |

The first two rows fit `indicators` as it stands. The third does not, and not in a way
a JSONB column fixes.

## Why a finding is not an observation

`indicators` is keyed `(indicator_id, geography_id, period, demographic_group)` with a
`NUMERIC value`. A `doj_findings.findings[]` record is:

```
id, category, headline, valueLabel ("866,164" — a string),
detail, publicMeaning, dashboardGap,
responsibleEntities[], monitoringStatus, monitoringStatusLabel
```

- **No numeric value.** `valueLabel` is display text.
- **No period.** The report covers January 2018 – August 2023 and was published
  2024-12-04: a range plus a publication date, not an observation period.
- **`publicMeaning` and `dashboardGap` are editorial**, written by this project's
  authors, not extracted from the source.

Forcing this into `dimensions` JSONB would put the whole record in the JSONB column and
use none of the table's keys, at which point the table is contributing nothing.

**The hybrid case is the interesting one.** `juvenile_doj_monitor.relativeRateFindings`
cites an RRI of 4.45 for 2016. That number *is* an observation and belongs in
`indicators`. The narrative built around it is not. Findings and indicators
cross-reference each other; they are not alternatives, and a design that makes them
alternatives will force one of them to be stored badly.

## Four kinds of surface

| Kind | Examples | Backed by | Store |
|---|---|---|---|
| 1. **Main dashboard** | all three `app/page.tsx` | the fact table | Postgres — settled |
| 2. **Data deep-dive** | education `charter-schools`, `schools` | a filtered slice of the same fact table | Postgres — settled; no schema work, a query and a build target |
| 3. **Document findings** | justice `doj-report`, `youth-justice` | finding records, milestone timelines, compliance ratings, quotes with page cites | **open — this doc's subject** |
| 4. **Editorial / explanatory** | justice `system-map`, `glossary`, `loved-one-help`, `agency-gaps`; education `story`, `glossary` | prose, hardcoded in `.tsx` or a `lib/*.ts` module | **recommendation: stays in git** |

Kind 4 is stated explicitly because "move the data to Postgres" invites moving all of
it. Editorial copy in a database gains nothing — no pipeline writes it, there is no
provenance to record and no cadence to track — and it loses the review surface a PR
diff gives it. `901justice/app/agency-gaps/page.tsx` imports no data at all today, and
`901education/app/story/page.tsx` reads a hand-written `lib/stories.ts`. Both are
correct as they are, not gaps to close.

Kind 2 deserves one note: it is the cheap kind, and justice's `youth-justice` page is
currently kind 3 (it reads `juvenileDojMonitorData`) where a slice of it could be kind
2. Worth checking during the migration whether part of that page is really an
indicator query.

## Recommendation for kind 3

Findings are neither editorial nor observations. They are **document-derived records
with provenance** — an extraction from a PDF, reviewed by a human before publication.
That is exactly what the T3 tier and the `approvals` gate exist for, which argues for a
store rather than git.

A sketch, deliberately sharing the existing provenance spine rather than inventing a
second one:

```
findings(
  finding_id, dashboard, subject_key,      -- 'doj-mpd-2024', 'juvenile-court-monitor'
  category, headline, value_label,
  detail, public_meaning, editorial_note,
  responsible_entities JSONB,
  status, status_label,
  source_key → sources, source_url, source_page,
  quote,
  indicator_ref,                           -- optional link to the indicators cell it describes
  run_id → source_runs,
  retrieved_at
)
```

plus something for the dated-event timelines (`responseMilestones`, `milestones`) —
either its own table or a `kind` discriminator on `findings`. Which one should be
decided against justice's three actual files, not assumed here.

**What it buys:** the DOJ page's figures pass the same review gate as everything else,
`source_runs` records the extraction, and a finding can cite the indicator cell it
describes. Justice's `lib/types.ts` already has `report-backed` in its `DataStatus`
union — the same idea, arriving early and without a store behind it.

**What it costs:** a second content model in the schema, and the `_meta` /
`DataStatus` contract has to cover it.

### Not decided — two things to settle first

1. **Whether kind 3 goes in Postgres at all**, or stays git-committed JSON with the
   review gate applied by PR. `901justice/PLATFORM_ARCHITECTURE_DECISIONS.md` D3's
   reasoning bears directly on this: justice's volume is tiny, the database is being
   adopted for staff usability rather than scale, and a PR-based gate was already
   judged technically sufficient at this volume. A findings page updated once or twice
   a year may be the case where that holds.
2. **Whether milestones are a separate table or a `kind` on `findings`.**

## The template question

Kinds 3 and 4 are where three dashboards will each otherwise invent a layout, which is
the `SampleBadge` story again (57/58/58 lines across three repos before anyone looked).

Rule-of-three, honestly applied: kinds 3 and 4 have **two** consumers today — justice's
`doj-report`/`youth-justice` and education's `charter-schools`/`story`. Per §7.2's
precedent that is not yet an extraction. But it is the moment to *look*, and looking is
cheap now because both pairs are already built: a two-way diff of their page chrome is
possible today, where `SampleBadge` was only diffed after the third copy existed.

**Recommendation: no `ui/` component yet.** When justice's DOJ page is rebuilt against
whatever kind 3 resolves to, diff its chrome against education's `charter-schools` and
record the shared structure in this doc. Extract on the third consumer, with the
comparison already done rather than starting from three drifted copies.
