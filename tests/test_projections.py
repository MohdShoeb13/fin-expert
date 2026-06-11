"""Unit tests for goal projection math (src/utils/projections.py)."""

import math

import pytest

from src.utils.projections import (
    RISK_PROFILES,
    future_value,
    project_goal,
    required_monthly,
)


class TestFutureValue:
    def test_lump_sum_only(self):
        # $10k at 6% for 10 years, monthly compounding.
        fv = future_value(10_000, 0, 0.06, 10)
        assert fv == pytest.approx(10_000 * (1 + 0.06 / 12) ** 120)

    def test_contributions_only(self):
        fv = future_value(0, 100, 0.06, 1)
        # 12 contributions of $100 must exceed $1,200 with growth.
        assert 1_200 < fv < 1_300

    def test_zero_rate(self):
        assert future_value(1_000, 100, 0.0, 2) == pytest.approx(1_000 + 100 * 24)

    def test_combined_is_sum_of_parts(self):
        combined = future_value(5_000, 200, 0.05, 8)
        parts = future_value(5_000, 0, 0.05, 8) + future_value(0, 200, 0.05, 8)
        assert combined == pytest.approx(parts)


class TestRequiredMonthly:
    def test_round_trip_with_future_value(self):
        monthly = required_monthly(500_000, 10_000, 0.065, 20)
        assert future_value(10_000, monthly, 0.065, 20) == pytest.approx(500_000, rel=1e-9)

    def test_zero_when_lump_covers_target(self):
        assert required_monthly(10_000, 100_000, 0.05, 10) == 0.0

    def test_zero_rate(self):
        # No growth: need exactly target/months.
        assert required_monthly(12_000, 0, 0.0, 1) == pytest.approx(1_000)


class TestProjectGoal:
    def test_basic_projection(self):
        p = project_goal(100_000, 10, 500, initial_amount=5_000, risk_profile="moderate")
        assert p.years == 10
        assert p.risk_profile == "moderate"
        assert p.annual_return == RISK_PROFILES["moderate"]["annual_return"]
        assert len(p.timeline) == 10
        assert p.projected_final == p.timeline[-1].balance

    def test_timeline_is_monotonic(self):
        p = project_goal(100_000, 15, 300)
        balances = [pt.balance for pt in p.timeline]
        assert balances == sorted(balances)

    def test_timeline_growth_accounting(self):
        p = project_goal(50_000, 5, 400, initial_amount=2_000)
        for pt in p.timeline:
            assert pt.growth == pytest.approx(pt.balance - pt.contributed, abs=0.01)

    def test_goal_met_and_shortfall(self):
        met = project_goal(10_000, 10, 500)
        assert met.goal_met is True
        assert met.shortfall == 0.0

        unmet = project_goal(10_000_000, 5, 100)
        assert unmet.goal_met is False
        assert unmet.shortfall > 0
        assert unmet.required_monthly_for_goal > 100

    def test_aggressive_beats_conservative(self):
        kwargs = dict(target_amount=100_000, years=20, monthly_contribution=300)
        agg = project_goal(**kwargs, risk_profile="aggressive")
        con = project_goal(**kwargs, risk_profile="conservative")
        assert agg.projected_final > con.projected_final

    def test_invalid_risk_profile(self):
        with pytest.raises(ValueError, match="risk_profile"):
            project_goal(100_000, 10, 500, risk_profile="yolo")

    def test_invalid_years(self):
        with pytest.raises(ValueError, match="years"):
            project_goal(100_000, 0, 500)
        with pytest.raises(ValueError, match="years"):
            project_goal(100_000, 61, 500)

    def test_to_dict_serializable(self):
        d = project_goal(100_000, 3, 500).to_dict()
        assert isinstance(d["timeline"], list)
        assert isinstance(d["timeline"][0], dict)
        assert {"year", "balance", "contributed", "growth"} <= d["timeline"][0].keys()

    def test_known_scenario(self):
        # $800/mo for 20 years at moderate 6.5% -> ~ $390k of growth+contrib.
        p = project_goal(500_000, 20, 800, risk_profile="moderate")
        assert p.projected_final == pytest.approx(
            future_value(0, 800, 0.065, 20), rel=1e-6
        )
        assert not math.isnan(p.required_monthly_for_goal)
