# Civic Engagement Suite & AI Story Engine: Project Specification & Master Task List

**Target Package:** `civic-dashboard-kit` (Shared UI & Toolkit Package)  
**Consumer Dashboards:** `901education`, `901justice`, `901economy`  
**Status:** In Development · Parallel Track  

---

## 1. Project Vision & Governance

### 1.1 Why This Lives in `civic-dashboard-kit`
The Civic Engagement Suite consists of modular frontend components, interactive advocacy tools, and narrative generation engines that are **domain-agnostic by design**. 

Housing this project in `civic-dashboard-kit` provides:
1. **Zero Code Duplication:** A single implementation of the `AdvocacyDrawer`, `StoryboardModal`, `PrintFactSheetGenerator`, and `SystemFunnelVisualizer` serves all three dashboards.
2. **Independent Release Velocity:** Features can be built, tested, and versioned via npm tags without disrupting daily data refreshes or annual TDOE updates in the individual dashboards.
3. **Clean Contract-First Architecture:** Each dashboard simply imports the components and passes domain-specific config and static JSON manifests.

---

## 2. Feature Architecture & Component Matrix

```
┌───────────────────────────────────────────────────────────────────────────┐
│                           CIVIC ENGAGEMENT SUITE                          │
│                                                                           │
│  ┌─────────────────────────┐  ┌─────────────────────────┐  ┌───────────┐  │
│  │   3-Tier Disclosure     │  │     Advocacy Drawer     │  │ Print 1-Pg│  │
│  │   (Summary/Context/     │  │   (Target Body, Asks,   │  │ Fact Sheet│  │
│  │    Provenance)          │  │    Testimony Script)    │  │ Generator │  │
│  └─────────────────────────┘  └─────────────────────────┘  └───────────┘  │
│  ┌─────────────────────────┐  ┌─────────────────────────┐  ┌───────────┐  │
│  │   TORA / Public Records │  │  Neighborhood Composite │  │ System    │  │
│  │   Request Generator     │  │  Lens (Cross-System)    │  │ Funnel    │  │
│  └─────────────────────────┘  └─────────────────────────┘  └───────────┘  │
│  ┌─────────────────────────────────────────────────────────────────────┐  │
│  │              Dynamic 4-Slide AI Storyboard Engine                   │  │
│  │   (Lived Reality -> Intersections -> Root Causes -> Civic Action)   │  │
│  └─────────────────────────────────────────────────────────────────────┘  │
└───────────────────────────────────────────────────────────────────────────┘
                                    │
       ┌────────────────────────────┼────────────────────────────┐
       ▼                            ▼                            ▼
 901education                  901justice                   901economy
 (MSCS / TDOE)                 (Courts / Jail / MPD)        (Wages / Housing)
```

---

## 3. Master Task List & Work Breakdown Structure (WBS)

### Track 1: Shared Type Definitions & Schemas (Foundation)
*Goal: Publish immutable TypeScript interfaces in `civic-dashboard-kit`.*

- [ ] **Task 1.1: Define Core Engagement Interfaces**
  - **Target File:** `civic-dashboard-kit/src/types/engagement.ts`
  - **Schema Scope:** `AdvocacyConfig`, `PolicyDemand`, `ResponsibleEntity`, `TalkingPointsScript`.
  - **Acceptance Criteria:** Strict typing, exported via package entry point with full JSDoc documentation.
- [ ] **Task 1.2: Define Cross-Domain Metric & Composite Lens Schemas**
  - **Target File:** `civic-dashboard-kit/src/types/crossDomain.ts`
  - **Schema Scope:** `CrossDomainMetric`, `NeighborhoodCompositeData`, `DemographicProfile`, `CompoundedEquityScore`.
  - **Acceptance Criteria:** Supports geography grains (`zip`, `census_tract`, `county_district`).
- [ ] **Task 1.3: Define AI Storyboard 4-Slide Structured Output Schema**
  - **Target File:** `civic-dashboard-kit/src/types/storyboard.ts`
  - **Schema Scope:** `StoryboardResponse`, `StoryboardSlideHumanContext`, `StoryboardSlideIntersection`, `StoryboardSlideRootCauses`, `StoryboardSlideCivicAction`, `AudiencePersona`.
  - **Acceptance Criteria:** Validated with Zod schemas for runtime response parsing.

---

### Track 2: Core Action & Advocacy Components
*Goal: Low-friction civic action tools ready to mount on existing metric cards.*

- [ ] **Task 2.1: Implement `AdvocacyDrawer` Component**
  - **Target File:** `civic-dashboard-kit/src/components/AdvocacyDrawer.tsx`
  - **Features:**
    - Slide-out mobile-responsive drawer with focus management.
    - Plain-language takeaway banner.
    - Responsible elected body info (schedule, chambers location, speaker signup link).
    - Categorized policy demands (Budget Ask, Policy Reform, Oversight Request).
    - 1-Click copy of a 3-minute public comment script.
  - **Acceptance Criteria:** Fully keyboard accessible (Esc to close, tab-trapped), WCAG 2.1 AA compliant.
- [ ] **Task 2.2: Implement `PrintFactSheet` 1-Pager Generator**
  - **Target File:** `civic-dashboard-kit/src/components/PrintFactSheet.tsx` & `print.css`
  - **Features:**
    - Dedicated `@media print` layout turning any metric or section into an 8.5x11 black-and-white canvassing flyer.
    - Includes QR code linking back to the live dashboard page.
    - Compact 3-point takeaway, meeting time/location, and organizer contact box.
  - **Acceptance Criteria:** Fits strictly on one printed sheet without awkward page breaks in Chrome/Safari print preview.
- [ ] **Task 2.3: Implement `ToraRequestGenerator` (Public Records Letter Generator)**
  - **Target File:** `civic-dashboard-kit/src/components/ToraRequestGenerator.tsx`
  - **Features:**
    - Modal triggered by "Public Data Gap" tiles.
    - Pre-populates Tennessee Open Records Act (T.C.A. § 10-7-503) formal request letter.
    - Injects target agency custodian email (e.g., MSCS Public Records Officer, County Mayor's Office).
    - Mailto link + 1-click clipboard copy.
  - **Acceptance Criteria:** Compliant with current Tennessee Open Records Act statutory language.
- [ ] **Task 2.4: Implement `CivicCalendarSync` Button**
  - **Target File:** `civic-dashboard-kit/src/components/CivicCalendarSync.tsx`
  - **Features:**
    - Generates downloadable `.ics` file or direct Google Calendar link for upcoming MSCS Board, County Commission, or City Council meetings.
    - Injects meeting agenda link and public comment speaking tips into event notes.

---

### Track 3: Narrative & Scrollytelling Visualizers
*Goal: Rich storytelling components connecting data to human systems.*

- [ ] **Task 3.1: Implement `StoryboardModal` (Interactive Scrollyteller)**
  - **Target File:** `civic-dashboard-kit/src/components/StoryboardModal.tsx`
  - **Features:**
    - 4-slide carousel/scrollyteller inspired by `decriminalizepoverty.org/present1/`.
    - Audience persona switcher (`resident`, `organizer`, `journalist`, `policymaker`).
    - Smooth step transitions, keyboard navigation (Left/Right arrows).
    - Slide-specific layouts: stat hero callouts, cross-system cards, root-cause tags, and action checklist.
  - **Acceptance Criteria:** Flawless touch swipe on mobile devices, sub-100ms slide transitions.
- [ ] **Task 3.2: Implement `SystemFunnelVisualizer` (Disparity Pipeline)**
  - **Target File:** `civic-dashboard-kit/src/components/SystemFunnelVisualizer.tsx`
  - **Features:**
    - Reusable D3/SVG pipeline showing stage-by-stage drop-offs.
    - Calculates and displays Racial Disproportionality Index (RDI) at each gate.
    - Hover/focus states showing the statutory policy lever for each stage.
  - **Acceptance Criteria:** Accessible SVG with full ARIA labeling, responsive down to 320px viewport width.
- [ ] **Task 3.3: Implement `NeighborhoodCompositeLens` Component**
  - **Target File:** `civic-dashboard-kit/src/components/NeighborhoodCompositeLens.tsx`
  - **Features:**
    - Dropdown / search selector for Shelby County ZIP codes and Census Tracts.
    - Triad layout rendering Education, Justice, and Economy metrics side-by-side.
    - Integrated action triggers ("Advocate" and "Tell Story") on each metric card.

---

### Track 4: AI Storyboard Generation Engine (Backend / Edge)
*Goal: Grounded, hallucination-free dynamic synthesis.*

- [ ] **Task 4.1: Context Aggregator Module**
  - **Target File:** `civic-dashboard-kit/src/server/contextAggregator.ts`
  - **Logic:** Joins a requested primary metric ID with pre-computed correlated indicators from the other two domains based on shared Census geography or demographic cohort.
- [ ] **Task 4.2: Structured Prompt & Anti-Hallucination Guardrail System**
  - **Target File:** `civic-dashboard-kit/src/server/storyboardEngine.ts`
  - **Logic:**
    - Prompt template enforcing strict JSON output conforming to `StoryboardResponse`.
    - Hard constraint: LLM is strictly forbidden from generating numeric statistics not present in the injected context.
    - Persona voice tuning (e.g., grade 6–8 reading level for `resident`, policy levers and statutes for `policymaker`).
- [ ] **Task 4.3: Edge / API Route Template**
  - **Target File:** `civic-dashboard-kit/src/server/apiHandler.ts`
  - **Logic:** Ready-to-mount Next.js App Router handler (`app/api/storyboard/route.ts`) supporting streaming or JSON response.

---

### Track 5: Dashboard Integration & Rollout
*Goal: Mount and configure the suite across the three live sites.*

- [ ] **Task 5.1: 901education Integration**
  - Update `SnapshotSection.tsx` with 3-tier progressive disclosure.
  - Add `AdvocacyDrawer` configs for MSCS Board of Managers and Shelby County Commission.
  - Mount `ToraRequestGenerator` on `EarlyChildhoodSection.tsx` gap tiles.
- [ ] **Task 5.2: 901justice Integration**
  - Mount `SystemFunnelVisualizer` on Juvenile Justice & Bail pipeline sections.
  - Add `AdvocacyDrawer` configs for General Sessions Judges and County Sheriff.
- [ ] **Task 5.3: 901economy Integration**
  - Mount `NeighborhoodCompositeLens` with wage, eviction, and tax abatement metrics.
  - Add `AdvocacyDrawer` configs for EDGE Board and Memphis City Council.

---

## 4. Phasing & Milestone Strategy

```
MILESTONE 1: Contracts & Print Tools (Weeks 1–2)
├── Publish schemas in civic-dashboard-kit (engagement.ts, crossDomain.ts)
├── Implement AdvocacyDrawer & PrintFactSheet components
└── Initial mount on 901education with local static configs

MILESTONE 2: Scrollyteller & Funnel Components (Weeks 3–4)
├── Implement StoryboardModal scrollyteller UI
├── Implement SystemFunnelVisualizer (D3 disparity pipeline)
└── Mount TORA public records generator on all Public Data Gap tiles

MILESTONE 3: PostgreSQL Consolidation & Live Cross-Domain (Postgres Phase)
├── Migrate 901education/901justice stores into shared Postgres instance
├── Materialize cross-system neighborhood views (vw_neighborhood_composite)
└── Connect AI Storyboard Engine to live cross-domain queries
```
