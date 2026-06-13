"""Unit tests for all six agents with mocked LLMs, market data, and retrieval."""

import pytest

from src.agents.finance_qa import FinanceQAAgent
from src.agents.goal_planning import GoalPlanningAgent, extract_goal_params
from src.agents.market_analysis import MarketAnalysisAgent, extract_symbols
from src.agents.news_synthesizer import NewsSynthesizerAgent
from src.agents.portfolio_analysis import PortfolioAnalysisAgent
from src.agents.registry import AGENT_CLASSES
from src.agents.tax_education import TaxEducationAgent
from src.utils.disclaimers import EDUCATIONAL_DISCLAIMER
from tests.conftest import FakeLLM


HOLDINGS = [
    {"symbol": "VTI", "shares": 10, "asset_type": "stock_etf"},
    {"symbol": "BND", "shares": 20, "asset_type": "bond_etf"},
    {"symbol": "AAPL", "shares": 5, "asset_type": "stock"},
]


class TestRegistry:
    def test_all_six_agents_registered(self):
        assert set(AGENT_CLASSES) == {
            "finance_qa", "portfolio_analysis", "market_analysis",
            "goal_planning", "news_synthesizer", "tax_education",
        }

    def test_agent_names_match_registry_keys(self):
        for key, cls in AGENT_CLASSES.items():
            assert cls.name == key


class TestFinanceQA:
    def test_responds_with_citations_and_disclaimer(self, fake_llm, fake_retriever):
        agent = FinanceQAAgent(llm=fake_llm, retriever=fake_retriever)
        res = agent.respond("What is compound interest?")
        assert EDUCATIONAL_DISCLAIMER in res.content
        assert res.agent == "finance_qa"
        assert res.citations and res.citations[0]["title"] == "Compound Interest"


class TestTaxEducation:
    def test_prefers_tax_category(self, fake_llm, fake_retriever):
        searches = []
        original = fake_retriever.search

        def tracking_search(query, top_k=None, category=None):
            searches.append(category)
            # Return 2 chunks so the tax-restricted search is "enough".
            return original(query, top_k, category) * 2

        fake_retriever.search = tracking_search
        agent = TaxEducationAgent(llm=fake_llm, retriever=fake_retriever)
        res = agent.respond("How do capital gains work?")
        assert searches == ["tax"]
        assert EDUCATIONAL_DISCLAIMER in res.content

    def test_falls_back_to_whole_kb_when_tax_results_thin(self, fake_llm, fake_retriever):
        searches = []
        original = fake_retriever.search

        def tracking_search(query, top_k=None, category=None):
            searches.append(category)
            return original(query, top_k, category)  # always 1 chunk -> thin

        fake_retriever.search = tracking_search
        agent = TaxEducationAgent(llm=fake_llm, retriever=fake_retriever)
        agent.respond("How do capital gains work?")
        assert searches == ["tax", None]


class TestMarketAnalysis:
    def test_asks_for_symbol_when_none_found(self, fake_llm, fake_market):
        agent = MarketAnalysisAgent(llm=fake_llm, market_service=fake_market)
        res = agent.respond("How is the market doing for that thing?")
        assert "ticker" in res.content.lower()
        assert res.data == {}

    def test_returns_quotes_and_trends(self, fake_llm, fake_market):
        agent = MarketAnalysisAgent(llm=fake_llm, market_service=fake_market)
        res = agent.respond("How is AAPL doing?")
        assert res.data["quotes"][0]["symbol"] == "AAPL"
        assert "AAPL" in res.data["trends"]
        assert EDUCATIONAL_DISCLAIMER in res.content

    def test_graceful_message_when_data_unavailable(self, fake_llm, failing_market):
        agent = MarketAnalysisAgent(llm=fake_llm, market_service=failing_market)
        res = agent.respond("How is AAPL doing?")
        assert "couldn't fetch" in res.content.lower()
        assert EDUCATIONAL_DISCLAIMER in res.content


class TestExtractSymbols:
    @pytest.mark.parametrize(
        "query,expected",
        [
            ("How is AAPL doing?", ["AAPL"]),
            ("How is apple stock today?", ["AAPL"]),
            ("Compare MSFT and NVDA", ["MSFT", "NVDA"]),
            ("How is AAPL doing vs the S&P 500?", ["^GSPC", "AAPL"]),
            ("what is the nasdaq doing", ["^IXIC"]),
            ("how are stocks doing", []),
        ],
    )
    def test_extraction(self, query, expected):
        assert extract_symbols(query) == expected

    def test_stopwords_not_treated_as_tickers(self):
        assert extract_symbols("WHAT IS A GOOD ETF TO BUY") == []

    def test_max_symbols_cap(self):
        assert len(extract_symbols("AAPL MSFT NVDA TSLA AMZN", max_symbols=3)) == 3


class TestNewsSynthesizer:
    def test_synthesizes_articles(self, fake_llm, fake_market):
        agent = NewsSynthesizerAgent(llm=fake_llm, market_service=fake_market)
        res = agent.respond("Any news about AAPL?")
        assert res.data["articles"]
        assert res.data["articles"][0]["related_symbol"] == "AAPL"

    def test_defaults_to_market_proxies(self, fake_llm, fake_market):
        agent = NewsSynthesizerAgent(llm=fake_llm, market_service=fake_market)
        res = agent.respond("What's happening in the markets?")
        symbols = {a["related_symbol"] for a in res.data["articles"]}
        assert symbols == {"SPY", "QQQ"}

    def test_graceful_message_when_no_news(self, fake_llm, failing_market):
        agent = NewsSynthesizerAgent(llm=fake_llm, market_service=failing_market)
        res = agent.respond("Any news about AAPL?")
        assert "couldn't retrieve" in res.content.lower()


class TestPortfolioAnalysisAgent:
    def test_asks_for_holdings_when_absent(self, fake_llm):
        agent = PortfolioAnalysisAgent(llm=fake_llm)
        res = agent.respond("Analyze my portfolio")
        assert "share your holdings" in res.content.lower()

    def test_analyzes_holdings(self, fake_llm, patched_market):
        agent = PortfolioAnalysisAgent(llm=fake_llm)
        res = agent.respond("Analyze my portfolio", holdings=HOLDINGS)
        assert res.data["analysis"]["total_value"] == pytest.approx(5_400)
        assert EDUCATIONAL_DISCLAIMER in res.content

    def test_graceful_when_market_down(self, fake_llm, monkeypatch, failing_market):
        import src.data.market_data as md

        monkeypatch.setattr(md, "_service", failing_market)
        agent = PortfolioAnalysisAgent(llm=fake_llm)
        res = agent.respond("Analyze my portfolio", holdings=HOLDINGS)
        assert "couldn't complete" in res.content.lower()


class TestGoalPlanning:
    def test_full_params_in_query_produce_projection(self, fake_llm):
        agent = GoalPlanningAgent(llm=fake_llm)
        res = agent.respond("I want to save $500k in 20 years putting in $800 a month")
        proj = res.data["projection"]
        assert proj["target_amount"] == 500_000
        assert proj["years"] == 20
        assert proj["monthly_contribution"] == 800
        assert EDUCATIONAL_DISCLAIMER in res.content

    def test_missing_params_ask_conversationally(self, fake_llm):
        agent = GoalPlanningAgent(llm=fake_llm)
        res = agent.respond("Help me plan for retirement")
        assert res.data == {}  # no projection without required params

    def test_zero_monthly_contribution_is_valid(self, fake_llm):
        # $0/month is a legitimate value (lump-sum-only growth), not "missing".
        agent = GoalPlanningAgent(llm=fake_llm)
        res = agent.respond("I want to save $100k in 10 years with $0 per month")
        proj = res.data["projection"]
        assert proj["monthly_contribution"] == 0
        assert proj["target_amount"] == 100_000

    def test_kwargs_override_query(self, fake_llm):
        agent = GoalPlanningAgent(llm=fake_llm)
        res = agent.respond(
            "plan my goal",
            target_amount=100_000, years=10, monthly_contribution=500,
            risk_profile="aggressive",
        )
        assert res.data["projection"]["risk_profile"] == "aggressive"


class TestExtractGoalParams:
    def test_full_extraction(self):
        params = extract_goal_params(
            "I want to save $500k in 20 years with $800 per month, low risk"
        )
        assert params["target_amount"] == 500_000
        assert params["years"] == 20
        assert params["monthly_contribution"] == 800
        assert params["risk_profile"] == "conservative"

    def test_millions_suffix(self):
        assert extract_goal_params("I need $1.5m in 30 years")["target_amount"] == 1_500_000

    def test_explicit_profile_word(self):
        assert extract_goal_params("save $10k aggressive")["risk_profile"] == "aggressive"

    def test_empty_query(self):
        assert extract_goal_params("hello") == {}


class TestDisclaimerEnforcement:
    """Every agent response must carry the educational disclaimer (FAQ requirement)."""

    def test_all_agents_include_disclaimer(self, fake_llm, fake_retriever, fake_market, patched_market):
        responses = [
            FinanceQAAgent(llm=fake_llm, retriever=fake_retriever).respond("what is a stock"),
            TaxEducationAgent(llm=fake_llm, retriever=fake_retriever).respond("roth ira"),
            MarketAnalysisAgent(llm=fake_llm, market_service=fake_market).respond("AAPL?"),
            NewsSynthesizerAgent(llm=fake_llm, market_service=fake_market).respond("news"),
            PortfolioAnalysisAgent(llm=fake_llm).respond("analyze", holdings=HOLDINGS),
            GoalPlanningAgent(llm=fake_llm).respond("save $100k in 10 years, $500 monthly"),
        ]
        for res in responses:
            assert EDUCATIONAL_DISCLAIMER in res.content, f"{res.agent} missing disclaimer"
