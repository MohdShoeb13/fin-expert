"""API integration tests via FastAPI TestClient (no network, no LLM)."""

import pytest
from fastapi.testclient import TestClient

from src.web_app.main import app

client = TestClient(app)


def test_health():
    res = client.get("/api/health")
    assert res.status_code == 200
    assert res.json() == {"status": "ok"}


# ----------------------------------------------------------------- goals

class TestGoalsPlan:
    def test_valid_projection(self):
        res = client.post("/api/goals/plan", json={
            "target_amount": 100_000, "years": 10,
            "monthly_contribution": 500, "initial_amount": 5_000,
            "risk_profile": "moderate",
        })
        assert res.status_code == 200
        body = res.json()
        assert body["projection"]["years"] == 10
        assert len(body["projection"]["timeline"]) == 10
        assert "moderate" in body["risk_profiles"]

    def test_invalid_risk_profile_422(self):
        res = client.post("/api/goals/plan", json={
            "target_amount": 100_000, "years": 10,
            "monthly_contribution": 500, "risk_profile": "yolo",
        })
        assert res.status_code == 422

    def test_pydantic_validation_422(self):
        res = client.post("/api/goals/plan", json={
            "target_amount": -5, "years": 10, "monthly_contribution": 500,
        })
        assert res.status_code == 422


# -------------------------------------------------------------- portfolio

class TestPortfolioAnalyze:
    def test_valid_portfolio(self, patched_market):
        res = client.post("/api/portfolio/analyze", json={"holdings": [
            {"symbol": "VTI", "shares": 10, "asset_type": "stock_etf"},
            {"symbol": "BND", "shares": 20, "asset_type": "bond_etf"},
        ]})
        assert res.status_code == 200
        body = res.json()
        assert body["total_value"] == pytest.approx(4_400)
        assert body["risk_level"] in {"Conservative", "Moderate", "Aggressive"}

    def test_empty_holdings_422(self, patched_market):
        res = client.post("/api/portfolio/analyze", json={"holdings": []})
        assert res.status_code == 422

    def test_market_down_503(self, monkeypatch, failing_market):
        import src.data.market_data as md

        monkeypatch.setattr(md, "_service", failing_market)
        res = client.post("/api/portfolio/analyze", json={"holdings": [
            {"symbol": "VTI", "shares": 10, "asset_type": "stock_etf"},
        ]})
        assert res.status_code == 503


# ----------------------------------------------------------------- market

class TestMarketEndpoints:
    def test_quote_with_history(self, patched_market):
        res = client.get("/api/market/AAPL")
        assert res.status_code == 200
        body = res.json()
        assert body["quote"]["symbol"] == "AAPL"
        assert body["quote"]["price"] == 200.0
        assert len(body["history"]) > 0

    def test_invalid_ticker_422(self, patched_market):
        res = client.get("/api/market/%24%24%24")  # "$$$"
        assert res.status_code == 422

    def test_unknown_symbol_503(self, patched_market):
        res = client.get("/api/market/ZZZZ")
        assert res.status_code == 503

    def test_quote_survives_history_failure(self, patched_market):
        from src.data.market_data import MarketDataUnavailable

        def boom(symbol, period="6mo"):
            raise MarketDataUnavailable("history down")

        patched_market.get_history = boom
        res = client.get("/api/market/AAPL")
        assert res.status_code == 200
        body = res.json()
        assert body["quote"]["symbol"] == "AAPL"
        assert body["history"] == []
        assert body["history_unavailable"] is True

    def test_news(self, patched_market):
        res = client.get("/api/market/AAPL/news")
        assert res.status_code == 200
        body = res.json()
        assert body["symbol"] == "AAPL"
        assert body["articles"][0]["title"].startswith("AAPL")


# ------------------------------------------------------------------- chat

class TestChat:
    def test_chat_returns_routed_response(self, monkeypatch):
        import src.workflow.graph as graph_module

        def fake_run_turn(session_id, message, holdings=None, goal_params=None):
            return {
                "content": f"Answer to {message}",
                "agent": "finance_qa",
                "route": "finance_qa",
                "citations": [],
                "data": {},
            }

        monkeypatch.setattr(graph_module, "run_turn", fake_run_turn)
        res = client.post("/api/chat", json={
            "message": "What is a stock?", "session_id": "test-session",
        })
        assert res.status_code == 200
        body = res.json()
        assert body["agent"] == "finance_qa"
        assert body["route"] == "finance_qa"
        assert "What is a stock?" in body["content"]

    def test_chat_validation_422(self):
        res = client.post("/api/chat", json={"message": "", "session_id": "s"})
        assert res.status_code == 422

    def test_chat_stream_emits_sse_events(self, monkeypatch):
        import json

        import src.workflow.graph as graph_module

        def fake_stream_turn(session_id, message, holdings=None, goal_params=None):
            yield {"type": "route", "route": "finance_qa"}
            yield {"type": "token", "text": "Hello"}
            yield {"type": "token", "text": " world"}
            yield {"type": "done", "response": {
                "content": "Hello world", "agent": "finance_qa",
                "route": "finance_qa", "citations": [], "data": {},
            }}

        monkeypatch.setattr(graph_module, "stream_turn", fake_stream_turn)
        with client.stream("POST", "/api/chat/stream", json={
            "message": "hi", "session_id": "s",
        }) as res:
            assert res.status_code == 200
            assert res.headers["content-type"].startswith("text/event-stream")
            body = "".join(res.iter_text())

        events = [
            json.loads(line[5:]) for line in body.splitlines() if line.startswith("data:")
        ]
        types = [e["type"] for e in events]
        assert types == ["route", "token", "token", "done"]
        assert "".join(e["text"] for e in events if e["type"] == "token") == "Hello world"
        assert events[-1]["response"]["content"] == "Hello world"

    def test_chat_failure_500(self, monkeypatch):
        import src.workflow.graph as graph_module

        def broken(*args, **kwargs):
            raise RuntimeError("graph blew up")

        monkeypatch.setattr(graph_module, "run_turn", broken)
        res = client.post("/api/chat", json={"message": "hi", "session_id": "s"})
        assert res.status_code == 500
