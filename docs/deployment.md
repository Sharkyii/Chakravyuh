# Deployment

Two Cloudflare Workers, deployed independently:

- **`web/next-app`** -- Next.js frontend, built with `@opennextjs/cloudflare`
  and deployed as a standard Worker with static assets.
- **`backend-worker`** -- a thin Worker that proxies into a Cloudflare
  Container running the FastAPI backend (`Dockerfile` at repo root). The
  container needs real CPU/memory for XGBoost/pandas inference, which is why
  it's a Container rather than a Pyodide-based Python Worker (Pyodide can't
  run XGBoost's C extensions).

## Local development

`docker-compose.yml` at the repo root runs both services together:

```bash
docker compose up --build
```

Frontend on `localhost:3000`, API on `localhost:8000`.

## Frontend deploy

```bash
cd web/next-app
npm run deploy   # opennextjs-cloudflare build && opennextjs-cloudflare deploy
```

Set `NEXT_PUBLIC_API_BASE_URL` in `wrangler.jsonc` (`vars`) to the deployed
backend Worker's URL before deploying.

## Backend deploy

```bash
cd backend-worker
npm run deploy   # wrangler deploy, builds the container image from ../Dockerfile
```

Requires a running Docker daemon locally (or `--containers-rollout=none` to
skip the container build/rollout, e.g. for a Worker-only config check).

`stage5/models/*.pkl` are gitignored (exceed GitHub's file size limit) but
get baked into the container image via `COPY stage5 ./stage5` in the
Dockerfile, since Docker build context isn't git-filtered -- only train the
models locally once before running `docker build` / `wrangler deploy`.

## CI

`.github/workflows/ci.yml` runs Python lint/tests, frontend typecheck/lint/
build, and the Playwright e2e suite on every push/PR to `main`. It does not
deploy -- deploys are manual via the commands above until a deploy job is
added.
