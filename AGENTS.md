# Agent instructions

## Project

Synthetic payment fraud generator + detector for the Mastercard Innovation Challenge 2026
(GenAI-enabled payment fraud). Three pillars: identify attack vectors, generate synthetic
data reproducing them, detect them with an ML model. This repo covers generate + defend.

Read before making non-trivial changes:
- `docs/master-project-brief.md` — challenge scope, architecture, timeline, judging criteria
- `docs/data-schema-v1.md` — the seven-table schema contract between generator and detector
- `docs/attack-catalogue.md` — frozen attack catalogue (58 entries, collapsed to 13 generators)

## Setup

```
uv sync
```

Python 3.11+, managed by `uv`. Dependencies are pinned in `pyproject.toml`; do not add a
dependency without pinning an exact version.

## Common commands

```
make install   # uv sync
make test      # uv run pytest
make lint      # uv run ruff check src tests
make data SEED=42   # generate the dataset (added once the generators land)
```

Run `make test` before committing. Run `make lint` if you touched more than a couple of files.

## Code style

- Type hints and docstrings on all public functions.
- Python `dataclasses` for row schemas (one module per table under `src/schema/`), each
  paired with a `pyarrow` schema for parquet I/O. Keep the two in sync — see
  `tests/schema/test_arrow_schemas.py` for the drift check.
- No magic numbers in generator code. Every calibration constant lives in
  `src/generators/calibration.py` with a comment citing its source or reasoning.
- Seeded RNG throughout. `make data SEED=42` must produce byte-identical output on a clean
  clone — this is a judged criterion, not a nice-to-have.
- Don't invent or rename schema fields. If `docs/data-schema-v1.md` seems wrong or
  ambiguous, say so and ask rather than silently deciding.
- Only fields a real payment system would hold at decision time belong in the schema. If
  an issuer or PSP wouldn't have it at the moment of scoring, it doesn't belong.
- No hardcoded regulatory limits (UPI caps, AFA thresholds, etc.) without a dated comment
  — several changed in 2025 and stale values are a known defect risk in this project.

## Commits

- No AI attribution. Do not add "Co-Authored-By", "Generated with Claude Code", or any
  similar trailer to commit messages or PR descriptions.
- Small commit messages only: one short imperative line describing what changed in the
  code (e.g. "Add transaction schema and arrow round-trip tests"). No references to
  conversation phases, steps, days, or internal planning language — that context lives in
  the conversation and the project docs, not in git history.
- Commit after each unit of work, then push to `origin`. The GitHub repo is the source of
  truth for project state; don't let work sit uncommitted across a session boundary.
- Never commit `data/generated/` (gitignored) or anything under it.
