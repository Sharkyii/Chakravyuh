.PHONY: install test lint

install:
	uv sync

test:
	uv run pytest

lint:
	uv run ruff check src tests

# `make data SEED=42` arrives with the legitimate transaction generator
# (Phase 1, step 3). Not wired up yet -- schema and population generators
# come first.
