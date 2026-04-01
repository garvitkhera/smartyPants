# Smarty Pants — AI-Powered R&D Lending POC

R&D Tax Incentive (R&DTI) lending platform with a 4-step AI credit assessment pipeline powered by Claude.

## What It Does

Companies doing R&D in Australia get a government tax refund (up to 43.5% of R&D spend), but it takes 12-18 months. Smarty Pants lends them that money now, secured against the incoming refund.

The AI engine runs a 4-step pipeline on every application:

1. **Hard Rules** — Deterministic gates from the Credit Policy (LVR, min spend, ABN, etc.)
2. **R&D Eligibility** — Claude analyses R&D activities against ATO criteria
3. **Credit Risk** — Claude does character-based lending + financial health assessment
4. **Audit Risk** — Claude predicts ATO audit probability and refund impact
5. **Decision** — Claude writes the final credit decision narrative

Plus a parametric pricing engine with sliders for term, LVR, and grade.

## Quick Start (Local)

```bash
pip install -r requirements.txt
export ANTHROPIC_API_KEY=sk-ant-...
streamlit run app.py
```

## Deploy on Render (Free Tier)

1. Push to GitHub
2. Create a **Web Service** on Render
3. Set:
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `streamlit run app.py --server.port=$PORT --server.address=0.0.0.0 --server.headless=true`
4. Add environment variables: `ANTHROPIC_API_KEY`, `SUPABASE_URL` (optional), `SUPABASE_KEY` (optional)

Or use the `render.yaml` for Blueprint deploys.

## Supabase Setup (Optional)

1. Create a project at [supabase.com](https://supabase.com)
2. Go to SQL Editor → paste and run `schema.sql`
3. Copy your Project URL and `anon` key into the app sidebar or env vars

Without Supabase, everything works in-memory (no persistence between sessions).

## Tech Stack

| Layer | Tech |
|-------|------|
| Frontend | Streamlit (Python) |
| AI Engine | Anthropic Claude Sonnet via API |
| Rules Engine | Python (deterministic credit policy gates) |
| Pricing | Parametric Python engine |
| Database | Supabase (PostgreSQL) |
| Deployment | Render (single process) |

## Project Structure

```
app.py              # Streamlit frontend (single entry point)
ai_engine.py        # Claude AI pipeline (4 steps, streaming)
credit_policy.py    # Dummy credit policy + hard rules + pricing
database.py         # Supabase client (graceful degradation)
schema.sql          # Supabase table schema
render.yaml         # Render deployment config
```
