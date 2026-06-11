"""FastAPI backend for the AI Finance Assistant.

Endpoints:
  POST /api/chat              -> route a message through the LangGraph workflow
  POST /api/chat/stream       -> same turn, streamed as SSE token events
  POST /api/portfolio/analyze -> deterministic portfolio metrics (no LLM)
  GET  /api/market/{symbol}   -> live quote + 6mo history
  GET  /api/market/{symbol}/news
  POST /api/goals/plan        -> deterministic goal projection (no LLM)
  GET  /api/health
"""

from __future__ import annotations

import json

from fastapi import FastAPI, HTTPException
from fastapi.concurrency import run_in_threadpool
from fastapi.middleware.cors import CORSMiddleware
from sse_starlette.sse import EventSourceResponse
from starlette.concurrency import iterate_in_threadpool

from src.core.config import get_config
from src.core.logging import get_logger
from src.data.market_data import MarketDataUnavailable, get_market_data_service
from src.data.portfolio import analyze_portfolio
from src.utils.projections import RISK_PROFILES, project_goal
from src.web_app.schemas import ChatRequest, ChatResponse, GoalRequest, PortfolioRequest

logger = get_logger(__name__)

app = FastAPI(title="AI Finance Assistant", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=get_config().get("server.cors_origins", ["http://localhost:5173"]),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok"}


@app.post("/api/chat", response_model=ChatResponse)
async def chat(req: ChatRequest) -> ChatResponse:
    from src.workflow.graph import run_turn

    try:
        result = await run_in_threadpool(
            run_turn,
            req.session_id,
            req.message,
            [h.model_dump() for h in req.holdings] if req.holdings else None,
            req.goal_params,
        )
        return ChatResponse(**result)
    except Exception as exc:  # noqa: BLE001
        logger.exception("Chat turn failed")
        raise HTTPException(status_code=500, detail=f"Chat failed: {exc}") from exc


@app.post("/api/chat/stream")
async def chat_stream(req: ChatRequest) -> EventSourceResponse:
    """Stream a chat turn as SSE: route -> token... -> done."""
    from src.workflow.graph import stream_turn

    events = stream_turn(
        req.session_id,
        req.message,
        [h.model_dump() for h in req.holdings] if req.holdings else None,
        req.goal_params,
    )

    async def event_source():
        # LangGraph streaming is synchronous; iterate it off the event loop.
        async for event in iterate_in_threadpool(events):
            yield {"data": json.dumps(event)}

    return EventSourceResponse(event_source())


@app.post("/api/portfolio/analyze")
async def portfolio_analyze(req: PortfolioRequest) -> dict:
    try:
        analysis = await run_in_threadpool(
            analyze_portfolio, [h.model_dump() for h in req.holdings]
        )
        return analysis.to_dict()
    except MarketDataUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.get("/api/market/{symbol}")
async def market_quote(symbol: str, period: str = "6mo") -> dict:
    svc = get_market_data_service()
    try:
        quote = await run_in_threadpool(svc.get_quote, symbol)
        history = await run_in_threadpool(svc.get_history, symbol, period)
        return {"quote": quote.to_dict(), "history": [vars(p) for p in history]}
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except MarketDataUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@app.get("/api/market/{symbol}/news")
async def market_news(symbol: str, limit: int = 8) -> dict:
    svc = get_market_data_service()
    try:
        articles = await run_in_threadpool(svc.get_news, symbol, limit)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {"symbol": symbol.upper(), "articles": articles}


@app.post("/api/goals/plan")
async def goals_plan(req: GoalRequest) -> dict:
    try:
        projection = project_goal(
            target_amount=req.target_amount,
            years=req.years,
            monthly_contribution=req.monthly_contribution,
            initial_amount=req.initial_amount,
            risk_profile=req.risk_profile,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {"projection": projection.to_dict(), "risk_profiles": RISK_PROFILES}


if __name__ == "__main__":
    import uvicorn

    cfg = get_config()
    uvicorn.run(
        "src.web_app.main:app",
        host=cfg.get("server.host", "0.0.0.0"),
        port=cfg.get("server.port", 8000),
        reload=True,
    )
