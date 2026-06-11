# Demo Video Script — AI Finance Assistant

Target length: **5–7 minutes**. Have the app running (`docker compose up` or
local dev) with at least one LLM key configured, and Claude Desktop with the
MCP server registered for the bonus segment.

## 0. Intro (30s)

- "This is the AI Finance Assistant — a multi-agent financial education system."
- One-liner on the stack: LangGraph orchestration, six agents across three LLM
  providers (GPT, Gemini, Groq), FAISS RAG, live market data, React frontend.
- Point at the persistent disclaimer banner: education, never advice.

## 1. Multi-agent routing in the Chat tab (90s)

Type these in one session and call out the **agent badge** changing on each
response — that's the LangGraph router classifying and dispatching:

1. `What is compound interest?` → 🎓 Finance Q&A — point out **source
   citations** from the knowledge base.
2. `How is Apple stock doing vs the S&P 500?` → 📈 Market Analysis — note the
   live prices and 3-month trend in the answer.
3. `How are capital gains taxed in a Roth IRA?` → 🧾 Tax Education.
4. `What's happening in the markets today?` → 📰 News Synthesizer — headlines
   attributed to publishers.

Then demonstrate **conversation memory**: ask `Can you explain that last point
more simply?` and show it answers in context (SQLite checkpointing per session).

## 2. Portfolio tab (60s)

- The sample three-fund portfolio (VTI/VXUS/BND) is preloaded — click
  **Analyze portfolio**.
- Walk through: live total value, **diversification score** (Herfindahl-based),
  risk score/level, allocation pie + asset-type bar charts.
- Edit: bump VTI shares way up, re-analyze → the **concentration warning**
  appears. "These numbers are computed deterministically — the LLM only
  explains them, so it can't hallucinate your portfolio math."

## 3. Market tab (45s)

- Look up `NVDA`, switch periods on the price chart, scroll the news list.
- Mention resilience: "yFinance primary, Alpha Vantage fallback, 30-minute
  cache — if everything is down you get the last cached price flagged as stale,
  never a blank screen."

## 4. Goals tab (45s)

- Enter: $500,000 target, 20 years, $800/month, moderate risk → **Project my goal**.
- Show the stacked area chart (contributions vs compound growth) and the goal
  reference line.
- It falls short → point at the "monthly needed" hint (~$945). Switch to
  aggressive and re-run to show the assumption change.

## 5. Resilience + engineering (45s)

- Kill the backend's network or remove the API keys (pre-recorded is fine):
  chat still routes via **keyword fallback**, quotes serve **stale cache**
  with a warning.
- Flash the test run: `pytest` → **162 tests, 94% coverage** with an 80% gate.
- Flash `config.yaml`: per-agent provider mapping — "swap any agent to any
  provider without touching code."

## 6. Bonus: MCP server in Claude Desktop (45s)

- In Claude Desktop, ask: *"Analyze this portfolio: 30 VTI, 25 VXUS, 20 BND —
  use the finance tools."*
- Show Claude calling `analyze_portfolio` and `search_financial_knowledge`,
  and note the same deterministic engine powers the web app, the API, and MCP.

## 7. Wrap (15s)

- Recap: 6 agents, 3 LLM providers, RAG with citations, live data with
  graceful degradation, full test suite, Docker, MCP.
- "Everything is educational — the assistant teaches, it doesn't advise."

## Pre-flight checklist

- [ ] `.env` has at least GROQ + GOOGLE keys (chat is fast and free-tier)
- [ ] FAISS index built (first KB query otherwise stalls the demo)
- [ ] Markets… exist (weekday demo = live price changes; weekend = flat "Today" numbers)
- [ ] Claude Desktop config points at this repo's venv python
- [ ] Terminal with `pytest` output ready to show
