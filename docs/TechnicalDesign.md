# Technical Design — AI Finance Assistant

This document explains the key architecture decisions and their trade-offs.
For setup and usage see the [README](../README.md); for the build log see
[progress.md](progress.md).

## 1. Orchestration: LangGraph StateGraph

A single `StateGraph` routes every conversation turn:

```
START → router → (conditional edge on state["route"]) → one of 6 agent nodes → END
```

**Why LangGraph over a hand-rolled dispatcher or CrewAI:**
- First-class conversation state with reducers (`add_messages`) — multi-turn
  memory is part of the graph, not bolted on.
- SQLite checkpointing (`SqliteSaver`) keyed by `thread_id = session_id` gives
  per-session memory that survives server restarts, for free.
- Conditional edges make the router→agent fan-out explicit and testable
  (`build_graph(checkpointer=False)` compiles an ephemeral graph for tests).

**State schema** (`src/workflow/state.py`): messages (append-reduced), `route`,
`holdings`, `goal_params`, `agent_response`, `error`. Structured inputs
(holdings, goal params) ride alongside the chat so the UI can pass form data
into the same workflow.

**Error handling:** each agent node wraps `respond()` in a try/except; failures
produce a safe fallback message (with disclaimer) and record `error` in state —
a failed LLM call never 500s the chat endpoint.

## 2. Multi-provider LLM strategy

Three providers, assigned per agent in `config.yaml`:

| Provider | Model | Assigned to | Why |
|---|---|---|---|
| Groq | llama-3.3-70b-versatile | Router | Lowest latency; classification is cheap and frequent |
| Gemini | gemini-2.0-flash | Q&A, Market, News, Tax | Generous free tier for high-volume RAG-grounded agents |
| OpenAI | gpt-4o-mini | Portfolio, Goals | Strong numeric reasoning for metric/projection explanation |

The registry (`src/core/llm_registry.py`) resolves `agent name → provider →
chat model`, caches instances, and **falls back to any configured provider**
when a key is missing. Trade-off: a fallback provider may be slower or
rate-limited, but a partially configured environment stays fully functional —
important for evaluators who may only have one key.

## 3. RAG pipeline

- **Corpus**: 50 hand-curated markdown articles in 8 categories with YAML
  frontmatter (`title`, `category`, `source`) — the folder name is the
  category, which powers filtered retrieval.
- **Chunking**: `RecursiveCharacterTextSplitter`, 800 chars / 120 overlap —
  large enough to keep a concept intact, small enough for 4-chunk contexts.
- **Embeddings**: `sentence-transformers/all-MiniLM-L6-v2` — local, free, fast
  (~90MB). No embedding API costs or rate limits.
- **Store**: FAISS with disk persistence. Chosen over a hosted vector DB
  because the corpus is small, static, and must run offline/in Docker.
- **Scoring**: FAISS L2 distance mapped to a [0,1] relevance score
  (`1 - d/2`); results below a 0.25 threshold are dropped rather than padding
  the context with noise.
- **Attribution**: every retrieved chunk carries title + source; agents cite
  as `[n]` and the API returns structured citations the UI renders.
- **Category filtering** over-fetches 3× then filters, so the tax agent's
  restricted search still fills `top_k`. The tax agent falls back to the whole
  KB when tax-only results are thin (retirement/tax overlap).

## 4. Market data resilience

```
fresh cache (30-min TTL) → yFinance (3 retries, exponential backoff)
    → Alpha Vantage → stale cache (flagged) → MarketDataUnavailable
```

- The TTL cache **retains expired entries** (`get_stale`) so total provider
  failure degrades to "old data with a warning" instead of an error.
- Every `Quote` carries `provider`, `as_of`, and `stale` — the UI shows a
  freshness notice for stale data, and agents are prompted to mention it.
- yFinance needs no key (primary); Alpha Vantage requires a free key
  (fallback). Both are normalized into one `Quote` dataclass so consumers
  never know which provider answered.

## 5. Deterministic core, LLM shell

Portfolio math (`src/data/portfolio.py`) and goal projections
(`src/utils/projections.py`) are **pure Python, not LLM output**:

- Diversification: normalized Herfindahl-Hirschman index → 0–100 score.
- Risk: allocation-weighted asset-type risk weights → score + level.
- Projections: closed-form FV of lump + annuity; required-monthly solver;
  risk profiles at 4.5% / 6.5% / 8.5% nominal.

The LLM only *explains* numbers computed deterministically — no hallucinated
arithmetic, and `/api/portfolio/analyze` + `/api/goals/plan` work with zero
LLM keys. The same layer backs the REST API, the agents, and the MCP server.

## 6. Compliance guardrails

- `with_disclaimer()` is applied in `BaseAgent._finalize()` — structurally
  impossible for an agent response to skip the disclaimer (and it's
  idempotent, so multi-pass flows don't stack it).
- `COMMON_GUARDRAILS` appended to every system prompt: education only, no
  buy/sell recommendations, define jargon, don't invent figures.
- The frontend shows a persistent disclaimer banner.

## 7. Frontend

React 18 + Vite + TypeScript (strict) + Recharts. Four tabs map to the four
user journeys (Chat / Portfolio / Market / Goals); the Chat tab stays mounted
(hidden via CSS) so conversation state survives tab switches. The Vite dev
server proxies `/api` to :8000; in Docker, nginx does the same — the frontend
never hardcodes a backend origin.

## 8. Testing strategy

162 tests, 94% coverage, no network and no real LLM calls:

- **Boundary mocking**: LLMs replaced with `FakeListChatModel`; market
  providers mocked at `_fetch_yfinance` / `_fetch_alpha_vantage` so the retry,
  fallback, and stale-cache chain is tested for real.
- **Math is tested exactly** (round-trip: `required_monthly` feeds
  `future_value` back to the target).
- **Workflow integration**: graph compiled with an in-memory checkpointer to
  prove session memory works across turns and that agent crashes produce the
  fallback message.
- **API contract**: every endpoint's happy path plus 422/503/500 paths via
  `TestClient`.
- `pytest.ini` enforces `--cov-fail-under=80`.

## 9. Known limitations

- Chat responses are not streamed (SSE was descoped; `run_in_threadpool`
  keeps the server responsive).
- The retriever loads the FAISS index lazily on first query; cold start in a
  fresh environment includes the embedding-model download (pre-built in the
  Docker image).
- Ticker/goal extraction is regex-based — good for demo phrasing, not
  arbitrary text (the LLM router tolerates most misroutes since every agent
  can ask clarifying questions).
- yFinance is an unofficial API; the Alpha Vantage fallback and stale cache
  exist precisely because it occasionally rate-limits.
