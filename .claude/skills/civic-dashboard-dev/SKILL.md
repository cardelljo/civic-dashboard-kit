---
name: civic-dashboard-dev
description: Development process for the 901 civic dashboards (901justice, 901education, 901economy) and this toolkit. Use when writing code, reviewing a PR, delegating a ticket, investigating CI, or making an architecture decision in any of these repos.
---

# Development process

## Who owns what (read before editing this file)

This skill covers **process across repos**. It is not the only instruction file, and the
split matters because the audiences differ:

| File | Audience | Owns |
|---|---|---|
| `<repo>/AGENTS.md` | **any** agent, including Codex and other non-Claude delegates | that repo's non-negotiables and the operational verification checklist |
| this skill | Claude sessions, all repos | cross-repo process, decision homes, token discipline |
| `docs/ARCHITECTURE.md` (this repo) | everyone | infrastructure decisions binding more than one dashboard |

**Delegates never load this skill.** If a rule must reach Codex, it goes in `AGENTS.md`.
Change operational test rules there first; this file summarizes.

*All four repos — the three dashboards and this toolkit — now have an `AGENTS.md`, and
they differ deliberately. A rule that holds for one is not assumed to hold for the
others. Read the one in the repo you are editing; do not carry a non-negotiable across
repos from memory.*

## 1. Verify, then claim

Never report something as working that you have not executed. Keep **verified** and
**pending** separate in every summary. A confident summary of untested work is worse than
none: it ends the review that would have caught the problem.

Four failure modes, all of which have already occurred here:

- **A skipped test is not a passing test.** `pytest` exits **0** when every database test
  skips for want of `TOOLKIT_TEST_DATABASE_URL`. Check the skip count, not the exit code.
- **A pipe destroys the exit code.** `pytest ... | tail -2 && git commit` commits even when
  tests fail. Run, check `$?`, then commit.
- **A test that has never failed may assert nothing.** For real arithmetic or a data
  contract, break the code deliberately and confirm the suite goes red.
- **Green CI can mean nothing ran.** Zero checks is not a pass. Confirm *which* checks ran.

Verify against the source — the live API, the file on disk, the run history — not memory.
Correct yourself in one line and move on.

## 1a. What the Claude cloud environment gives you — use it before speculating

Real credentials and a real database are available in the session environment.
Several wrong claims in this project's history would have been caught by one live
call, so **verify against the API rather than reasoning about it.**

**Working, and safe to call** — public read-only data APIs, no cost, no writes:

| Env var | Verified against |
|---|---|
| `CENSUS_API_KEY` | `AcsClient` — all 64 variables of 901economy's ACS 1-year pull, MSA cut, clean |
| `FRED_API_KEY` | `FredClient` — `MPHNA`, `MPHLF` |
| `BEA_API_KEY` | `BeaClient` — `CAGDP1`/`47157` fine; **no metro GDP exists, see `bea.py`** |

Read them from the environment; never paste a key into a file, a commit, a PR
body, or the transcript. When printing an exception from an API call, scrub the
key first — `requests` puts it in the URL, so raw error text leaks it.

**`DATABASE_URL` is set but not reachable.** It names a private Coolify service
that does not resolve outside that network — DNS fails, so there is nothing to
retry. That is the intended posture, not a misconfiguration. Consequences: you
cannot apply `db/schema.sql`, run seeds, or inspect production from a session.
Those run from the pipeline container on the host.

**For database work, build a local Postgres instead:** `scripts/dev-postgres.sh`
gives Postgres 18 + PostGIS 3.6 matching the deployed instance, and takes
`pytest` from a double-digit skip count to **one** — `test_ci_guards.py`'s own
CI-only check, expected to skip locally. It's not always still running between
sessions: `pg_isready -h localhost -p 5433` before assuming it's up, rerun the
script if not (idempotent). Use it before claiming anything about
`postgres_store` or `boundaries` works.

**No `ANTHROPIC_API_KEY`** is set (only `ANTHROPIC_BASE_URL`), so `ai_extract` /
T3 extraction paths cannot be exercised live.

## 2. Read the recorded decisions; don't re-derive them

| Question | Answer lives in |
|---|---|
| Binds several dashboards (DB, PostGIS, boundaries) | `civic-dashboard-kit/docs/ARCHITECTURE.md` |
| Toolkit behavior, choosing a store | `civic-dashboard-kit/README.md` |
| What to work on next, in this repo | `civic-dashboard-kit/docs/TASKS.md`'s **Next Up** |
| A cross-repo finding that isn't a decision or a task (a sibling repo's actual state as last checked, precedent for a judgment call) | `civic-dashboard-kit/docs/PROJECT_NOTES.md` |
| One dashboard only | that repo's `PLAN.md` / `docs/TASKS.md` / `docs/PROJECT_NOTES.md` |

Decisions here get revisited on evidence — that is welcome — but cite the section you are
contradicting. **A new decision that binds a sibling repo is recorded in the shared file
first**, then summarized locally. Recording one only where it was made is how three
dashboards nearly ended up with three copies of the same Shelby County polygons.

## 3. Architecture invariants

- **Static data.** Frontends never query a database or API. Pipelines write storage; a
  build step emits `data/*.json`; the site imports those files. PostGIS did not change
  this and neither does anything else.
- **Honest gaps.** Missing data renders as a gap tile naming who holds it. Suppressed
  values render as suppressed — never zero, never interpolated. Every figure carries
  source and vintage.
- **Append-only stores.** New rows supersede; nothing is overwritten.
- **Dependencies pinned to immutable commits, not `@main`.** Bumping is a deliberate commit.
- **Don't write a third copy.** Check `toolkit.*` before porting logic between repos.

## 4. Token discipline

Context is the scarce resource, and most waste is avoidable:

- **Never dump a large API response.** GitHub's `list_workflow_runs` returns ~300KB for 30
  runs. Use `per_page`, or parse the saved file with a script printing only what you need.
- **Grep, then read a range.** `grep -n` to locate, then `offset`/`limit`. Read whole files
  only when you will use the whole thing.
- **Count when you only need existence** — `grep -c` over printing matches.
- **Don't re-read a file you just edited.** The edit fails loudly if it failed.
- **Batch independent calls** in one message; they run in parallel.
- **Put intermediates in scratchpad files**, not in the conversation.
- **Don't paste file contents into PR bodies.** Describe and reference.
- **Run the narrowest suite that covers the change**, then the full one once at the end.

## 5. Delegation

Delegate mechanical, closed tickets; keep contract-and-judgment work in-thread. A
delegable ticket names one source, states acceptance criteria, points at a worked
exemplar, and **says what is out of scope** so the delegate doesn't discover it halfway.

Review delegated output as real work. It has caught bugs here that the author missed, and
the author has caught bugs it introduced. When it disagrees with an instruction, check the
source before assuming the instruction was right.

## 6. When to ask, when to act

Ask when the call is genuinely the user's: an architecture trade-off, anything hard to
reverse on a live site, or scope that reads two ways. Give a recommendation *with* the
question, not a survey.

Act without asking on the obvious next step of approved work, ordinary implementation
choices, and investigating something suspicious.

Surface unrequested findings **once**, with evidence, then let it go.

## 7. Communication

Lead with the answer, then reasoning, then caveats. Table for comparing more than two
things. Flag your own errors in one line and continue.

When explaining mechanics — how a CI trigger fires, what a flag does — be concrete and
brief: what happens, when, and what it does **not** cover. The reader is technically
fluent and reasons well about systems; skip the concepts, pin down the behavior.
