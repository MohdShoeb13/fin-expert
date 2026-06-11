"""Pydantic request/response models for the REST API."""

from __future__ import annotations

from pydantic import BaseModel, Field


class Holding(BaseModel):
    symbol: str = Field(..., min_length=1, max_length=10)
    shares: float = Field(..., gt=0)
    asset_type: str = Field(default="stock")


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=4000)
    session_id: str = Field(..., min_length=1, max_length=128)
    holdings: list[Holding] | None = None
    goal_params: dict | None = None


class ChatResponse(BaseModel):
    content: str
    agent: str
    route: str = ""
    citations: list[dict] = []
    data: dict = {}


class PortfolioRequest(BaseModel):
    holdings: list[Holding] = Field(..., min_length=1)


class GoalRequest(BaseModel):
    target_amount: float = Field(..., gt=0)
    years: int = Field(..., ge=1, le=60)
    monthly_contribution: float = Field(..., ge=0)
    initial_amount: float = Field(default=0, ge=0)
    risk_profile: str = Field(default="moderate")
