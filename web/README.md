# Chakravyuh Web Portal (Next.js & FastAPI)

A premium cybersecurity-themed analyst portal to ingest payment records, visualize model scores, configure dynamic GenAI prompts, monitor closed-loop ML diagnostics, and inspect the G01-G13 attack lifecycle.

## Architectural Structure

- **FastAPI Backend (`web/api.py`)**: Runs on port `8000`. Acts as the real-time inference server, invoking the trained fraud models, preprocessing parameters, and wrapping prompt calls to the Gemini API.
- **Next.js Frontend (`web/next-app/`)**: Runs on port `3000`. Interactive visual portal built with React, Tailwind CSS, and Lucide icons.

---

## Getting Started

### 1. Start the Backend API Server
Make sure you are at the project root directory:
```bash
uv run uvicorn web.api:app --host 127.0.0.1 --port 8000 --reload
```

### 2. Start the Frontend Dashboard
Launch the development server:
```bash
# In a separate terminal session
# Run from within the web/next-app directory:
npm run dev
```
Open [http://localhost:3000](http://localhost:3000) in your web browser.

### 3. Portal Credentials
Use the following security credentials to bypass the login gateway:
* **Username:** `admin`
* **Password:** `chakravyuh2026`

---

## Features

- **Analyst Login Screen**: Mock cybersecurity gatekeeper protecting model diagnostics.
- **Risk Scoring Studio**: Visual gauge metrics mapping risk scores, top classifier predictions, active device anomalies (calls, proxy, screen-shares), and Gemini AI insights.
- **GenAI Settings Modals**: Input a custom Google Gemini Key directly in the UI settings panel. Automatically falls back to a simulated rule-based local generator if no key is entered.
- **Closed-Loop Intelligence**: Radial progress rings charting PR-AUC and Recalls, live feature importances, and adaptive config parameters.
- **Attack Connection Graph**: Visual network flow of the 13 attack families categorized across 5 stages (Access -> Probing -> Execution -> Evasion -> Exfiltration). Click any node to view target rails, observabilities, novelty, and difficulty ratings.
