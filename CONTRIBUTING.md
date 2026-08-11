# Contributing

## Setup

```
git clone https://github.com/cardelljo/civic-dashboard-kit
cd civic-dashboard-kit
pip install -e ".[ai,postgres]"
pytest
```

Postgres integration tests (`tests/test_postgres_store.py`) skip automatically
if `TOOLKIT_TEST_DATABASE_URL` isn't set — they need a real Postgres, since
the store's `indicators_current` view relies on `DISTINCT ON`, which has no
SQLite equivalent. **A skipped test is not a passing test**: `pytest` still
exits 0, so check the counts, not the exit code. `pytest` should report
**39 passed, 0 skipped**; 8 skips means you have no database.

If you already run Postgres locally, any 16+ instance will do:

```
createdb civic_toolkit_dev
export TOOLKIT_TEST_DATABASE_URL=postgresql://localhost/civic_toolkit_dev
pytest tests/test_postgres_store.py -v
```

Otherwise `scripts/dev-postgres.sh` builds one matching the deployed instance —
**Postgres 18 + PostGIS 3.6** (docs/ARCHITECTURE.md §3), installed from PGDG
since Ubuntu 24.04 ships only `postgresql-16`:

```
sudo ./scripts/dev-postgres.sh          # idempotent; prints the DSN to export
export TOOLKIT_TEST_DATABASE_URL=postgresql://postgres:postgres@localhost:5433/civic_toolkit_test
pytest -q
```

It runs on port **5433** so it won't disturb a system `postgresql-16`, and
`initdb`s with `--locale=C` deliberately — see §3 for why the alpine image's
default locale leaves `datcollate` claiming something musl cannot provide.

## Adding a new API client

Follow the shape of an existing one (`census.py`, `fred.py`, and `bea.py` are
all the same pattern) rather than inventing a new one:

- A thin class taking whatever auth the API needs in `__init__` (an API key,
  a base URL) — no hardcoded credentials, ever.
- Methods that build the request, call `requests`, and return a normalized
  `dict`/`list[dict]` — not the raw API response shape. Callers shouldn't
  need to know the source API's specific field names or response envelope.
- Handle the source's specific quirks inside the client, not in every
  caller's code: FRED's `.` missing-value sentinel gets dropped in
  `fred.py`, not re-implemented by every dashboard that uses it. If an API
  has an error-response shape distinct from HTTP error codes (BEA does),
  raise a clear exception from inside the client.
- No dashboard-specific logic. If you're tempted to add a parameter for
  "the way my dashboard needs this," that logic belongs in your own
  pipeline code, calling this client — not in the client itself.

## Testing conventions

- **API clients: fixture-based, no network I/O.** Monkeypatch
  `requests.get`/`requests.post` to return a canned response and assert on
  the request shape + parsed output (see `tests/test_toolkit_clients.py`).
  Never make a real network call in a test.
- **`postgres_store.py`: real Postgres, via the `TOOLKIT_TEST_DATABASE_URL`
  skip pattern above.** Assert on actual database state after calling the
  module's functions, not just that a function ran without raising.
- **`observations.py`: `tmp_path`-based, no server needed** — it's a file
  ledger, so a pytest temp directory is the whole fixture.

## Adding a new store backend

Don't add a third one casually. `observations.py` and `postgres_store.py`
already cover the two ends of the scale spectrum this toolkit targets (see
the README's "Choosing a store" section). A new backend needs a real reason
neither of those meets — not just a different preference — and should keep
the same `Observation`/append-only/"newest row wins" design so the concept
transfers for anyone who already knows one of the other two.

## Pull requests

- One logical change per PR. If you're fixing a bug and adding a feature,
  that's two PRs.
- Run `pytest` before opening — a red test suite blocks review.
- Update the module reference table in `README.md` if you add or rename a
  module.
- Update `CHANGELOG.md` under `[Unreleased]`.
