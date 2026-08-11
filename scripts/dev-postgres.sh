#!/usr/bin/env bash
# Start a local PostgreSQL 18 + PostGIS cluster for running this package's
# database tests, and print the DSN to export.
#
# Why this exists: `tests/test_postgres_store.py` skips entirely without
# TOOLKIT_TEST_DATABASE_URL, and a skipped test is not a passing test -- pytest
# still exits 0. Before this script the only real Postgres was in CI, so
# `postgres_store` changes were unverifiable locally.
#
# Matches what the Coolify host runs (docs/ARCHITECTURE.md §3): Postgres 18,
# PostGIS 3.6. Ubuntu 24.04 ships only postgresql-16, so 18 comes from PGDG.
#
# Idempotent: re-running against a live cluster just reprints the DSN.
#
#   ./scripts/dev-postgres.sh
#   export TOOLKIT_TEST_DATABASE_URL=postgresql://postgres:postgres@localhost:5433/civic_toolkit_test
#   pytest -q          # expect 39 passed, 0 skipped
set -euo pipefail

PG_MAJOR=18
PORT="${PGDEV_PORT:-5433}"   # not 5432: leaves any system postgresql-16 alone
DB=civic_toolkit_test
PGBIN="/usr/lib/postgresql/${PG_MAJOR}/bin"
PGDATA="/var/lib/postgresql/${PG_MAJOR}/test"
DSN="postgresql://postgres:postgres@localhost:${PORT}/${DB}"

need_root() {
  [ "$(id -u)" -eq 0 ] || { echo "error: needs root (installs packages, writes /var/lib/postgresql)" >&2; exit 1; }
}

if [ ! -x "${PGBIN}/initdb" ]; then
  need_root
  echo "==> installing postgresql-${PG_MAJOR} + PostGIS from PGDG"
  apt-get install -y -q curl ca-certificates gnupg >/dev/null
  install -d /usr/share/postgresql-common/pgdg
  curl -fsS -o /usr/share/postgresql-common/pgdg/apt.postgresql.org.asc \
    https://www.postgresql.org/media/keys/ACCC4CF8.asc
  . /etc/os-release
  echo "deb [signed-by=/usr/share/postgresql-common/pgdg/apt.postgresql.org.asc] https://apt.postgresql.org/pub/repos/apt ${VERSION_CODENAME}-pgdg main" \
    > /etc/apt/sources.list.d/pgdg.list
  apt-get update -q >/dev/null
  apt-get install -y -q "postgresql-${PG_MAJOR}" "postgresql-${PG_MAJOR}-postgis-3" >/dev/null
fi

if "${PGBIN}/pg_isready" -p "${PORT}" -q 2>/dev/null; then
  echo "==> cluster already running on ${PORT}"
else
  need_root
  if [ ! -s "${PGDATA}/PG_VERSION" ]; then
    echo "==> initdb (locale=C, deliberately)"
    # --locale=C rather than the default: on the alpine image the host runs,
    # initdb ACCEPTS en_US.utf8 and warns "no usable system locales were found",
    # leaving datcollate claiming a locale musl cannot provide while text orders
    # by byte value. Choosing C here keeps the catalog honest and matches that
    # actual ordering behavior. See docs/ARCHITECTURE.md §3.
    mkdir -p "${PGDATA}"
    chown -R postgres:postgres "$(dirname "${PGDATA}")"
    runuser -u postgres -- "${PGBIN}/initdb" -D "${PGDATA}" --locale=C --encoding=UTF8 >/dev/null
  fi
  mkdir -p /var/log/postgresql && chown postgres:postgres /var/log/postgresql
  echo "==> starting on port ${PORT}"
  runuser -u postgres -- "${PGBIN}/pg_ctl" -D "${PGDATA}" -o "-p ${PORT}" \
    -l /var/log/postgresql/dev-${PG_MAJOR}.log start >/dev/null
  for _ in $(seq 30); do "${PGBIN}/pg_isready" -p "${PORT}" -q && break; sleep 1; done
fi

runuser -u postgres -- "${PGBIN}/psql" -p "${PORT}" -tAc \
  "ALTER USER postgres PASSWORD 'postgres'" >/dev/null

if ! runuser -u postgres -- "${PGBIN}/psql" -p "${PORT}" -lqt | cut -d'|' -f1 | grep -qw "${DB}"; then
  echo "==> creating ${DB} with PostGIS"
  runuser -u postgres -- "${PGBIN}/createdb" -p "${PORT}" "${DB}"
fi
runuser -u postgres -- "${PGBIN}/psql" -p "${PORT}" -d "${DB}" -qc \
  "CREATE EXTENSION IF NOT EXISTS postgis" >/dev/null

echo
runuser -u postgres -- "${PGBIN}/psql" -p "${PORT}" -d "${DB}" -tAc \
  "SELECT 'postgres ' || current_setting('server_version') || ', postgis ' || postgis_version()
        || ', collate ' || (SELECT datcollate FROM pg_database WHERE datname = current_database())"
echo
echo "export TOOLKIT_TEST_DATABASE_URL=${DSN}"
