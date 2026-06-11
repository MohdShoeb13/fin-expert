"""Tests for the MCP server tools (in-process, no stdio client needed)."""

import json

import pytest

from mcp_server.server import mcp


def call(name: str, args: dict) -> dict:
    """Invoke an MCP tool and parse its JSON text content."""
    import asyncio

    result = asyncio.get_event_loop().run_until_complete(mcp.call_tool(name, args))
    contents = result[0] if isinstance(result, tuple) else result
    return json.loads(contents[0].text)


@pytest.fixture(scope="module")
def event_loop_policy():
    import asyncio

    asyncio.set_event_loop(asyncio.new_event_loop())


def test_all_four_tools_registered():
    import asyncio

    tools = asyncio.new_event_loop().run_until_complete(mcp.list_tools())
    assert {t.name for t in tools} == {
        "get_stock_quote",
        "analyze_portfolio",
        "search_financial_knowledge",
        "project_goal",
    }
    # Every tool must document itself for the client model.
    assert all(t.description for t in tools)


def test_project_goal_tool():
    body = call("project_goal", {
        "target_amount": 500_000, "years": 20, "monthly_contribution": 800,
        "initial_amount": 10_000, "risk_profile": "moderate",
    })
    assert body["projected_final"] == pytest.approx(428_901.21, abs=1)
    assert body["goal_met"] is False
    assert "disclaimer" in body


def test_get_stock_quote_tool(patched_market):
    body = call("get_stock_quote", {"symbol": "AAPL"})
    assert body["symbol"] == "AAPL"
    assert body["price"] == 200.0
    assert "disclaimer" in body


def test_analyze_portfolio_tool(patched_market):
    body = call("analyze_portfolio", {"holdings": [
        {"symbol": "VTI", "shares": 10, "asset_type": "stock_etf"},
        {"symbol": "BND", "shares": 20, "asset_type": "bond_etf"},
    ]})
    assert body["total_value"] == pytest.approx(4_400)
    assert body["risk_level"] in {"Conservative", "Moderate", "Aggressive"}
    assert "disclaimer" in body


def test_search_financial_knowledge_tool(monkeypatch, fake_retriever):
    import src.rag.retriever as retriever_module

    monkeypatch.setattr(
        retriever_module, "KnowledgeRetriever", lambda *a, **kw: fake_retriever
    )
    body = call("search_financial_knowledge", {"query": "compound interest"})
    assert body["results"][0]["title"] == "Compound Interest"
    assert body["results"][0]["source"]
    assert "disclaimer" in body
