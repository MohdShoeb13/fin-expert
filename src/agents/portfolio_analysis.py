"""Portfolio Analysis Agent: values holdings and explains the metrics."""

from __future__ import annotations

import json

from langchain_core.messages import BaseMessage

from src.agents.base_agent import AgentResponse, BaseAgent
from src.data.market_data import MarketDataUnavailable
from src.data.portfolio import analyze_portfolio


class PortfolioAnalysisAgent(BaseAgent):
    name = "portfolio_analysis"
    description = "Analyzes a user's portfolio: value, allocation, diversification, risk."

    @property
    def system_prompt(self) -> str:
        return (
            "You are a portfolio education specialist. You receive computed portfolio "
            "metrics as JSON: total value, per-holding allocations, allocation by asset "
            "type, a diversification score (0-100, higher = more diversified), a risk "
            "score (0-100) with level, and warnings. Explain what the numbers mean for a "
            "beginner: comment on concentration, diversification, and how the risk level "
            "relates to time horizon. Discuss principles (e.g. 'concentrated positions "
            "increase risk'), never 'buy X' or 'sell Y'. Keep it structured and concise."
        )

    def respond(self, query: str, history: list[BaseMessage] | None = None, **kwargs) -> AgentResponse:
        holdings = kwargs.get("holdings") or []
        if not holdings:
            return self._finalize(
                "I'd be happy to analyze your portfolio! Please share your holdings — "
                "for each one I need the ticker symbol, number of shares, and ideally the "
                "type (stock, ETF, bond fund...). For example: '50 shares of AAPL and "
                "20 shares of BND'. You can also use the Portfolio tab to enter them."
            )
        try:
            analysis = analyze_portfolio(holdings)
        except (MarketDataUnavailable, ValueError) as exc:
            return self._finalize(
                f"I couldn't complete the analysis: {exc}. Please check the ticker "
                "symbols and try again in a moment."
            )

        metrics = analysis.to_dict()
        context = f"Computed portfolio metrics:\n{json.dumps(metrics, indent=2)}"
        text = self._invoke(self._build_messages(query or "Analyze my portfolio.", history, context))
        return self._finalize(text, data={"analysis": metrics})
