# Section pattern, headline records, and headline review

**Status: proposed, not adopted.** Written 2026-09-24 from a design review of all three
dashboards' home pages (rendered at desktop and phone width, measured, and audited
section by section) and a round of mockups the owner reviewed. Tracked from
`docs/TASKS.md` Next Up. Nothing here is built yet; the quick fixes the review surfaced
(contrast, internal jargon on public pages, the kit's Tailwind scan in economy, the
FRED thousands scale, stale month labels) already shipped separately as
901economy#67, 901justice#53 and 901education#66.

This doc covers four things that depend on each other, in build order:

1. **The section pattern** — how every home-page section reads, the same way on all
   three dashboards.
2. **Headline records** — the takeaway heading, anchor number, and context line of a
   section stored as data with provenance, not hardcoded in a `.tsx` file.
3. **Headline review** — a fact check, then a narrative review, then a human decision,
   in the admin review queue `docs/ARCHITECTURE.md` §1.2 already places in the pipeline
   container.
4. **The rotating front strip** — "four things to know" at the top of each dashboard,
   drawn from approved headline records.

## Why — measured, 2026-09-23

The owner's read was that the eye has nowhere to settle. The measurements agree:

- **The type scale is inverted on all three dashboards.** KPI labels are 12px uppercase
  in muted slate; the numbers under them are 30px bold; the section `h2` is 20px — the
  heading is *smaller* than the numbers inside its own section. Education's home page
  carries 46 numbers at 24px or larger in 57 identical white cards.
- **Squint test (page rendered at 0.3 scale):** headings vanish; what survives is
  whatever has color — justice's amber data-gap banners, education's pipeline bars.
  The numbers themselves blur into identical grey boxes: loud individually, none in
  charge.
- **Headings name topics, not findings.** "Jail Population & Conditions", not what is
  true about the jail. The exceptions were the strongest parts of the sites: education's
  "Our kids are growing. The system isn't giving them enough to grow into", the Stories
  slides, and justice's DOJ findings, which were buried as `h3`s.
- **Justice is long and boxed.** 24,487px at desktop, 49,322px on a phone. Police
  Accountability alone was 5,347px with 57 framed boxes; the Jail section used eight
  accent colors on its big numbers.
- **Trends are rare and detached.** 3 of economy's 41 KPI cards showed a trend (mostly
  because most series have one vintage so far); chart titles name the metric
  ("Monthly Crime Trend") instead of what the chart shows.

## 1. The section pattern

Every home-page section reads in this order. Nothing is removed from the page; what
does not fit the first four steps folds.

| Step | What | Spec |
|---|---|---|
| 1 | Topic label | 13px, 700, uppercase, tracked; names the topic and the as-of period (`JAIL · JULY 2026 REPORT`). |
| 2 | Takeaway heading | The loudest words in the section: 32px display face (24px on phones). One sentence stating what is true, from a **headline record** (§2). |
| 3 | Anchor | One number per section at 56–64px (48px on phones), in the body face, with its trend beside it (a small chart with hover, or a sparkline) and **one** comparison — state, peers, or last period, never several rings at once. |
| 4 | Supporting numbers | Three or four, as statements: the number at 28px on its own line, then the sentence continuing below it, lowercase, 16px, dark ink (`2,584` / `people booked into the jail in July`). The label must carry the same ink as the number — this is the fix for labels vanishing at a distance. |
| 5 | Folds | Closed by default, one click away, never deleted: "What this doesn't tell us" (data gaps, with who holds the data), topic-specific detail, "How we know" (source and method). |

Rules that hold across the pattern:

- **Chart titles state the finding**; the metric name moves to the subtitle.
- **Color carries meaning only**: red worsening, green improving, amber dashed border for
  a data gap — each with an icon or text, never color alone. No decorative accent
  colors on numbers.
- **Words lead, numbers prove**: headings in the display face, numbers in the body face.
- **Contrast floor**: nothing readable in `slate-400` on white (2.56:1); `slate-600`
  (`#475569`) is the lightest body-text tone.
- **Phones**: a number must be visible on the first screen.

**Same pattern, different emphasis per dashboard** — consistent in how information is
related, not identical in what is emphasized:

- **901justice: the gap is often the finding.** Where the data is not published, the
  anchor is the gap itself — styled as a finding (amber dashed), naming who holds the
  data and what to ask for — not a repeated banner.
- **901education: the pipeline is the anchor.** The existing "100 students enter
  kindergarten" visual becomes the Where We Stand section, with a state marker on each
  row and a click-to-select detail panel (value, three-year trend, state comparison,
  source). Its footnote keeps the honesty: each row is a separate measure, not one
  cohort followed over time.
- **901economy: the two-clause finding is the anchor.** `TwoClauseFinding` ("X, but Y"
  — both clauses required) doubles as a chart toggle (one axis at a time, never two
  scales), followed by a comparison that answers "is that a lot?" within one ring.
  Economy's "Coming soon" measures collapse to a single line instead of a grid of
  placeholder tiles.

**Extraction.** All three dashboards already carry their own KPI-card copy
(901economy's `KpiCard.tsx` was generalized out of 901education's `SnapshotSection.tsx`;
justice's `HeroMetrics.tsx` inlines another). Adopting this pattern on the third
dashboard is the rule-of-three trigger `docs/ARCHITECTURE.md` §7.2 names for `KpiCard`
and `TrendChart`. The sequencing below builds the pattern in one dashboard first as the
reference implementation and extracts when the second adopts it, with the diff already
done — the §7.2 lesson rather than three drifted copies.

## 2. Headline records

A section's takeaway heading, anchor, and context line change when the data does and
carry an editorial choice that someone approved. That is neither an `indicators` row
(`docs/ARCHITECTURE.md` §1, "What belongs in an `Observation`") nor editorial copy that
belongs in git (`docs/DASHBOARD_SURFACES.md`, kind 4). It is closest to the kind-3
*finding* records in `docs/DASHBOARD_SURFACES.md`: document-derived, human-reviewed,
with provenance — and it should share that model rather than invent a second one.

Sketch, deliberately parallel to the `findings` sketch in `DASHBOARD_SURFACES.md`:

```
headlines(
  headline_id, dashboard, section_key,          -- 'jail', 'courts', 'where-we-stand'
  heading,                                      -- the takeaway sentence
  context_line,                                 -- optional; required when the review says so
  anchor_ref,                                   -- the indicators cell (or findings row) the heading rests on
  supporting_refs JSONB,                        -- cells cited by the supporting numbers
  as_of,                                        -- the data vintage the wording is true for
  status,                                       -- draft | fact_checked | in_review | approved | retired
  featured_rank,                                -- NULL, or its slot in the front strip (§4)
  fact_check JSONB,                             -- pass/fail per check, with the values compared
  narrative_review JSONB,                       -- scores, notes, proposed reframes (§3)
  decided_by, decided_at, decision,             -- publish | publish_with_context | reframe | hold
  supersedes → headlines,
  created_from                                  -- 'pipeline' | 'staff'
)
```

Two properties matter more than the column list:

- **A heading is tied to the cell it describes.** When a newer run supersedes that
  cell, the heading is automatically **stale** — it drops back to review and stops
  being featured, rather than asserting a number the page no longer shows.
- **Approval is recorded, not implied.** The public page can show that a heading was
  reviewed, when, and against which data vintage.

**Interim, before the queue exists.** The admin review queue lands after the container
consolidation (Next Up items 1–2). Until then a dashboard can adopt the section pattern
with headline records as a committed `data/headlines.json` in the same shape, reviewed
by PR — the review-by-PR route 901justice's D3 already judged sufficient at its volume.
Moving the records to Postgres later is a load, not a redesign.

**Bearing on `DASHBOARD_SURFACES.md`'s open question 1** (whether kind 3 lives in
Postgres at all): headlines are a finding-shaped record that changes on every data
refresh, not once or twice a year. That is a reason to put finding-shaped records in
Postgres behind the review queue. It argues toward one answer; it does not decide it.

## 3. Headline review

```
Draft ─► Fact check ─► Narrative review ─► Human decision ─► Published
(pipeline   (pass/fail,     (scored against     (review queue:     (with its
 or staff)   gates the       the dashboard's     publish / publish   review
             rest)           narrative brief)    with context /      record)
                                                 reframe / hold)
```

### The rule that protects credibility

**The review chooses emphasis and context. It never removes a figure or changes a
number.** A heading that fails the fact check cannot be published, whatever its
narrative score. A figure that cuts against a dashboard's argument stays on the page —
as a supporting number with a context line, or in a fold — it just does not become the
heading unless it earns it. This is the same commitment as "gaps shown, never filled in"
and `TwoClauseFinding`'s both-clauses-required rule: the series' credibility with
readers who disagree with it is the thing the advocacy depends on.

### Step 1 — Fact check (gate)

Automated where it can be, human-confirmed where it cannot:

- Every number in the heading and context line resolves to its `anchor_ref` or a
  `supporting_refs` cell, at the stated `as_of`, after rounding.
- Quantifier words match the value: "most" > 50%; "about a third" within ±3 points of
  33.3%; "doubled" ≥ 2.0×; "fewer than 1 in 100" < 1%.
- Unit honesty: counts are not described as people or cases (the AOC court data is
  counts of charges; one case carries several), rates are not described as totals.
- Causal language ("because", "led to", "caused") is not allowed unless a cited source
  makes the causal claim.
- No cross-dataset inference the data cannot support (e.g. dismissed court counts and
  the jail population are different units, periods, and people).
- Each dashboard's own display rules from its `AGENTS.md`, as checks — e.g. 901economy's
  "current dollars for levels, inflation-adjusted dollars for growth". (The first mockup
  of economy's heading, "doubled on paper", broke that rule; a check would have caught
  it.)

### Step 2 — Narrative review

A model drafts the review; a person decides. The model reads the draft heading, its
cited values, and the dashboard's **narrative brief** (below), and returns scores, a
note per score, how the heading could be quoted against the dashboard's purpose, and up
to three reframes, each of which must itself pass the fact check. It runs in the
pipeline container beside the extractors, writes into `narrative_review`, and **never
publishes anything on its own.**

Rubric, each 1–5 (5 best):

| Dimension | 5 means | 1 means |
|---|---|---|
| **Context** | A resident draws the right conclusion from the heading plus its context line. | True but misleading on its own. |
| **Narrative fit** | Advances the dashboard's thesis as stated in its brief. | Hands an opposing frame a ready-made quote. |
| **Misuse resistance** | Hard to clip into an opposing argument without changing its meaning. | Can be screenshotted as-is to argue the opposite. |
| **Clarity** | A resident gets it in about five seconds. | Needs the chart to decode. |

Decision guidance — recommended to the reviewer, not automatic:

- Fact check fails → **hold**.
- Narrative fit ≤ 2 **or** misuse resistance ≤ 2 → **reframe**; the original figure
  stays as a supporting number with a context line.
- Context ≤ 3 but fixable by one sentence → **publish with context**.
- Otherwise → **publish**.

### Worked example — 901justice, Courts (TN AOC FY2024–25, Shelby County Criminal Court)

15,841 criminal counts were disposed: 9,618 dismissed or nolle prossed (60.7%); 3,587
guilty pleas as charged plus 987 to a lesser charge (4,574, 28.9%); 97 convictions and
55 acquittals at trial (152, 0.96%); 653 diversions.

| Candidate heading | Facts | Context | Fit | Misuse | Clarity | Decision |
|---|---|---|---|---|---|---|
| "Most criminal charges closed last year were dismissed." | pass | 2 | 1 | 1 | 5 | **Reframe.** True, but invites the "lenient DA and judges" reading, and says nothing about why charges are dropped. |
| "6 in 10 charges filed didn't hold up in court." | **fail** | 3 | 4 | 3 | 4 | **Hold.** Overclaims: many counts are dropped as part of a plea to another count, which is not the same as a weak charge. The reform-friendly draft is the one that failed the fact check. |
| "Fewer than 1 in 100 criminal charges were decided at trial." | pass | 4 | 5 | 4 | 4 | **Publish with context.** Context line: "Counts, not cases or people — one case can carry several counts." 60.7% stays as a supporting number. |

Scores here are illustrative until the brief they are scored against is approved.

### Narrative briefs live in the dashboard repos, not here

The rubric's "narrative fit" is scored against a per-dashboard **narrative brief**:
thesis, frames and terms to use and avoid, anticipated opposing readings and how the
dashboard answers them, and audiences. **This repo is public; the dashboard repos are
private.** A messaging brief — especially its "anticipated opposing readings" — is
advocacy strategy and belongs with its dashboard, at `docs/NARRATIVE_BRIEF.md` in each
dashboard repo, owned by Stand for Children Tennessee. This repo holds only the
mechanism and the rubric. First drafts of all three briefs were written 2026-09-24 from
the dashboards' own docs (and, for justice, the Memphis & Shelby County Justice & Safety
Alliance's public materials) and are marked as drafts pending owner review.

## 4. The rotating front strip

"Four things to know" at the top of each dashboard's home page (mocked for justice:
jail population, violent crime, the pretrial data gap, the DOJ citation finding):

- Each tile is an approved headline record with `featured_rank` set: one heading, one
  number or one named gap, its as-of date, and a link to its section.
- **At least one tile may be a gap**, styled as a finding.
- A tile leaves the strip when its record goes stale (§2) or a newer record is approved
  for its slot. The strip never shows an unapproved or stale heading; with fewer than
  four approved, it shows fewer.
- Because the public sites are static exports (`docs/ARCHITECTURE.md` §1.1), rotation
  happens at publish time — the builder reads approved, featured records — not per
  visitor.

**Toward "ask the dashboard".** The owner's stated long-term goal is a reader typing or
saying what they want to know and getting a view assembled for them. Headline records
are that feature's raw material: each is a reviewed, sourced claim tied to its data
cell, its section, and its related cells. Building them as data now is what makes the
later feature an assembly problem rather than a writing problem. The query-driven
delivery it needs is exactly the case `docs/ARCHITECTURE.md` §1.1 names for revisiting
static export; nothing here decides that.

## Sequencing

1. **Adopt this spec** (owner decision), and approve each dashboard's narrative brief.
2. **Reference implementation in one dashboard**: the section pattern plus
   `data/headlines.json` reviewed by PR, one section at a time. 901justice is the
   natural first choice: it has the longest page and the most to gain, and the
   "justice is the lens" rule (`docs/ARCHITECTURE.md` §1.3) argues for shaping shared
   components against it rather than retrofitting it last.
3. **Extract `ui/` components** (section header, anchor-with-trend, supporting
   statements, fold) when the second dashboard adopts the pattern, with the diff
   against the first recorded here beforehand.
4. **Headline records in Postgres + the review queue** — after Next Up items 1–2, as
   part of the admin queue build rather than a separate app.
5. **Model-drafted narrative review** as a pipeline job writing into
   `narrative_review`.
6. **The rotating front strip**, once enough approved records exist to rotate.

## Open decisions (owner)

- Adopt the section pattern as the series standard?
- Approve (or rewrite) each dashboard's narrative brief — the rubric is only as good as
  what it scores against.
- Who is the "person decides" in step 4 — one approver per dashboard, or a named pair
  for anything featured on the front strip?
- Should the public page show a heading's review record (reviewed by whom, when), or
  only that it was reviewed?
