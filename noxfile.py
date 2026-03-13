"""Nox sessions for Phantex.

Run a single session:
    nox -p 3.11 -s lint
    nox -p 3.11 -s format
    nox -p 3.11 -s typecheck
    nox -p 3.11 -s tests
    nox -p 3.11 -s pre-commit

Run all default sessions:
    nox -p 3.11
"""

from __future__ import annotations

import nox

nox.options.sessions = ("lint", "format", "typecheck", "tests")
nox.options.reuse_existing_virtualenvs = True

PYTHON = "3.11"
SOURCE_DIRS = ["phantex", "tests"]


@nox.session(python=PYTHON)
def lint(session: nox.Session) -> None:
    """Run ruff linter."""
    session.install("ruff>=0.15.6")
    session.run("ruff", "check", *SOURCE_DIRS)


@nox.session(python=PYTHON)
def format(session: nox.Session) -> None:
    """Run ruff formatter (check mode in CI, fix mode locally).

    Pass -- --fix to apply fixes:
        nox -p 3.11 -s format -- --fix
    """
    session.install("ruff>=0.15.6")
    args = session.posargs or ["--check"]
    session.run("ruff", "format", *args, *SOURCE_DIRS)


@nox.session(python=PYTHON)
def typecheck(session: nox.Session) -> None:
    """Run mypy static type checker."""
    session.install("mypy>=1.19.1")
    session.install(
        "flask>=3.1.3",
        "bleak>=2.1.1",
        "apscheduler>=3.11.2",
    )
    session.run("mypy", "phantex")


@nox.session(python=PYTHON)
def tests(session: nox.Session) -> None:
    """Run pytest with coverage."""
    session.install(
        "pytest>=8.0.0",
        "pytest-cov>=6.0.0",
        "flask>=3.1.3",
        "bleak>=2.1.1",
        "apscheduler>=3.11.2",
    )
    session.install("-e", ".")
    session.run(
        "pytest",
        "tests",
        "--cov=phantex",
        "--cov-report=term-missing",
        "--cov-report=html",
        *session.posargs,
    )


@nox.session(python=PYTHON, name="pre-commit")
def pre_commit(session: nox.Session) -> None:
    """Run pre-commit hooks against all files."""
    session.install("pre-commit>=4.0.0")
    session.run("pre-commit", "run", "--all-files")
