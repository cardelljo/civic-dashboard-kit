# Redesign direction for the series (2026-10-28)

**Status: direction set by the owner (Cardell Orrin, 2026-10-28); build not started.**
Extends `docs/SECTION_PATTERN_AND_HEADLINE_REVIEW.md` rather than replacing it: the section
pattern and headline records stay, and this doc sets the page model, the order of work and
the chart grammar around them. Tracked from `docs/TASKS.md` Next Up.

## How it was reached

Every page of all three dashboards was captured at desktop and phone width (22 pages, as of
901justice `e6c99a4`, 901education `085230a`, 901economy `3bb42c2`). Five reviewers — a
graphic designer, a UX lead, a Memphis parent, an advocate and a reporter — reviewed them,
then debated to a consensus; dataviz, infographic and story specialists joined later rounds.
Persona write-ups and the screenshot archive live in the project's shared files, not in a
repo, so the archive can grow with each phase.

**Verdict:** keep the headline unit; rebuild the front door and the page model around it.
This is a rearrangement, not a visual redesign. The visual system, components and headline
records carry over.

## Who it is for and what they should do

- **Audience:** residents with no data background come first, mostly on phones, often
  arriving from a shared link. Funders, reporters and officials come second.
- **Visitor path:** understand the data, then find something worth sharing (on social media
  or with an official), then, where a real ask exists, connect to it. Not every section has
  an ask; every section can be shared.
- **On-page text:** anything that pulls focus from the data has to earn its place. Method
  and sourcing detail moves to an info bubble or the sources page.
- **Placeholders:** none on the page. One collapsed "coming soon" line is allowed, listing
  only ticketed items.

## Page model (same on all three)

```
/                 Overview: one-line stance, "four things to know" strip, place picker
                  ("Your ZIP or your child's school"), topic tiles (headline + number +
                  small graphic -> topic page), overview graphic
/topics/<topic>   Headline -> anchor + trend -> supporting numbers -> explorer (time,
                  group, place) -> "What we're asking" -> folds (limits, how we know)
/where            One shared map and place lookup, ?topic= and ?place= prefilled
/stories/<story>  Guided walkthroughs that cite headline records
/data             Sources, gaps and who holds them, methods, downloads, glossary
/act              Take action, help pages, who to contact
/ask  (later)     A plain-language question becomes a view assembled from topic, place
                  and headline records
```

The home page samples the data broadly enough that nobody misses what matters; topic pages
give depth. Justice splits into topic pages first; education and economy stay single pages
with anchor links until their headlines are done.

## Phases

Cumulative; each ships on its own.

0. **Trust sweep (small).** Strip internal language from rendered pages (job numbers,
   "this session", repo file names, fetch logs) and add a CI check that fails on it; cut
   method and justification prose from section bodies; one figure and one label per
   question; drop KPI cards that repeat a headline anchor; show data dates, not build dates;
   collapse placeholders.
1. **Finish the section unit.** Trend beside each anchor with one comparison; chart titles
   that state the finding; a "What we're asking" band only where the dashboard's brief has a
   position; copy-citation, share card, CSV and link anchor on each headline; one graphic
   per headline.
2. **Front door.** The strip from approved headlines, the place picker, topic tiles, the
   same nav shape on all three sites, a visible Take Action on phones.
3. **Topic pages**, justice first; the shared `/where` map; `/data`; full-width stories; an
   action page per dashboard.
4. **"Ask the dashboard."** Topic pages and places with their own addresses, plus
   fact-checked headline records, are its raw material. Views are assembled from them, not
   written, which is why the static sites stay and "ask" becomes one route.

Held headlines are on phase 2's critical path: each dashboard's strip needs its strongest
sections cleared.

## Chart grammar

A small fixed set of forms. The big number becomes one form among several, not the default.

| Form | Use it for | Phone |
|---|---|---|
| Big number + one comparison | A single fact that is the whole point | Number first, full width |
| Trend line, end-labeled, one annotation | Up or down over time (5+ points) | ~160px tall, minimal axes |
| Two bars: us vs. benchmark | A rate against a benchmark | Horizontal, values on bars |
| 100-dot grid | A share people should feel ("fewer than 1 in 100") | 10x10, ~300px |
| Slope / before-after | Change between two moments or groups | Two labeled columns |
| Share pair | Disparity: share of an outcome vs. share of the population | Two stacked bars, bracket |
| Map or ranked place strip | Where | Map above a ranked list |
| Steps ("leaky pipe") | A sequence of stages | Vertical steps |

**Rules:**
- No two adjacent sections use the same form.
- One big number per section; supporting figures are different numbers.
- One motion moment per page; reduced-motion users see the final state.
- Color carries meaning only: the site accent for the place, grey for the benchmark, amber
  reserved for data gaps.
- Every graphic can be shared as an image with its source and date.
- No hover-only tooltips.
- No Sankey until data supports one honestly.

**Infographic layer:** at most one per section, an exact number always printed beside a
pictogram, and no real-sounding quotes unless sourced. Each dashboard gets one signature
graphic (education: 100 students filling stage by stage; justice: the path of a charge;
economy: a receipt for abatement dollars, once per-county data exists).

**Share cards:** one template that renders from an approved headline record (claim,
graphic, source, date, link). A card missing any of these doesn't render.

## Stories

A story follows one composite person through the system, like a pipeline graphic for one
life. Rules:
- Label it as a composite up front: the person is invented, every number is real.
- Use no invented quotes.
- Draw only on the story's own dashboard.
- Say in one line when a pipeline joins rates from separate releases rather than tracking
  one cohort.

Two versions are being tried: story-led, and a data-led scroll beneath it. Education goes
first; the same template carries to justice (arrest to disposition) and economy (one
household's paycheck).

## What stays where

- Framing, stance and each section's wording live in each dashboard's private
  `docs/NARRATIVE_BRIEF.md`, never here.
- This doc carries only the shared design.
- Per-dashboard phase tickets live in each dashboard's task list.
