"""Portfolio analytics: valuation, allocation, diversification, and risk.

Pure calculation layer used by the Portfolio Analysis agent, the REST API,
and the MCP server. Metrics follow the project FAQ: total value, allocation
percentages, diversification score, and a simple risk assessment by asset type.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from src.core.logging import get_logger
from src.data.market_data import MarketDataUnavailable, get_market_data_service
from src.utils.validators import normalize_ticker, validate_positive

logger = get_logger(__name__)

# Risk weight per asset type (0 = cash-like, 1 = most volatile).
ASSET_RISK_WEIGHTS = {
    "stock": 0.9,
    "stock_etf": 0.7,
    "reit_etf": 0.75,
    "crypto": 1.0,
    "bond_etf": 0.25,
    "bond": 0.2,
    "cash": 0.0,
}
DEFAULT_RISK_WEIGHT = 0.7


@dataclass
class HoldingValue:
    symbol: str
    name: str
    shares: float
    price: float
    value: float
    allocation_pct: float
    asset_type: str
    change_percent: float = 0.0
    error: str | None = None


@dataclass
class PortfolioAnalysis:
    total_value: float
    holdings: list[HoldingValue]
    allocation_by_type: dict[str, float]
    diversification_score: float  # 0-100
    risk_score: float  # 0-100
    risk_level: str  # Conservative / Moderate / Aggressive
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "total_value": self.total_value,
            "holdings": [vars(h) for h in self.holdings],
            "allocation_by_type": self.allocation_by_type,
            "diversification_score": self.diversification_score,
            "risk_score": self.risk_score,
            "risk_level": self.risk_level,
            "warnings": self.warnings,
        }


def _herfindahl_diversification(allocations: list[float]) -> float:
    """Map allocation concentration to a 0-100 diversification score.

    Uses the normalized Herfindahl-Hirschman index: 1 holding -> 0,
    many equal holdings -> approaches 100.
    """
    if len(allocations) <= 1:
        return 0.0
    hhi = sum((a / 100.0) ** 2 for a in allocations)
    n = len(allocations)
    normalized = (hhi - 1.0 / n) / (1.0 - 1.0 / n)  # 0 (equal) .. 1 (concentrated)
    return round((1.0 - normalized) * 100, 1)


def analyze_portfolio(holdings: list[dict]) -> PortfolioAnalysis:
    """Value each holding at live prices and compute portfolio metrics.

    holdings: [{"symbol": "VTI", "shares": 10, "asset_type": "stock_etf"}, ...]
    """
    if not holdings:
        raise ValueError("Portfolio is empty")

    svc = get_market_data_service()
    valued: list[HoldingValue] = []
    warnings: list[str] = []

    for h in holdings:
        symbol = normalize_ticker(h["symbol"])
        shares = validate_positive(h.get("shares", 0), f"shares for {symbol}")
        asset_type = h.get("asset_type", "stock")
        try:
            quote = svc.get_quote(symbol)
            valued.append(
                HoldingValue(
                    symbol=symbol,
                    name=quote.name,
                    shares=shares,
                    price=quote.price,
                    value=round(quote.price * shares, 2),
                    allocation_pct=0.0,  # filled below
                    asset_type=asset_type,
                    change_percent=quote.change_percent,
                )
            )
            if quote.stale:
                warnings.append(f"Price for {symbol} is from cache and may be outdated.")
        except (MarketDataUnavailable, ValueError) as exc:
            logger.warning("Could not price %s: %s", symbol, exc)
            warnings.append(f"Could not fetch a price for {symbol}; it was excluded.")

    if not valued:
        raise MarketDataUnavailable("Could not price any holdings in the portfolio")

    total = sum(h.value for h in valued)
    for h in valued:
        h.allocation_pct = round(h.value / total * 100, 2)

    allocation_by_type: dict[str, float] = {}
    for h in valued:
        allocation_by_type[h.asset_type] = round(
            allocation_by_type.get(h.asset_type, 0) + h.allocation_pct, 2
        )

    diversification = _herfindahl_diversification([h.allocation_pct for h in valued])
    risk_score = round(
        sum(
            ASSET_RISK_WEIGHTS.get(h.asset_type, DEFAULT_RISK_WEIGHT) * h.allocation_pct
            for h in valued
        ),
        1,
    )
    risk_level = (
        "Conservative" if risk_score < 35 else "Moderate" if risk_score < 65 else "Aggressive"
    )

    # Concentration warnings beyond the numeric scores.
    for h in valued:
        if h.allocation_pct > 30:
            warnings.append(
                f"{h.symbol} is {h.allocation_pct:.0f}% of the portfolio — "
                "consider whether this concentration matches your risk tolerance."
            )
    if len(valued) < 3:
        warnings.append("Fewer than 3 holdings provides limited diversification.")

    return PortfolioAnalysis(
        total_value=round(total, 2),
        holdings=valued,
        allocation_by_type=allocation_by_type,
        diversification_score=diversification,
        risk_score=risk_score,
        risk_level=risk_level,
        warnings=warnings,
    )
