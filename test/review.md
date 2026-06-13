# Manual Code Review Findings

Manual review performed without CodeRabbit.

> **Status (2026-06-13): all four findings resolved.** See commit history and
> `docs/progress.md` §13. The two Major findings have regression tests; the
> tracked-build-metadata file was removed and gitignored.

## Findings

### Major: Index symbols are extracted and documented but rejected by validation

`src/agents/market_analysis.py` maps `s&p 500`, `nasdaq`, and `dow` to `^GSPC`, `^IXIC`, and `^DJI`. `mcp_server/server.py` also documents `^GSPC` as a supported ticker example.

However, `src/utils/validators.py` requires ticker symbols to start with `A-Z`, so index symbols beginning with `^` fail before yFinance is called.

Reproduced behavior:

```text
extract_symbols("How is Apple stock doing vs the S&P 500?") -> ["AAPL", "^GSPC"]
normalize_ticker("^GSPC") raises ValueError
```

Suggested fix: allow leading `^` for index tickers and add tests for `^GSPC`, `^IXIC`, and `^DJI`.

### Major: Chat goal planning treats `$0/month` as missing

`src/web_app/schemas.py` permits `monthly_contribution >= 0`, and the projection math supports zero monthly contributions.

But `src/agents/goal_planning.py` checks required fields using truthiness:

```python
missing = required - {k for k, v in params.items() if v}
```

That drops valid zero values.

Reproduced behavior:

```text
"I want to save $100k in 10 years with $0 per month"
extracts monthly_contribution: 0.0
then marks monthly_contribution as missing
```

Suggested fix: check key presence / `is not None`, not truthiness.

### Minor: Market quote endpoint fails entirely when history fails

`src/web_app/main.py` fetches quote and history in the same `try` block for `/api/market/{symbol}`.

If quote succeeds but `get_history()` raises `MarketDataUnavailable`, the endpoint returns `503` and the Market tab loses the valid quote too.

Suggested fix: return the quote with `history: []` plus a warning when only history fails.

### Minor: Generated TypeScript build metadata is tracked

`frontend/tsconfig.tsbuildinfo` is tracked by git, but it is generated build metadata.

Suggested fix: add it to `.gitignore` and remove it from the repository.

## Verification

Commands run:

```bash
.venv/bin/python -m pytest
npm run build
```

Results:

```text
166 passed
93.85% coverage
frontend build passed
```

The frontend build produced only the existing large bundle warning.
