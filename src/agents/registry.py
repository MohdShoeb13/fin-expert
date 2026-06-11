"""Single place to construct and look up the six agents."""

from __future__ import annotations

from functools import lru_cache

from src.agents.base_agent import BaseAgent
from src.agents.finance_qa import FinanceQAAgent
from src.agents.goal_planning import GoalPlanningAgent
from src.agents.market_analysis import MarketAnalysisAgent
from src.agents.news_synthesizer import NewsSynthesizerAgent
from src.agents.portfolio_analysis import PortfolioAnalysisAgent
from src.agents.tax_education import TaxEducationAgent

AGENT_CLASSES: dict[str, type[BaseAgent]] = {
    cls.name: cls
    for cls in (
        FinanceQAAgent,
        PortfolioAnalysisAgent,
        MarketAnalysisAgent,
        GoalPlanningAgent,
        NewsSynthesizerAgent,
        TaxEducationAgent,
    )
}


@lru_cache(maxsize=None)
def get_agent(name: str) -> BaseAgent:
    if name not in AGENT_CLASSES:
        raise KeyError(f"Unknown agent: {name}. Available: {sorted(AGENT_CLASSES)}")
    return AGENT_CLASSES[name]()
