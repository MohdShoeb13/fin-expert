"""Sample portfolios for demos, testing, and evaluator walkthroughs."""

SAMPLE_PORTFOLIOS = {
    "beginner_balanced": {
        "name": "Beginner Balanced",
        "holdings": [
            {"symbol": "VTI", "shares": 30, "asset_type": "stock_etf"},
            {"symbol": "VXUS", "shares": 25, "asset_type": "stock_etf"},
            {"symbol": "BND", "shares": 20, "asset_type": "bond_etf"},
        ],
    },
    "tech_concentrated": {
        "name": "Tech Concentrated (high risk)",
        "holdings": [
            {"symbol": "AAPL", "shares": 50, "asset_type": "stock"},
            {"symbol": "MSFT", "shares": 30, "asset_type": "stock"},
            {"symbol": "NVDA", "shares": 40, "asset_type": "stock"},
            {"symbol": "GOOGL", "shares": 20, "asset_type": "stock"},
        ],
    },
    "income_focused": {
        "name": "Income Focused",
        "holdings": [
            {"symbol": "SCHD", "shares": 60, "asset_type": "stock_etf"},
            {"symbol": "VNQ", "shares": 30, "asset_type": "reit_etf"},
            {"symbol": "BND", "shares": 50, "asset_type": "bond_etf"},
            {"symbol": "VTIP", "shares": 25, "asset_type": "bond_etf"},
        ],
    },
}
