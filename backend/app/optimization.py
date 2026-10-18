"""Investigation candidates, not claims of achievable savings."""

import uuid

from .schemas import Opportunity, OpportunityReport, OpportunityType


def run_optimization_analysis(dataset_id, attribution, anomalies):
    candidates = []
    seen = set()
    for driver in attribution.top_drivers:
        if driver.change_pct is not None and driver.change_pct > 20:
            key = f"{driver.dimension}:{driver.value}"
            seen.add(key)
            candidates.append(
                Opportunity(
                    id=str(uuid.uuid4()),
                    dataset_id=dataset_id,
                    opportunity_type=OpportunityType.cost_growth,
                    entity=key,
                    description=f"Investigate a {driver.change_pct:.1f}% increase across comparable billing windows.",
                    evidence=attribution.evidence
                    + [f"Current cost: {driver.cost:.2f}; change: {driver.change_pct:.1f}%"],
                    potential_savings_estimate=None,
                    confidence=0.5,
                    priority_score=min(1, driver.change_pct / 100),
                )
            )
    for anomaly in anomalies:
        key = f"{anomaly.entity_type}:{anomaly.entity_value}"
        if key in seen or anomaly.deviation <= 0:
            continue
        seen.add(key)
        candidates.append(
            Opportunity(
                id=str(uuid.uuid4()),
                dataset_id=dataset_id,
                opportunity_type=OpportunityType.cost_spike,
                entity=key,
                description=f"Investigate unusual billed spend on {anomaly.detected_at}; statistical flag, not confirmed waste.",
                evidence=anomaly.supporting_evidence,
                potential_savings_estimate=None,
                confidence=anomaly.confidence,
                priority_score=min(1, abs(anomaly.deviation_pct) / 200),
            )
        )
    candidates.sort(key=lambda x: (-x.priority_score, x.entity))
    return OpportunityReport(
        dataset_id=dataset_id,
        opportunities=candidates,
        total_opportunities=len(candidates),
        total_potential_savings=None,
    )
