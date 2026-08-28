FROM python:3.11-slim AS base

RUN apt-get update && apt-get install -y --no-install-recommends \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:0.11.26 /uv /uvx /usr/local/bin/

WORKDIR /app

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

COPY src ./src
COPY stage5 ./stage5
COPY web ./web
COPY data/generated/stage5/baseline/stage2 ./data/generated/stage5/baseline/stage2

ENV PATH="/app/.venv/bin:$PATH"

EXPOSE 8000

CMD ["uvicorn", "web.api:app", "--host", "0.0.0.0", "--port", "8000"]
