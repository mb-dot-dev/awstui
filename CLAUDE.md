# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project overview

`awst` (AWS Console Terminal UI) is a TUI application built on [Textual](https://textual.textualize.io/). The project is in early skeleton stage — `src/awst/skeleton_app.py` contains a placeholder `SkeletonApp` that will be replaced/expanded as the real console UI is built. Requires Python >=3.14. Dependency management and packaging use `uv`.

## Commands

All commands run through `uv` and are wrapped by the `Makefile`; prefer the `make` targets.

- `make install-dev` — install all dependencies (including dev group) via `uv sync --frozen`.
- `make install` — install production-only dependencies.
- `make lint` — run `ruff check`, `ruff format --check`, and `ty check` (type checking). Run this before considering any change complete.
- `make format` — auto-format code with `ruff format`.
- `make unit` — run the test suite (`uv run --frozen pytest`).
- `make test` — run `lint` then `unit`; this is the full local check, and mirrors CI.
- `make coverage` — run tests with coverage, writing `build/coverage.xml` (coverage fails under 75%).

Run a single test directly with uv/pytest, e.g.:
```
uv run --frozen pytest tests/test_skeleton_app.py::test_happy_path
```

There is no separate typecheck-only Makefile target; `ty check` is invoked as part of `make lint`.

## Architecture

- `src/awst/__init__.py` exposes `main()`, the console-script entry point (`awst` command, see `[project.scripts]` in `pyproject.toml`), which instantiates and runs the Textual `App`.
- The Textual `App` subclass (currently `SkeletonApp`) is the root of the UI: it defines `CSS` inline and implements `compose()` to yield widgets. Future screens/widgets for AWS console functionality should follow this same Textual app/widget/screen pattern.
- Tests use `pytest-asyncio` and Textual's `run_test()` pilot harness to drive the app headlessly and assert against widget state (see `tests/test_skeleton_app.py`).

## Linting conventions

Ruff is configured with a broad rule set (see `[tool.ruff.lint]` in `pyproject.toml`), including flake8-annotations, bandit (security), bugbear, complexity, pathlib, and more, with a 120-char line length. Notable per-file relaxations: `tests/**/*.py` may use `assert`, hardcoded-looking values/strings, local imports inside functions, and `print`.

## CI

- `.github/workflows/main.yaml` runs on push/PR to `main`: installs deps, lints, runs coverage, then submits results to SonarQube/SonarCloud (project key `mb-dot-dev_awst`).
- `.github/workflows/release.yaml` publishes to PyPI via trusted publishing when a `v*.*.*` tag is pushed (sets the version from the tag, builds, and publishes with `uv`).
