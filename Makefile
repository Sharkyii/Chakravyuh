.PHONY: install test lint data graph

install:
	uv sync

test:
	uv run pytest

lint:
	uv run ruff check src tests

SEED ?= 42
OUTPUT_DIR ?= data/generated/stage1
STAGE2_OUTPUT_DIR ?= data/generated/stage2
N_CONSUMERS ?=
N_MERCHANTS ?=

data:
	uv run python -m src.generators.dataset --seed $(SEED) --output-dir $(OUTPUT_DIR) $(if $(N_CONSUMERS),--n-consumers $(N_CONSUMERS),) $(if $(N_MERCHANTS),--n-merchants $(N_MERCHANTS),)

graph:
	uv run python -m src.dataset.stage2 --input-dir $(OUTPUT_DIR) --output-dir $(STAGE2_OUTPUT_DIR)
