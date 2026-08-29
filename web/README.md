# Chakravyuh Web Portal (Next.js & FastAPI)

The live demo: an analyst portal for scoring transactions, watching the fraud/detector
closed loop, and exploring the attack catalogue — all in the browser.

## How it's put together

- **FastAPI backend (`web/api.py`)** — port `8000`. Loads the trained model, scores
  transactions, and optionally calls the Gemini API for the written analyst note.
- **Next.js frontend (`web/next-app/`)** — port `3000`. The actual portal UI.

---

## Running it locally

Start the backend (from the project root):
```bash
uv run uvicorn web.api:app --host 127.0.0.1 --port 8000 --reload
```

Then, in a separate terminal, start the frontend:
```bash
cd web/next-app
npm run dev
```

Open [http://localhost:3000](http://localhost:3000). There's no login — the entry
screen is a decorative boot animation, not real authentication (there's nothing to
sign in as).

---

## What's in the portal

- **Risk Scoring Studio** — score a transaction and see the model's confidence,
  which features drove the decision (SHAP), and an optional GenAI-written summary.
- **Closed-Loop Intelligence** — the detector's actual precision/recall numbers,
  and what happened when it was retrained on harder attacks.
- **Attack Connection Graph** — click through the attack catalogue and see how each
  one moves through a payment's lifecycle.

GenAI notes are optional. Add your own key in the settings panel, or leave it blank
— the portal falls back to a plain template automatically.
