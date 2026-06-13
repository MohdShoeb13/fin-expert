"""Goal Planning Agent: projections that respect the user's risk appetite."""

from __future__ import annotations

import json
import re

from langchain_core.messages import BaseMessage

from src.agents.base_agent import AgentResponse, BaseAgent
from src.utils.projections import RISK_PROFILES, project_goal


def _parse_amount(text: str) -> float | None:
    m = re.search(r"\$?\s*([\d,]+(?:\.\d+)?)\s*([kKmM]?)", text)
    if not m:
        return None
    value = float(m.group(1).replace(",", ""))
    suffix = m.group(2).lower()
    return value * (1_000 if suffix == "k" else 1_000_000 if suffix == "m" else 1)


def extract_goal_params(query: str) -> dict:
    """Best-effort extraction of goal parameters from free text."""
    params: dict = {}
    lowered = query.lower()

    target = re.search(r"(?:save|reach|need|goal of|target of|have)\s*\$?\s*([\d,]+(?:\.\d+)?)\s*([kKmM]?)", query, re.I)
    if target:
        params["target_amount"] = _parse_amount(target.group(0))
    years = re.search(r"(\d{1,2})\s*(?:years|yrs|year)", lowered)
    if years:
        params["years"] = int(years.group(1))
    monthly = re.search(r"\$?\s*([\d,]+(?:\.\d+)?)\s*(?:per month|a month|/month|monthly)", lowered)
    if monthly:
        params["monthly_contribution"] = float(monthly.group(1).replace(",", ""))
    for profile in RISK_PROFILES:
        if profile in lowered:
            params["risk_profile"] = profile
    if "low risk" in lowered or "safe" in lowered:
        params.setdefault("risk_profile", "conservative")
    if "high risk" in lowered:
        params.setdefault("risk_profile", "aggressive")
    return params


class GoalPlanningAgent(BaseAgent):
    name = "goal_planning"
    description = "Helps plan financial goals with projections by risk appetite."

    @property
    def system_prompt(self) -> str:
        return (
            "You are a goal-planning educator. When projection JSON is provided, walk the "
            "user through it: the projected final balance vs. their target, how much comes "
            "from contributions vs. compound growth, and the required monthly amount if "
            "there's a shortfall. Mention the assumed annual return for their risk profile "
            "and its volatility note, and stress that projections are estimates, not "
            "guarantees. If parameters are missing, ask for them conversationally: target "
            "amount, time horizon in years, monthly contribution, starting amount, and "
            "risk appetite (conservative / moderate / aggressive)."
        )

    def respond(self, query: str, history: list[BaseMessage] | None = None, **kwargs) -> AgentResponse:
        params = {**extract_goal_params(query), **{k: v for k, v in kwargs.items() if v is not None}}
        params.pop("symbols", None)

        required = {"target_amount", "years", "monthly_contribution"}
        # Check presence, not truthiness — a $0 monthly contribution is valid.
        missing = required - {k for k, v in params.items() if v is not None}
        if missing:
            text = self._invoke(
                self._build_messages(
                    query,
                    history,
                    f"Known parameters so far: {json.dumps(params)}. "
                    f"Missing: {sorted(missing)}. Ask the user for the missing pieces.",
                )
            )
            return self._finalize(text)

        projection = project_goal(
            target_amount=float(params["target_amount"]),
            years=int(params["years"]),
            monthly_contribution=float(params["monthly_contribution"]),
            initial_amount=float(params.get("initial_amount", 0) or 0),
            risk_profile=params.get("risk_profile", "moderate"),
        )
        profile_info = RISK_PROFILES[projection.risk_profile]
        context = (
            f"Projection results:\n{json.dumps(projection.to_dict(), indent=2)}\n"
            f"Risk profile details: {json.dumps(profile_info)}"
        )
        text = self._invoke(self._build_messages(query, history, context))
        return self._finalize(text, data={"projection": projection.to_dict()})
