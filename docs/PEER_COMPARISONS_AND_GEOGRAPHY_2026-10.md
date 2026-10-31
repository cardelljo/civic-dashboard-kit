# Peer comparisons and geography labels (2026-10)

An audit of where the three dashboards give peer-place context, and a design for telling
readers which area a figure covers (city, county, school district, metro). Done
2026-10-31; recommendations approved by the owner (Cardell Orrin) the same day. Tickets
live in each repo's task list; this file is the shared reasoning they point to.

## Findings

- **No dashboard tracks population over time,** and no ticket asked for it. Population is
  only plumbing: economy's top-50 metro ring is ranked from Census population estimates
  (2023 vintage, Memphis metro 46th at 1,335,674); justice's TBI agency file carries each
  police agency's population for per-100k rates. Justice's crime briefing found the city
  of Memphis lost 6.4% of its population from 2019 to 2025 (651,073 to 609,647), which turns
  a 3.7% fall in homicides into a 2.9% rise in the homicide rate. That never reached a page.
- **Peer comparisons were ticketed on economy only.** Built today: economy's Chamber
  10-metro charts (IT wages, IT growth, NIH per resident, per-capita income, GDP headline)
  and its Tennessee-county PILOT ring; justice's Tennessee police-agency comparison and FBI
  Crime Data Explorer state/U.S. rates; education's per-pupil spending vs. Nashville,
  Hamilton and Knox districts.
- **Built but unused:** 901education `data/peer_comparisons.json` (MSCS vs. those three
  districts, ELA and math) renders nowhere. Economy's `KpiCard` has a `comparison` prop no
  section passes. This repo's `SourceLine` has a `geography` field no dashboard uses.
- **NAEP big-city results:** MSCS (as "Shelby County") took part in the Trial Urban
  District Assessment in 2017, 2019 and 2022 and did not take part in 2024 (per NCES's TUDA
  pages; verify on nces.ed.gov before building). No repo mentioned it.

## Decisions (owner, 2026-10-31)

1. **Peer ring:** justice and education use economy's Chamber 10-metro ring for city-level
   peer comparisons for now (Memphis, Nashville, Indianapolis, Kansas City, St. Louis,
   Milwaukee, Louisville, Oklahoma City, New Orleans, Birmingham). One ring per chart still
   holds; Tennessee peers and state/U.S. benchmarks remain separate rings.
2. **Population goes on economy,** as city, county and metro trends plus peer-metro growth.
3. **Justice turns the population finding into a headline or section** (rates, not counts,
   against a 2019 baseline) that links to economy's population section: the series' first
   cross-dashboard link.
4. **Geography tags are a kit component abstracted by jurisdiction,** not hardcoded to
   Memphis, because education is adding Nashville (MNPS) and more jurisdictions will follow.
5. **City-to-county-to-metro navigation is deferred to phase 3** (the shared `/where`
   page). Until then, compare levels only where a measure exists at two or more of them.

## Geography tag design (for the kit ticket)

Labels come from data plus a jurisdiction config, never from strings typed into a page.

- **Levels are generic.** A fixed enum describes *what kind* of area a figure covers:
  `city`, `county`, `school-district`, `metro`, `state`, `nation`, plus `peer-ring` for a
  comparison chart. Data carries the level (economy already stores `geography_type` per
  row; justice and education add it to each file's `_meta` or row).
- **Names come from a jurisdiction config.** Each dashboard (and each jurisdiction within
  one, e.g. education's Memphis and Nashville) supplies display names and one-line notes
  per level, for example `{ city: "City of Memphis", county: "Shelby County",
  "school-district": "MSCS", metro: { name: "Memphis metro", note: "9 counties in TN, MS
  and AR" } }`. A new jurisdiction is a new config entry, not new components.
- **One component renders it:** a small chip beside each figure and chart title (via
  `SourceLine`'s geography slot), with a tap-for-more note. No explanatory prose on the
  page.
- **A "Which <place>?" table on each Data Sources page,** generated from the same data and
  config: each measure, its level, and why (the level the source publishes).
- **Optional check:** a headline whose wording names one level while its data row is
  another fails review.
- **Place ladder:** where a measure exists at two or more levels (poverty, income,
  population, unemployment), a small City / County / Metro bar strip, using the chart
  grammar's "two bars: us vs. benchmark" form.

Rule-of-three: all three dashboards need the tag, so it qualifies as kit code.

## Tickets

| Repo | Ticket |
| --- | --- |
| civic-dashboard-kit | `docs/TASKS.md` Next Up: "Geography tags, abstracted by jurisdiction" |
| 901economy | `docs/TASKS.md`: "Peer comparisons and population (2026-10-31)" |
| 901justice | `MESSAGE_FIRST_TRUST_HARDENING_BACKLOG.md`: "Peer comparisons and population (2026-10-31)" |
| 901education | `docs/TASKS.md`: "Peer comparisons (2026-10-31)" |

## Sources

- NCES, [Trial Urban District Assessment](https://nces.ed.gov/nationsreportcard/tuda/) and
  [NAEP snapshots](https://nces.ed.gov/nationsreportcard/snapshots/) (2024 non-participants).
- Repo files on each `main`, 2026-10-31: economy `PLAN.md` jobs 1, 2, 9, 15, 16; justice
  `docs/CRIME_DECLINE_BRIEFING_2026.md` and `docs/DASHBOARD_LESSONS_FROM_PRESS_REVIEW.md`
  (item 10); education `data/peer_comparisons.json`; this repo's `ui/SourceLine.tsx`.
