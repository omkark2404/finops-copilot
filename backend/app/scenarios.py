"""
Scenario Simulation Engine.

What-if calculations — ALL deterministic.
No LLM involvement in calculations.

Critical distinction:
  ESTIMATED SAVINGS != REALIZED SAVINGS
  All estimates are projections with stated assumptions.
  Never fabricate realized savings.
"""
from __future__ import annotations
from datetime import datetime
from typing import Optional

from .schemas import SavingsEstimate, ScenarioType


def simulate_usage_reduction(
    recommendation_id: str,
    current_cost: float,
    reduction_pct: float,
    time_horizon_days: int = 30,
    entity: str = "",
) -> SavingsEstimate:
    """What if usage decreases by X%?"""
    if not (0 < reduction_pct < 100):
        raise ValueError("reduction_pct must be between 0 and 100")
    projected = current_cost * (1 - reduction_pct / 100)
    savings = current_cost - projected
    return SavingsEstimate(
        recommendation_id=recommendation_id,
        scenario_type=ScenarioType.usage_reduction,
        scenario_description=f"Usage reduction of {reduction_pct:.1f}% for {entity or 'entity'}",
        current_cost=round(current_cost, 2),
        projected_cost=round(projected, 2),
        estimated_savings=round(savings, 2),
        estimated_savings_pct=round(reduction_pct, 2),
        assumptions=[
            f"Usage volume decreases by {reduction_pct:.1f}%",
            "Unit pricing remains constant",
            "No new workloads added",
            "Based on billing data only — utilization data not available",
            "ESTIMATED SAVINGS — not realized savings",
        ],
        confidence=0.5,  # Medium confidence — billing-only assumption
        time_horizon_days=time_horizon_days,
        created_at=datetime.utcnow(),
    )


def simulate_price_change(
    recommendation_id: str,
    current_cost: float,
    price_change_pct: float,
    time_horizon_days: int = 30,
    entity: str = "",
) -> SavingsEstimate:
    """What if unit pricing changes by X%?"""
    projected = current_cost * (1 + price_change_pct / 100)
    savings = current_cost - projected
    return SavingsEstimate(
        recommendation_id=recommendation_id,
        scenario_type=ScenarioType.price_change,
        scenario_description=f"Provider price change of {price_change_pct:+.1f}% for {entity or 'entity'}",
        current_cost=round(current_cost, 2),
        projected_cost=round(projected, 2),
        estimated_savings=round(savings, 2),
        estimated_savings_pct=round(-price_change_pct, 2),
        assumptions=[
            f"Unit pricing changes by {price_change_pct:+.1f}%",
            "Usage volume remains constant",
            "No contractual lock-in",
            "ESTIMATED SAVINGS — not realized savings",
        ],
        confidence=0.4,
        time_horizon_days=time_horizon_days,
        created_at=datetime.utcnow(),
    )


def simulate_recommendation_implementation(
    recommendation_id: str,
    current_cost: float,
    estimated_savings_pct: float,
    assumptions: list[str],
    confidence: float = 0.6,
    time_horizon_days: int = 30,
    entity: str = "",
) -> SavingsEstimate:
    """Simulate implementing a specific recommendation."""
    savings = current_cost * (estimated_savings_pct / 100)
    projected = current_cost - savings
    return SavingsEstimate(
        recommendation_id=recommendation_id,
        scenario_type=ScenarioType.recommendation_implementation,
        scenario_description=f"Implementing recommendation for {entity or 'entity'}",
        current_cost=round(current_cost, 2),
        projected_cost=round(projected, 2),
        estimated_savings=round(savings, 2),
        estimated_savings_pct=round(estimated_savings_pct, 2),
        assumptions=assumptions + ["ESTIMATED SAVINGS — not realized savings"],
        confidence=confidence,
        time_horizon_days=time_horizon_days,
        created_at=datetime.utcnow(),
    )


def run_scenario(
    recommendation_id: str,
    scenario_type: ScenarioType,
    config: dict,
) -> SavingsEstimate:
    """Dispatch to appropriate scenario simulation."""
    current_cost = float(config.get("current_cost", 0))
    entity = str(config.get("entity", ""))
    horizon = int(config.get("time_horizon_days", 30))

    if scenario_type == ScenarioType.usage_reduction:
        return simulate_usage_reduction(
            recommendation_id, current_cost,
            float(config.get("reduction_pct", 10)),
            horizon, entity
        )
    elif scenario_type == ScenarioType.price_change:
        return simulate_price_change(
            recommendation_id, current_cost,
            float(config.get("price_change_pct", -10)),
            horizon, entity
        )
    elif scenario_type == ScenarioType.recommendation_implementation:
        return simulate_recommendation_implementation(
            recommendation_id, current_cost,
            float(config.get("estimated_savings_pct", 10)),
            list(config.get("assumptions", [])),
            float(config.get("confidence", 0.6)),
            horizon, entity
        )
    else:
        raise ValueError(f"Unknown scenario type: {scenario_type}")
