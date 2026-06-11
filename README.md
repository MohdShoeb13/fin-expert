# AI Finance Assistant 💰

A multi-agent financial education system that democratizes financial literacy
through conversational AI. Built as the capstone for *Applied Agentic AI for SWEs*.

> 📘 **Educational use only.** This assistant teaches financial concepts — it never
> gives personalized investment advice or buy/sell recommendations. Every response
> carries a disclaimer.

## What it does

Ask anything from *"What is compound interest?"* to *"Analyze my portfolio"* —
a LangGraph router classifies each message and dispatches it to one of **six
specialized agents**:

| Agent | Capability | Powered by |
|---|---|---|
| 🎓 Finance Q&A | Financial education grounded in a 50-article knowledge base (RAG + citations) | Gemini Flash |
| 📊 Portfolio Analysis | Live valuation, allocation %, diversification score, risk assessment | GPT-4o-mini |
| 📈 Market Analysis | Real-time quotes, 3-month trends, beginner-friendly metric explanations | Gemini Flash |
| 🎯 Goal Planning | Compound-growth projections by risk appetite, required-monthly solver | GPT-4o-mini |
| 📰 News Synthesizer | Recent headlines synthesized into a plain-language briefing | Gemini Flash |
| 🧾 Tax Education | Capital gains, account types, tax-loss harvesting (RAG over tax articles) | Gemini Flash |

The **router** runs on Groq (Llama 3.3) for low-latency classification, with a
keyword-heuristic fallback when no LLM is available.

## Architecture

```
┌──────────────────────────  React (Vite + TS)  ─────────────────────────┐
│   Chat 💬        Portfolio 📊        Market 📈         Goals 🎯         │
└───────────────────────────────┬─────────────────────────────────────────┘
                                │ REST (/api/*)
┌───────────────────────────────▼─────────────────────────────────────────┐
│                            FastAPI backend                              │
│  ┌────────────────────── LangGraph StateGraph ──────────────────────┐  │
│  │   START → Router (Groq + keyword fallback)                       │  │
│  │             ├→ Finance Q&A ──── RAG (FAISS + MiniLM embeddings)  │  │
│  │             ├→ Portfolio ────── portfolio analytics              │  │
│  │             ├→ Market ───────── market data service              │  │
│  │             ├→ Goals ────────── projection math                  │  │
│  │             ├→ News ─────────── yFinance news                    │  │
│  │             └→ Tax ──────────── RAG (tax category)               │  │
│  │   SQLite checkpointing = per-session conversation memory         │  │
│  └───────────────────────────────────────────────────────────────────┘  │
│  Market data: fresh cache → yFinance (retries) → Alpha Vantage →        │
│               stale cache → clear error      (30-min TTL)               │
└──────────────────────────────────────────────────────────────────────────┘
        ▲
        │ MCP (stdio)
   Claude Desktop ── get_stock_quote / analyze_portfolio /
                     search_financial_knowledge / project_goal
```

**Multi-provider LLM registry** (`config.yaml`): each agent maps to a provider
(OpenAI / Gemini / Groq). Providers are swappable without code changes, and if
a key is missing the registry automatically falls back to any configured
provider — the system works with **just one** API key.

## Quick start (local)

Requires Python 3.12 (3.14 lacks ML wheels — use [uv](https://docs.astral.sh/uv/))
and Node 18+.

```bash
# 1. Backend
uv venv --python 3.12 .venv
uv pip install --python .venv/bin/python -r requirements.txt

# 2. API keys (at least one LLM key; all three recommended)
cp .env.example .env       # then edit .env

# 3. Build the RAG index (first run downloads a ~90MB embedding model)
.venv/bin/python -m src.rag.vector_store

# 4. Start the API
.venv/bin/uvicorn src.web_app.main:app --port 8000

# 5. Frontend (new terminal)
cd frontend && npm install && npm run dev
```

Open **http://localhost:5173**.

### API keys (`.env`)

| Variable | Used for | Get one at |
|---|---|---|
| `GROQ_API_KEY` | Router (fast classification) | console.groq.com (free) |
| `GOOGLE_API_KEY` | Q&A / Market / News / Tax agents | aistudio.google.com (free tier) |
| `OPENAI_API_KEY` | Portfolio / Goals agents | platform.openai.com |
| `ALPHAVANTAGE_API_KEY` | Market data fallback (optional) | alphavantage.co (free) |

Any single LLM key is enough — agents fall back to whatever is configured.

## Quick start (Docker)

```bash
cp .env.example .env   # add your keys
docker compose up --build
```

- Frontend: **http://localhost:3000**
- API: **http://localhost:8000/api/health**

The backend image pre-builds the FAISS index, so first responses are fast.

## API reference

| Endpoint | Method | Description |
|---|---|---|
| `/api/health` | GET | Liveness check |
| `/api/chat` | POST | `{message, session_id, holdings?, goal_params?}` → routed agent response with citations |
| `/api/portfolio/analyze` | POST | `{holdings: [{symbol, shares, asset_type}]}` → metrics (no LLM) |
| `/api/market/{symbol}` | GET | Quote + history (`?period=1mo\|3mo\|6mo\|1y\|5y`) |
| `/api/market/{symbol}/news` | GET | Recent headlines |
| `/api/goals/plan` | POST | `{target_amount, years, monthly_contribution, initial_amount?, risk_profile?}` → projection (no LLM) |

Errors: `422` invalid input · `503` market data unavailable · `500` chat failure.

Example:

```bash
curl -s localhost:8000/api/goals/plan -H 'content-type: application/json' \
  -d '{"target_amount":500000,"years":20,"monthly_contribution":800}'
```

## MCP server (Claude Desktop integration)

Expose the finance tools directly to Claude Desktop — no LLM keys needed:

```bash
.venv/bin/python -m mcp_server.server
```

See **[mcp_server/README.md](mcp_server/README.md)** for the Claude Desktop
config snippet and example prompts.

## Tests

```bash
.venv/bin/python -m pytest
```

**162 tests, 94% coverage** (CI gate at 80%). No network or LLM calls — agents
run against fake LLMs, market data is mocked at the provider boundary, and the
graph is tested with a stub router. See `tests/`.

## Project structure

```
src/
├── agents/      # 6 agents + base class + registry
├── core/        # config loader, multi-provider LLM registry, logging
├── data/        # market data (yFinance→AlphaVantage→cache), portfolio math
├── rag/         # KB loader, FAISS vector store, retriever with citations
├── utils/       # disclaimers, validators, projection math
├── web_app/     # FastAPI endpoints + Pydantic schemas
└── workflow/    # LangGraph state, router, graph wiring
frontend/        # React + Vite + TS + Recharts (4 tabs)
knowledge_base/  # 50 curated articles in 8 categories (YAML frontmatter)
mcp_server/      # MCP stdio server for Claude Desktop
tests/           # 162 tests, 94% coverage
docs/            # problem statement, milestones, progress, design docs
```

## Resilience & compliance

- **Market data degradation chain**: fresh cache → yFinance (3 retries,
  exponential backoff) → Alpha Vantage → stale cache (flagged in the UI) →
  clear error. 30-minute TTL per the project FAQ.
- **LLM fallback**: router falls back to keyword heuristics; agents fall back
  to any configured provider.
- **Compliance**: every agent response (and MCP tool result) carries the
  educational disclaimer; guardrails forbid buy/sell recommendations.

## Troubleshooting

| Symptom | Fix |
|---|---|
| `LLMRegistryError: No usable LLM provider` | Add at least one key to `.env` (`cp .env.example .env`) |
| First KB query is slow | The embedding model (~90MB) downloads once; pre-build with `python -m src.rag.vector_store` |
| `faiss-cpu` install fails | You're on Python 3.13+/3.14 — create the venv with Python 3.12 (`uv venv --python 3.12`) |
| Quotes show "stale" warning | Providers are down/rate-limited; cached data is served by design |
| 429s from Gemini | Free tier is rate-limited; map more agents to `groq` in `config.yaml` |
| Frontend can't reach API | Backend must be on :8000 (Vite proxies `/api` there) |

## Documentation

- [docs/TechnicalDesign.md](docs/TechnicalDesign.md) — architecture decisions and trade-offs
- [docs/progress.md](docs/progress.md) — build log / milestone tracker
- [docs/DemoScript.md](docs/DemoScript.md) — demo video walkthrough
