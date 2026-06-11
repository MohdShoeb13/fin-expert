# Project Progress Tracker

Capstone: **AI Finance Assistant** — multi-agent financial education system.
This file tracks what has been built so far. Update it as work progresses.

_Last updated: 2026-06-11_

## Technology Decisions (locked in)

| Decision | Choice |
|---|---|
| Orchestration | LangGraph (StateGraph router) |
| LLMs | Multi-provider: OpenAI GPT + Google Gemini + Groq (config-driven, per-agent mapping) |
| Vector DB | FAISS (sentence-transformers/all-MiniLM-L6-v2 embeddings) |
| Market data | yFinance primary + Alpha Vantage fallback, 30-min TTL cache |
| Frontend | React (Vite + TypeScript + Recharts) over a FastAPI backend |
| Agents | All 6 from the start |
| Bonuses | MCP server + Docker + full test suite (80%+) |

## Status Overview

| # | Milestone | Status |
|---|---|---|
| 1 | Project scaffolding & core infrastructure | ✅ Done |
| 2 | Knowledge base (50 articles) + RAG pipeline | ✅ Done |
| 3 | Market data layer (yFinance + Alpha Vantage fallback) | ✅ Done |
| 4 | All six agents | ✅ Done |
| 5 | LangGraph workflow orchestration | ✅ Done |
| 6 | FastAPI backend | ✅ Done |
| 7 | React frontend (4 tabs) | ✅ Done (builds clean; needs visual check) |
| 8 | Test suite (80%+ coverage) | ✅ Done — **162 tests, 94% coverage** |
| 9 | MCP server (Claude Desktop) | ✅ Done (all 4 tools verified live) |
| 10 | Docker + README + design docs | ✅ Done (Docker config written; not built — Docker not installed on this machine) |

## What Has Been Built

### 1. Scaffolding & core infrastructure ✅
- Prescribed project structure (`src/agents`, `core`, `data`, `rag`, `web_app`, `utils`, `workflow`, `tests`) plus `frontend/`, `mcp_server/`, `knowledge_base/`.
- Python 3.12 venv via `uv` (`.venv/`), all dependencies installed (`requirements.txt`).
- `config.yaml` — single config for LLM provider/agent mapping, RAG params, cache TTL, server settings.
- `src/core/config.py` — YAML + `.env` config loader with dotted-path access.
- `src/core/llm_registry.py` — **multi-provider LLM registry**: Groq → router (low latency), Gemini Flash → Q&A/News/Tax (free tier), GPT-4o-mini → Portfolio/Goals (reasoning). Providers swappable in config; automatic fallback to any available provider if an API key is missing.
- `.env.example` — requires `OPENAI_API_KEY`, `GOOGLE_API_KEY`, `GROQ_API_KEY`, optional `ALPHAVANTAGE_API_KEY`.

### 2. Knowledge base + RAG ✅
- **50 curated articles** in `knowledge_base/` across 8 categories: basics (9), stocks (7), bonds (6), etfs_funds (7), retirement (7), tax (6), risk_diversification (8), glossary (2). Each has YAML frontmatter (title, category, source attribution).
- `src/rag/loader.py` — frontmatter-aware article loader (folder = category).
- `src/rag/vector_store.py` — chunking (800/120 overlap), HuggingFace embeddings, FAISS index with persistence (`.faiss_index/`). Rebuild with `.venv/bin/python -m src.rag.vector_store`.
- `src/rag/retriever.py` — semantic search with relevance scoring, category filtering, source citations.
- **Verified:** 126 chunks indexed; retrieval returns correct articles with scores (e.g. compound interest → 0.74).

### 3. Market data layer ✅
- `src/data/market_data.py` — fallback chain: fresh cache → yFinance (retries + exponential backoff) → Alpha Vantage → stale cache → error. Quotes carry provider + freshness timestamp + stale flag. History + news included.
- `src/data/cache.py` — thread-safe TTL cache (30-min) that retains expired entries for graceful degradation.
- `src/data/portfolio.py` — portfolio analytics: live valuation, allocation %, allocation by asset type, Herfindahl-based diversification score (0–100), risk score/level, concentration warnings.
- `src/data/sample_portfolios.py` — 3 demo portfolios.
- **Verified:** live AAPL/VTI quotes, history, news, and cache hits all work.

### 4. Six agents ✅ (`src/agents/`)
All extend `base_agent.py` (LLM from registry, shared guardrails, mandatory educational disclaimer on every response):
1. `finance_qa.py` — RAG-grounded education with [n] citations.
2. `portfolio_analysis.py` — explains computed portfolio metrics (asks for holdings if absent).
3. `market_analysis.py` — live quotes + 3-month trend context; ticker/company-name extraction.
4. `goal_planning.py` — parses goal params from free text, runs projections (`src/utils/projections.py`: FV math, required-monthly, risk profiles 4.5%/6.5%/8.5%).
5. `news_synthesizer.py` — yFinance news → beginner briefing with publisher attribution.
6. `tax_education.py` — RAG restricted to tax category with whole-KB fallback.

### 5. LangGraph workflow ✅ (`src/workflow/`)
- `state.py` — shared state (messages with `add_messages`, route, holdings, goal params, response).
- `router.py` — Groq LLM classification with **keyword-heuristic fallback** if LLM unavailable (verified all 6 routes).
- `graph.py` — StateGraph: START → router → conditional edge → agent node → END; SQLite checkpointing per `session_id` for multi-turn memory; error fallback node returns a safe message.
- **Verified:** graph compiles with all 8 nodes; keyword routing 6/6 correct.

### 6. FastAPI backend ✅ (`src/web_app/`)
- `POST /api/chat` (LangGraph turn), `POST /api/portfolio/analyze`, `GET /api/market/{symbol}` (+`/news`), `POST /api/goals/plan`, `GET /api/health`. CORS for Vite dev server. Pydantic validation throughout.
- **Verified live:** health ok, VTI quote, projection math, portfolio analysis, invalid ticker → 422.
- Run with: `.venv/bin/uvicorn src.web_app.main:app --port 8000`

### 7. React frontend ✅ (`frontend/`)
- Vite + TypeScript + Recharts. Four tabs:
  - **Chat** — agent badges, markdown rendering, source citations, suggestions, session memory.
  - **Portfolio** — holdings editor (sample pre-loaded), metric cards, allocation pie + asset-type bar charts, warnings.
  - **Market** — quote lookup, metric cards, period-selectable price chart, news list, stale-data notice.
  - **Goals** — projection form, stacked contributions-vs-growth area chart with goal reference line, required-monthly hint.
- Persistent educational disclaimer banner. Dark theme.
- **Verified:** `npm run build` passes clean (TS strict).
- Run with: `cd frontend && npm run dev` → http://localhost:5173

### 8. Test suite ✅ (`tests/`)
- **157 tests, 94% line coverage** (target was 80%; `pytest.ini` enforces `--cov-fail-under=80`).
- No network and no real LLM calls anywhere — fakes/mocks throughout (`tests/conftest.py`: `FakeLLM`, `FakeMarketService`, `FakeRetriever`).
- Coverage by area:
  - `test_projections.py` — FV math, required-monthly round-trip, timeline accounting, edge cases (zero rate, invalid years/profile).
  - `test_utils.py` — ticker validation, positive checks, disclaimer idempotency.
  - `test_cache.py` — TTL expiry, stale retention, overwrite, clear.
  - `test_portfolio.py` — valuation/allocation math, Herfindahl diversification, risk levels, concentration warnings, failure modes.
  - `test_market_data.py` — full fallback chain (cache → yFinance → Alpha Vantage → stale → error), retries, provider response parsing (mocked yfinance/requests), news parsing.
  - `test_router.py` — keyword routing for all 6 agents, LLM classification, fallback when LLM is down or returns garbage.
  - `test_agents.py` — all six agents with fake LLMs, symbol/goal-param extraction, disclaimer enforcement on every agent.
  - `test_rag.py` — frontmatter parsing, KB loader (real KB ≥50 articles), chunking metadata, retriever scoring/threshold/category filter, citation dedupe.
  - `test_workflow.py` — graph compilation, router→agent flow, agent-failure fallback message, **session memory across turns** (SQLite checkpointer), holdings pass-through.
  - `test_api.py` — every endpoint via TestClient: happy paths, 422 validation, 503 degradation, 500 chat failure.
- Run with: `.venv/bin/python -m pytest`

### 9. MCP server ✅ (`mcp_server/`)
- FastMCP (Python MCP SDK 1.27) over stdio exposing 4 tools: `get_stock_quote`, `analyze_portfolio`, `search_financial_knowledge`, `project_goal` — the same deterministic data/math layer the agents use, so no LLM keys are needed.
- Every tool result carries the educational disclaimer.
- `mcp_server/README.md` — Claude Desktop config snippet, Claude Code one-liner, example prompts.
- **Verified live:** all 4 tools invoked in-process — goal projection matches known math ($428,901), KB search hits "Compound Interest" (0.69), live VTI quote via yfinance, portfolio analysis correct. Covered by `tests/test_mcp_server.py` (suite now 162 tests).
- Run with: `.venv/bin/python -m mcp_server.server`

### 10. Docker + documentation ✅
- `Dockerfile` (backend) — Python 3.12-slim, pre-builds the FAISS index at image build so first responses are fast.
- `frontend/Dockerfile` — Node build stage → nginx serving the built SPA, proxying `/api` to the backend container (`frontend/nginx.conf`).
- `docker-compose.yml` — backend (:8000) + frontend (:3000), optional `.env`, named volume for conversation checkpoints, health check.
- `README.md` — architecture diagram, local + Docker quick starts, API key table, full API reference, test instructions, resilience/compliance summary, troubleshooting table.
- `docs/TechnicalDesign.md` — design decisions and trade-offs (LangGraph, multi-provider strategy, RAG params, market-data resilience, deterministic-core principle, testing strategy, known limitations).
- `docs/DemoScript.md` — 5–7 min demo video walkthrough with pre-flight checklist.

### 11. Frontend design polish ✅ (2026-06-11)
- **framer-motion** installed (it was missing despite an earlier attempted install) and wired throughout.
- Visual glow-up (`styles.css`, `index.html`): gradient mesh background, glassmorphism panels (backdrop blur + translucent borders), sky→indigo accent gradient on buttons/badges/active tab, gradient header text, Inter font, hover lift + glow on metric cards, styled scrollbar, focus rings.
- Motion layer (`frontend/src/motion.tsx`): `FadeIn`, `Stagger`/`StaggerItem`, `AnimatedNumber` (spring count-up); `MotionConfig reducedMotion="user"` respects OS settings.
- Per-component: sliding tab pill (`layoutId`), spring-in chat messages, animated 3-dot typing indicator, staggered metric cards with count-up numbers on Portfolio/Market/Goals, chart + news reveals.
- **Verified with headless Chrome (Playwright)**: screenshots of all 4 tabs with live data; chat conversation survives tab switches (regression check passed); no console errors (one benign favicon 404). `npm run build` passes TS strict; bundle 844 kB minified / 246 kB gzip (+130 kB raw for framer-motion). Backend suite still 162 passed / 94%.

### 12. Streaming chat (SSE) ✅ (2026-06-11)
- **`POST /api/chat/stream`** — ChatGPT-style token streaming. LangGraph `stream_mode=["updates","messages"]` in `stream_turn()` (`src/workflow/graph.py`); event protocol: `route` (agent badge appears immediately) → `token`× n → `done` (full response with disclaimer + citations), `error` on failure. Router tokens and full-message state updates are filtered out (`AIMessageChunk` check).
- Served via `sse-starlette` `EventSourceResponse` with the sync generator iterated in a threadpool; non-streaming `/api/chat` kept for compatibility.
- Frontend: `api.chatStream()` parses SSE over `fetch` + `ReadableStream` (handles `\r\n` frame endings — sse-starlette uses them; this was a real bug found in browser testing); ChatTab renders tokens into a live placeholder with a blinking cursor, typing dots only until the first token, and **falls back to the non-streaming endpoint** if the stream fails before any token.
- nginx config: `proxy_buffering off` for SSE in Docker.
- **Verified**: curl shows route/token/done events through both :8000 and the Vite proxy; headless Chrome confirmed incremental DOM growth with streaming cursor, then a clean final message (badge, citations, disclaimer). 4 new tests (stream event sequence, agent-crash fallback, graph-failure error event, SSE endpoint) — suite now **166 passed, ~94%**.
- Note: heavy test traffic can hit the Gemini free-tier per-minute limit; the LLM retries internally and the stream completes late rather than failing.

### Live end-to-end verification ✅ (2026-06-11)

With Groq + Gemini keys in `.env`, the chat pipeline was verified live:
- **Groq router** classified queries correctly (finance_qa, goal_planning).
- **Gemini agent** answered with RAG citations from the knowledge base.
- **Multi-turn memory** worked — a follow-up referencing "it" was answered in context (SQLite checkpointing).
- **Provider fallback verified for real**: no OpenAI key → goal_planning automatically fell back to Gemini (logged warning), and the projection math came through ($300/mo × 10y → $50,520 vs $50k goal).
- **Config fix:** `gemini-2.0-flash` now has zero free-tier quota at Google, so `config.yaml` was switched to **`gemini-2.5-flash`** (verified working; `gemini-flash-latest` and `2.5-flash-lite` also work with this key).

## Remaining Work

All 10 milestones are complete. Outstanding items need the user:

1. **Visual check of the frontend** — `npm run dev` builds clean, but the four tabs haven't been eyeballed in a browser.
2. **Docker build verification** — Docker isn't installed on this machine; run `docker compose up --build` where Docker is available.
3. **Record the demo video** — script in `docs/DemoScript.md`.
4. **(Optional) Register the MCP server** in Claude Desktop — snippet in `mcp_server/README.md`.
5. **(Optional) Add an OpenAI key** so portfolio/goal agents use their configured provider — the Gemini fallback already covers them.

## Notes / Known Items

- **LLM keys**: Groq + Gemini keys configured in `.env` (2026-06-11); OpenAI not set — registry falls back to Gemini for portfolio/goal agents.
- Embedding model downloads on first index build (~90 MB, cached afterwards).
- Python 3.14 is the system default but lacks ML wheels; the project venv pins **Python 3.12 via uv**.
- Frontend bundle is ~714 kB minified (Recharts); fine for the capstone, could code-split later.
