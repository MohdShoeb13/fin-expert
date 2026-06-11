"""MCP server for the AI Finance Assistant (bonus milestone).

Exposes the project's deterministic tool layer to any MCP client
(e.g. Claude Desktop) over stdio:

    get_stock_quote            -> live quote with provider + freshness metadata
    analyze_portfolio          -> valuation, allocation, diversification, risk
    search_financial_knowledge -> semantic search over the curated KB (FAISS)
    project_goal               -> compound-growth goal projection by risk profile

No LLM keys are needed — these tools are the same data/math layer the agents
use, so the calling model (Claude) does the reasoning on top of them.

Run:        .venv/bin/python -m mcp_server.server
Configure:  see mcp_server/README.md for the Claude Desktop snippet.
"""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from src.core.logging import get_logger
from src.utils.disclaimers import EDUCATIONAL_DISCLAIMER

logger = get_logger(__name__)

mcp = FastMCP(
    "ai-finance-assistant",
    instructions=(
        "Financial education tools: live market quotes, portfolio analytics, "
        "a curated financial knowledge base, and goal projections. "
        "All output is educational — never present it as personalized "
        "financial advice or buy/sell recommendations."
    ),
)


@mcp.tool()
def get_stock_quote(symbol: str) -> dict:
    """Get a live stock/ETF/index quote with freshness metadata.

    Args:
        symbol: Ticker symbol, e.g. "AAPL", "VTI", "^GSPC", "BTC-USD".

    Returns price, daily change, valuation metrics (market cap, P/E,
    52-week range), the provider that served it (yfinance / alpha_vantage),
    an as-of timestamp, and a `stale` flag when only cached data was available.
    """
    from src.data.market_data import get_market_data_service

    quote = get_market_data_service().get_quote(symbol)
    return {**quote.to_dict(), "disclaimer": EDUCATIONAL_DISCLAIMER}


@mcp.tool()
def analyze_portfolio(holdings: list[dict]) -> dict:
    """Analyze a portfolio: live valuation, allocation, diversification, risk.

    Args:
        holdings: List of holdings, each like
            {"symbol": "VTI", "shares": 10, "asset_type": "stock_etf"}.
            asset_type is one of: stock, stock_etf, bond_etf, bond,
            reit_etf, crypto, cash (defaults to "stock").

    Returns total value, per-holding allocation %, allocation by asset type,
    a diversification score (0-100, higher = more diversified), a risk score
    (0-100) with level, and concentration warnings.
    """
    from src.data.portfolio import analyze_portfolio as _analyze

    analysis = _analyze(holdings)
    return {**analysis.to_dict(), "disclaimer": EDUCATIONAL_DISCLAIMER}


@mcp.tool()
def search_financial_knowledge(query: str, category: str | None = None, top_k: int = 4) -> dict:
    """Search the curated financial education knowledge base (50 articles).

    Args:
        query: Natural-language question, e.g. "how does compound interest work".
        category: Optional filter — one of: basics, stocks, bonds, etfs_funds,
            retirement, tax, risk_diversification, glossary.
        top_k: Number of passages to return (default 4).

    Returns the most relevant passages with title, category, source
    attribution, and a relevance score in [0, 1].
    """
    from src.rag.retriever import KnowledgeRetriever

    chunks = KnowledgeRetriever().search(query, top_k=top_k, category=category)
    return {
        "query": query,
        "results": [
            {
                "content": c.content,
                "title": c.title,
                "category": c.category,
                "source": c.source,
                "score": c.score,
            }
            for c in chunks
        ],
        "disclaimer": EDUCATIONAL_DISCLAIMER,
    }


@mcp.tool()
def project_goal(
    target_amount: float,
    years: int,
    monthly_contribution: float,
    initial_amount: float = 0.0,
    risk_profile: str = "moderate",
) -> dict:
    """Project savings growth toward a financial goal.

    Args:
        target_amount: Goal amount in dollars, e.g. 500000.
        years: Time horizon, 1-60.
        monthly_contribution: Planned monthly contribution in dollars.
        initial_amount: Starting balance (default 0).
        risk_profile: conservative (4.5%/yr), moderate (6.5%/yr),
            or aggressive (8.5%/yr) assumed nominal returns.

    Returns the projected final balance, whether the goal is met, any
    shortfall, the required monthly contribution to hit the goal, and a
    year-by-year timeline splitting contributions from investment growth.
    """
    from src.utils.projections import project_goal as _project

    projection = _project(
        target_amount=target_amount,
        years=years,
        monthly_contribution=monthly_contribution,
        initial_amount=initial_amount,
        risk_profile=risk_profile,
    )
    return {**projection.to_dict(), "disclaimer": EDUCATIONAL_DISCLAIMER}


if __name__ == "__main__":
    logger.info("Starting AI Finance Assistant MCP server (stdio)")
    mcp.run()
