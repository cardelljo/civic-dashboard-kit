"""
Guards against a green build that verified nothing.

`pytest` exits 0 when every test in `tests/test_postgres_store.py` skips for
want of `TOOLKIT_TEST_DATABASE_URL`, so a broken service container, a renamed
env var, or a dropped `env:` block in the workflow all read as a passing build.
That has already happened in this project's history, which is why it is asserted
rather than trusted.

This module deliberately carries no module-level skip marker: a guard that skips
under the same condition it is meant to detect is not a guard.
"""

from __future__ import annotations

import os

import pytest

CI = bool(os.environ.get("CI"))


def test_postgres_tests_are_not_silently_skipped_in_ci():
    if CI and not os.environ.get("TOOLKIT_TEST_DATABASE_URL"):
        pytest.fail(
            "TOOLKIT_TEST_DATABASE_URL is unset in CI, so every test in "
            "tests/test_postgres_store.py skipped and this job proved nothing "
            "about postgres_store.py. Check the workflow's `env:` block and the "
            "Postgres service container."
        )


def test_postgres_driver_is_installed_in_ci():
    """A missing `[postgres]` extra would skip the same tests for a different
    reason -- an ImportError at collection, not a missing URL."""
    if not CI:
        pytest.skip("local run: the postgres extra is optional outside CI")
    import psycopg2  # noqa: F401
