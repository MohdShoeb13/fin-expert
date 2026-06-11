"""Financial goal projection math used by the Goal Planning agent and API."""

from __future__ import annotations

from dataclasses import dataclass

# Expected nominal annual returns by risk appetite (long-run historical bands).
RISK_PROFILES = {
    "conservative": {"annual_return": 0.045, "stock_allocation": 30, "volatility_note": "worst year ~ -10%"},
    "moderate": {"annual_return": 0.065, "stock_allocation": 60, "volatility_note": "worst year ~ -27%"},
    "aggressive": {"annual_return": 0.085, "stock_allocation": 90, "volatility_note": "worst year ~ -40%"},
}


@dataclass
class ProjectionPoint:
    year: int
    balance: float
    contributed: float
    growth: float


@dataclass
class GoalProjection:
    target_amount: float
    years: int
    risk_profile: str
    annual_return: float
    initial_amount: float
    monthly_contribution: float
    projected_final: float
    goal_met: bool
    shortfall: float
    required_monthly_for_goal: float
    timeline: list[ProjectionPoint]

    def to_dict(self) -> dict:
        d = vars(self).copy()
        d["timeline"] = [vars(p) for p in self.timeline]
        return d


def future_value(initial: float, monthly: float, annual_rate: float, years: int) -> float:
    """FV of a lump sum plus a monthly contribution annuity."""
    r = annual_rate / 12
    n = years * 12
    fv_lump = initial * (1 + r) ** n
    fv_contrib = monthly * (((1 + r) ** n - 1) / r) if r else monthly * n
    return fv_lump + fv_contrib


def required_monthly(target: float, initial: float, annual_rate: float, years: int) -> float:
    """Monthly contribution needed to reach target given the lump start."""
    r = annual_rate / 12
    n = years * 12
    fv_lump = initial * (1 + r) ** n
    remaining = max(0.0, target - fv_lump)
    if remaining == 0:
        return 0.0
    annuity_factor = (((1 + r) ** n - 1) / r) if r else n
    return remaining / annuity_factor


def project_goal(
    target_amount: float,
    years: int,
    monthly_contribution: float,
    initial_amount: float = 0.0,
    risk_profile: str = "moderate",
) -> GoalProjection:
    profile = risk_profile.lower()
    if profile not in RISK_PROFILES:
        raise ValueError(f"risk_profile must be one of {sorted(RISK_PROFILES)}")
    if years < 1 or years > 60:
        raise ValueError("years must be between 1 and 60")
    rate = RISK_PROFILES[profile]["annual_return"]

    timeline: list[ProjectionPoint] = []
    for year in range(1, years + 1):
        balance = future_value(initial_amount, monthly_contribution, rate, year)
        contributed = initial_amount + monthly_contribution * 12 * year
        timeline.append(
            ProjectionPoint(
                year=year,
                balance=round(balance, 2),
                contributed=round(contributed, 2),
                growth=round(balance - contributed, 2),
            )
        )

    final = timeline[-1].balance
    return GoalProjection(
        target_amount=target_amount,
        years=years,
        risk_profile=profile,
        annual_return=rate,
        initial_amount=initial_amount,
        monthly_contribution=monthly_contribution,
        projected_final=final,
        goal_met=final >= target_amount,
        shortfall=round(max(0.0, target_amount - final), 2),
        required_monthly_for_goal=round(
            required_monthly(target_amount, initial_amount, rate, years), 2
        ),
        timeline=timeline,
    )
