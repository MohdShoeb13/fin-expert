# AI Finance Assistant — MCP Server

Exposes the project's deterministic finance tools to any MCP client
(Claude Desktop, Claude Code, etc.) over stdio. No LLM API keys required —
the client model does the reasoning on top of these tools.

## Tools

| Tool | What it does |
|---|---|
| `get_stock_quote(symbol)` | Live quote with provider, as-of timestamp, and stale flag (yFinance → Alpha Vantage → cache fallback) |
| `analyze_portfolio(holdings)` | Total value, allocation %, diversification score (0–100), risk score/level, concentration warnings |
| `search_financial_knowledge(query, category?, top_k?)` | Semantic search over the 50-article curated knowledge base with source attribution |
| `project_goal(target_amount, years, monthly_contribution, initial_amount?, risk_profile?)` | Compound-growth projection with year-by-year timeline and required-monthly solver |

Every result carries the educational disclaimer.

## Run standalone (smoke test)

```bash
.venv/bin/python -m mcp_server.server
```

The server speaks MCP over stdio; it will wait for a client. Ctrl+C to exit.

## Claude Desktop setup

Add to `~/Library/Application Support/Claude/claude_desktop_config.json`
(create the file if it doesn't exist), replacing `/ABSOLUTE/PATH/TO/fin-expert`:

```json
{
  "mcpServers": {
    "ai-finance-assistant": {
      "command": "/ABSOLUTE/PATH/TO/fin-expert/.venv/bin/python",
      "args": ["-m", "mcp_server.server"],
      "cwd": "/ABSOLUTE/PATH/TO/fin-expert"
    }
  }
}
```

Restart Claude Desktop. The four tools appear under the 🔌 connector icon.

## Claude Code setup

```bash
claude mcp add ai-finance-assistant -- .venv/bin/python -m mcp_server.server
```

## Example prompts to try in Claude Desktop

- "Get a quote for VTI and explain what the metrics mean."
- "Analyze this portfolio: 30 shares VTI (stock ETF), 25 VXUS (stock ETF), 20 BND (bond ETF)."
- "Search the finance knowledge base for how tax-loss harvesting works."
- "If I save $800/month for 20 years starting with $10k at moderate risk, will I reach $500k?"

## Notes

- First `search_financial_knowledge` call may take ~30s if the FAISS index
  needs to be built (downloads the embedding model once, ~90 MB).
- Quotes need internet access; with no network you'll get cached data
  (flagged `stale: true`) or a clear error.
