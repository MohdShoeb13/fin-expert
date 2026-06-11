"""Unit tests for portfolio analytics (src/data/portfolio.py)."""

import pytest

from src.data.market_data import MarketDataUnavailable
from src.data.portfolio import _herfindahl_diversification, analyze_portfolio

THREE_FUND = [
    {"symbol": "VTI", "shares": 10, "asset_type": "stock_etf"},
    {"symbol": "BND", "shares": 20, "asset_type": "bond_etf"},
    {"symbol": "AAPL", "shares": 5, "asset_type": "stock"},
]


class TestHerfindahl:
    def test_single_holding_scores_zero(self):
        assert _herfindahl_diversification([100.0]) == 0.0

    def test_equal_weights_score_100(self):
        assert _herfindahl_diversification([25.0, 25.0, 25.0, 25.0]) == 100.0

    def test_concentration_lowers_score(self):
        balanced = _herfindahl_diversification([50.0, 50.0])
        skewed = _herfindahl_diversification([90.0, 10.0])
        assert balanced > skewed


class TestAnalyzePortfolio:
    def test_valuation_and_allocation(self, patched_market):
        analysis = analyze_portfolio(THREE_FUND)
        # 10*300 + 20*70 + 5*200 = 5400 (fake prices from conftest).
        assert analysis.total_value == pytest.approx(5_400)
        assert sum(h.allocation_pct for h in analysis.holdings) == pytest.approx(100, abs=0.1)
        vti = next(h for h in analysis.holdings if h.symbol == "VTI")
        assert vti.value == pytest.approx(3_000)
        assert vti.allocation_pct == pytest.approx(55.56, abs=0.01)

    def test_allocation_by_type(self, patched_market):
        analysis = analyze_portfolio(THREE_FUND)
        assert set(analysis.allocation_by_type) == {"stock_etf", "bond_etf", "stock"}
        assert sum(analysis.allocation_by_type.values()) == pytest.approx(100, abs=0.1)

    def test_risk_level_bond_heavy_is_conservative(self, patched_market):
        analysis = analyze_portfolio(
            [{"symbol": "BND", "shares": 100, "asset_type": "bond_etf"},
             {"symbol": "VTI", "shares": 1, "asset_type": "stock_etf"}]
        )
        assert analysis.risk_level == "Conservative"

    def test_risk_level_all_stock_is_aggressive(self, patched_market):
        analysis = analyze_portfolio(
            [{"symbol": "AAPL", "shares": 10, "asset_type": "stock"},
             {"symbol": "SPY", "shares": 10, "asset_type": "stock"}]
        )
        assert analysis.risk_level == "Aggressive"
        assert analysis.risk_score == pytest.approx(90, abs=0.5)

    def test_concentration_warning(self, patched_market):
        analysis = analyze_portfolio(THREE_FUND)
        assert any("VTI" in w and "%" in w for w in analysis.warnings)

    def test_few_holdings_warning(self, patched_market):
        analysis = analyze_portfolio([{"symbol": "VTI", "shares": 1, "asset_type": "stock_etf"}])
        assert any("Fewer than 3" in w for w in analysis.warnings)
        assert analysis.diversification_score == 0.0

    def test_unpriceable_symbol_excluded_with_warning(self, patched_market):
        analysis = analyze_portfolio(
        [{"symbol": "VTI", "shares": 1, "asset_type": "stock_etf"},
             {"symbol": "ZZZZ", "shares": 1, "asset_type": "stock"}]
        )
        symbols = {h.symbol for h in analysis.holdings}
        assert symbols == {"VTI"}
        assert any("ZZZZ" in w for w in analysis.warnings)

    def test_empty_portfolio_raises(self, patched_market):
        with pytest.raises(ValueError, match="empty"):
            analyze_portfolio([])

    def test_all_providers_down_raises(self, monkeypatch, failing_market):
        import src.data.market_data as md

        monkeypatch.setattr(md, "_service", failing_market)
        with pytest.raises(MarketDataUnavailable):
            analyze_portfolio(THREE_FUND)

    def test_invalid_shares_raise(self, patched_market):
        with pytest.raises(ValueError, match="shares for AAPL"):
            analyze_portfolio([{"symbol": "AAPL", "shares": 0, "asset_type": "stock"}])

    def test_invalid_ticker_raises(self, patched_market):
        with pytest.raises(ValueError, match="Invalid ticker"):
            analyze_portfolio([{"symbol": "$$$", "shares": 1}])

    def test_to_dict_round_trip(self, patched_market):
        d = analyze_portfolio(THREE_FUND).to_dict()
        assert {"total_value", "holdings", "allocation_by_type",
                "diversification_score", "risk_score", "risk_level", "warnings"} <= d.keys()
        assert isinstance(d["holdings"][0], dict)
