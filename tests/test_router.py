"""Tests for query routing (src/workflow/router.py)."""

import pytest

from src.workflow import router
from src.workflow.router import DEFAULT_ROUTE, ROUTES, classify, keyword_route
from tests.conftest import FakeLLM


class TestKeywordRoute:
    @pytest.mark.parametrize(
        "query,expected",
        [
            ("What is compound interest?", "finance_qa"),
            ("Can you analyze my portfolio allocation?", "portfolio_analysis"),
            ("What's the stock price of AAPL today?", "market_analysis"),
            ("I want to save for a house in 10 years", "goal_planning"),
            ("Any news about Tesla earnings report?", "news_synthesizer"),
            ("How are capital gains taxed in a Roth IRA?", "tax_education"),
        ],
    )
    def test_all_six_routes(self, query, expected):
        assert keyword_route(query) == expected

    def test_unknown_query_defaults_to_finance_qa(self):
        assert keyword_route("tell me something interesting") == DEFAULT_ROUTE

    def test_routes_are_valid(self):
        for q in ["portfolio", "tax", "news", "goal", "price", "anything"]:
            assert keyword_route(q) in ROUTES


class TestClassify:
    def test_uses_llm_when_available(self, monkeypatch):
        monkeypatch.setattr(
            router, "get_llm_for_agent", lambda name: FakeLLM(["market_analysis"])
        )
        assert classify("How is Apple doing?") == "market_analysis"

    def test_llm_route_normalized(self, monkeypatch):
        monkeypatch.setattr(
            router, "get_llm_for_agent", lambda name: FakeLLM(["  Goal-Planning \n"])
        )
        assert classify("retirement question") == "goal_planning"

    def test_invalid_llm_route_falls_back_to_keywords(self, monkeypatch):
        monkeypatch.setattr(
            router, "get_llm_for_agent", lambda name: FakeLLM(["not_a_route"])
        )
        assert classify("how are my holdings allocated") == "portfolio_analysis"

    def test_llm_failure_falls_back_to_keywords(self, monkeypatch):
        def broken(name):
            raise RuntimeError("no API key")

        monkeypatch.setattr(router, "get_llm_for_agent", broken)
        assert classify("what is the price of MSFT") == "market_analysis"

    def test_llm_failure_unknown_query_still_returns_valid_route(self, monkeypatch):
        def broken(name):
            raise RuntimeError("no API key")

        monkeypatch.setattr(router, "get_llm_for_agent", broken)
        assert classify("hello there") == DEFAULT_ROUTE
