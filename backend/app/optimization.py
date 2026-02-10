"""
Deterministic Optimization Engine.

Rules-based opportunity detection from billing data.
NO LLM involvement in opportunity scoring or rule logic.

Critical Honesty Rule:
  Never say 'underutilized' without utilization data.
  We only have billing data, NOT resource metrics.
  Always say: 'candidate for investigation because billed cost
  increased X% while billed quantity changed Y%'
"""
from __future__ import annotations
import uuid
from pathlib import Path
from typing import Optional

from .config import get_settings
from .db import get_duck
from .schemas import (
    AnomalyDetail, AnomalySeverity, CostAttributionReport,
    Opportunity, OpportunityReport, OpportunityType
)


def _score_opportunity(evidence_count: int, deviation_pct: float, cost: float) -> float:
    """Simple priority score: higher = more urgent."""
    evidence_weight = min(1.0, evidence_count / 5)
    deviation_weight = min(1.0, abs(deviation_pct) / 100)
    cost_weight = min(1.0, cost / 10000)
    return round((evidence_weight * 0.3 + deviation_weight * 0.4 + cost_weight * 0.3), 4)


def detect_cost_growth_opportunities(
    dataset_id: str,
    attribution: CostAttributionReport,
    threshold_pct: float = 20.0,
) -> list[Opportunity]:
    """Flag entities with >20% period-over-period cost growth."""
    opportunities = []
    for driver in attribution.top_drivers:
        if driver.change_pct is not None and abs(driver.change_pct) >= threshold_pct:
            cost_val = driver.cost
            opp = Opportunity(
                id=str(uuid.uuid4()),
                dataset_id=dataset_id,
                opportunity_type=OpportunityType.cost_growth,
                entity=f"{driver.dimension}:{driver.value}",
                description=(
                    f"{driver.value} ({driver.dimension}) is a candidate for investigation. "
                    f"Billed cost changed {driver.change_pct:+.1f}% period-over-period "
                    f"(${cost_val:,.2f} current spend, {driver.share_pct:.1f}% of total)."
                ),
                evidence=[
                    f"Dimension: {driver.dimension}",
                    f"Entity: {driver.value}",
                    f"Current period cost: ${cost_val:,.2f}",
                    f"Period-over-period change: {driver.change_pct:+.1f}%",
                    f"Share of total spend: {driver.share_pct:.1f}%",
                    f"Data source: deterministic cost analytics",
                ],
                potential_savings_estimate=cost_val * min(0.3, abs(driver.change_pct) / 200),
                confidence=0.7,
                priority_score=_score_opportunity(5, driver.change_pct, cost_val),
            )
            opportunities.append(opp)
    return opportunities


def detect_anomaly_based_opportunities(
    dataset_id: str,
    anomalies: list[AnomalyDetail],
) -> list[Opportunity]:
    """Convert high/critical anomalies into investigation opportunities."""
    opportunities = []
    for anomaly in anomalies:
        if anomaly.severity not in (AnomalySeverity.high, AnomalySeverity.critical):
            continue
        opp = Opportunity(
            id=str(uuid.uuid4()),
            dataset_id=dataset_id,
            opportunity_type=OpportunityType.cost_spike,
            entity=f"{anomaly.entity_type}:{anomaly.entity_value}",
            description=(
                f"{anomaly.entity_value} ({anomaly.entity_type}) had a {anomaly.severity.value} cost spike. "
                f"Billed cost was ${anomaly.actual_cost:,.2f} vs expected ${anomaly.expected_cost:,.2f} "
                f"({anomaly.deviation_pct:+.1f}%). This is a candidate for investigation."
            ),
            evidence=anomaly.supporting_evidence,
            potential_savings_estimate=max(0, anomaly.actual_cost - anomaly.expected_cost),
            confidence=anomaly.confidence,
            priority_score=_score_opportunity(
                len(anomaly.supporting_evidence), anomaly.deviation_pct, anomaly.actual_cost
            ),
        )
        opportunities.append(opp)
    return opportunities


def detect_concentration_opportunities(
    dataset_id: str,
    attribution: CostAttributionReport,
    concentration_threshold: float = 0.6,
) -> list[Opportunity]:
    """Flag concentrated spend (top entity > threshold% of total)."""
    opportunities = []
    if attribution.concentration_score >= concentration_threshold:
        top = attribution.top_drivers[0] if attribution.top_drivers else None
        if top:
            opp = Opportunity(
                id=str(uuid.uuid4()),
                dataset_id=dataset_id,
                opportunity_type=OpportunityType.cost_concentration,
                entity=f"{top.dimension}:{top.value}",
                description=(
                    f"Spend is concentrated: {top.value} ({top.dimension}) represents "
                    f"{top.share_pct:.1f}% of total spend. High concentration may indicate "
                    f"dependency risk or optimization opportunity."
                ),
                evidence=[
                    f"HHI concentration score: {attribution.concentration_score:.3f}",
                    f"Top entity: {top.value} ({top.dimension}) = {top.share_pct:.1f}% of spend",
                    f"Total spend: ${attribution.total_cost:,.2f}",
                ],
                potential_savings_estimate=0.0,  # Cannot estimate without more context
                confidence=0.6,
                priority_score=_score_opportunity(3, attribution.concentration_score * 100, attribution.total_cost),
            )
            opportunities.append(opp)
    return opportunities


def detect_quantity_growth_opportunities(dataset_id: str) -> list[Opportunity]:
    """Detect cases where cost grew faster than quantity (pricing change or new resources)."""
    from .storage import download_dataset_parquet
    parquet_path = download_dataset_parquet(dataset_id)
    duck = get_duck()

    opportunities = []
    try:
        if not _has_quantity(duck, parquet_path):
            return []

        rows = duck.execute(f"""
            SELECT
                COALESCE(CAST(service AS VARCHAR), 'unknown') as svc,
                DATE_TRUNC('month', charge_period_start) as month,
                SUM(billed_cost) as cost,
                SUM(quantity) as qty
            FROM read_parquet('{parquet_path}')
            WHERE quantity IS NOT NULL AND quantity > 0
            GROUP BY svc, DATE_TRUNC('month', charge_period_start)
            ORDER BY svc, month
        """).fetchdf()

        if rows.empty:
            return []

        for svc, grp in rows.groupby('svc'):
            if len(grp) < 2:
                continue
            grp = grp.sort_values('month')
            last = grp.iloc[-1]
            prev = grp.iloc[-2]
            cost_change = (last['cost'] - prev['cost']) / prev['cost'] * 100 if prev['cost'] > 0 else 0
            qty_change = (last['qty'] - prev['qty']) / prev['qty'] * 100 if prev['qty'] > 0 else 0
            if cost_change > 15 and cost_change > qty_change * 1.5:
                opp = Opportunity(
                    id=str(uuid.uuid4()),
                    dataset_id=dataset_id,
                    opportunity_type=OpportunityType.quantity_growth,
                    entity=f"service:{svc}",
                    description=(
                        f"{svc} is a candidate for investigation: billed cost increased "
                        f"{cost_change:.1f}% while billed quantity changed {qty_change:.1f}%. "
                        f"This may indicate a pricing change, tier upgrade, or new resource usage."
                    ),
                    evidence=[
                        f"Cost change: {cost_change:+.1f}%",
                        f"Quantity change: {qty_change:+.1f}%",
                        f"Current month cost: ${last['cost']:,.2f}",
                        f"Note: This analysis is based on billing data only. Utilization data is not available.",
                    ],
                    potential_savings_estimate=float(last['cost']) * 0.1,
                    confidence=0.6,
                    priority_score=_score_opportunity(4, cost_change, float(last['cost'])),
                )
                opportunities.append(opp)
    except Exception:
        pass
    return opportunities


def _has_quantity(duck, parquet_path) -> bool:
    try:
        r = duck.execute(f"SELECT SUM(quantity) FROM read_parquet('{parquet_path}') LIMIT 1").fetchone()
        return r[0] is not None
    except Exception:
        return False


def run_optimization_analysis(
    dataset_id: str,
    attribution: CostAttributionReport,
    anomalies: list[AnomalyDetail],
) -> OpportunityReport:
    """Run all opportunity detection rules and rank results."""
    all_opportunities = []

    # Rule 1: Cost growth > 20%
    all_opportunities.extend(detect_cost_growth_opportunities(dataset_id, attribution))

    # Rule 2: High/critical anomalies
    all_opportunities.extend(detect_anomaly_based_opportunities(dataset_id, anomalies))

    # Rule 3: Spend concentration
    all_opportunities.extend(detect_concentration_opportunities(dataset_id, attribution))

    # Rule 4: Cost/quantity divergence
    all_opportunities.extend(detect_quantity_growth_opportunities(dataset_id))

    # Sort by priority score descending
    all_opportunities.sort(key=lambda o: o.priority_score, reverse=True)

    total_potential = sum(o.potential_savings_estimate for o in all_opportunities)

    return OpportunityReport(
        dataset_id=dataset_id,
        opportunities=all_opportunities[:50],
        total_opportunities=len(all_opportunities),
        total_potential_savings=round(total_potential, 2),
    )
