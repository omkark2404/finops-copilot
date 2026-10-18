"""
Multi-Agent Orchestration Pipeline.

7-agent dependent pipeline:
  Data Quality → Cost Attribution → Anomaly Investigation
  → Opportunity → Optimization → Savings → Critic → Final Decision

Critical principle:
  Agents do NOT own numerical truth.
  All numbers come from deterministic analytics.
  LLM (Gemini) only explains and reasons over structured evidence.
  Application works without LLM (MockLLMProvider).
"""

from __future__ import annotations

import asyncio
import json
import uuid
from abc import ABC, abstractmethod

from .analytics import get_cost_drivers
from .anomaly import run_anomaly_detection
from .config import get_settings
from .optimization import run_optimization_analysis
from .schemas import (
    AgentRunDetail,
    AgentStatus,
    AgentType,
    AnomalyReport,
    CostAttributionReport,
    DataQualityReport,
    DecisionOutcome,
    FinalDecision,
    OpportunityReport,
    OptimizationAction,
    OptimizationRecommendation,
    PipelineRunDetail,
    RecommendationStatus,
    SavingsEstimate,
    ValidationReport,
)
from .time import utcnow

# ─── LLM Provider Abstraction ───────────────────────────────────────────────


class LLMProvider(ABC):
    """Optional Gemini explanations; deterministic offline mode is the default."""

    @abstractmethod
    async def explain(self, evidence: dict, task: str) -> str: ...

    @abstractmethod
    def is_available(self) -> bool: ...

    @property
    @abstractmethod
    def name(self) -> str: ...


class MockLLMProvider(LLMProvider):
    """Offline / demo mode provider. Returns structured summaries without LLM."""

    @property
    def name(self) -> str:
        return "MockLLMProvider"

    def is_available(self) -> bool:
        return False

    async def explain(self, evidence: dict, task: str) -> str:
        summary = json.dumps(
            {k: v for k, v in evidence.items() if not isinstance(v, (list, dict))},
            default=str,
        )
        return (
            f"[Demo Mode — Gemini API not configured] Task: {task}. Key evidence: {summary[:400]}"
        )


_EXTERNAL_FIELDS = frozenset(
    {
        "total_rows",
        "valid_rows",
        "duplicate_rows",
        "currency_consistent",
        "total_cost",
        "top_drivers",
        "concentration_score",
        "period_over_period_change_pct",
        "cost",
        "share_pct",
        "change_pct",
        "row_count",
        "total_anomalies",
        "critical_anomalies",
        "high_anomalies",
        "top_anomalies",
        "actual",
        "expected",
        "deviation_pct",
        "attribution_total",
        "total_opportunities",
        "total_potential_savings_estimate",
        "top_opportunities",
        "priority_score",
        "confidence",
        "opportunity",
        "rank",
        "potential_savings_estimate",
        "recommendation_count",
        "total_estimated_savings",
        "savings_count",
        "all_estimated",
        "validation_passed",
        "missing_evidence_count",
        "contradiction_count",
        "risk_count",
        "safe_to_proceed",
        "amount",
        "items",
        "total",
    }
)


def _numeric_evidence(value):
    # No account names, resource identifiers, arbitrary uploaded strings or prompts leave the app.
    if isinstance(value, bool) or isinstance(value, (int, float)):
        return value
    if isinstance(value, dict):
        return {
            str(k): _numeric_evidence(v)
            for k, v in value.items()
            if k in _EXTERNAL_FIELDS and isinstance(v, (int, float, bool, dict, list))
        }
    if isinstance(value, list):
        return [
            _numeric_evidence(v)
            for v in value[:10]
            if isinstance(v, (int, float, bool, dict, list))
        ]
    return None


def _numbers(value):
    import re
    from decimal import Decimal

    return {
        Decimal(x.replace(",", ""))
        for x in re.findall(r"(?<![A-Za-z])[-+]?\d[\d,]*(?:\.\d+)?", str(value))
    }


class GeminiProvider(LLMProvider):
    """Optional bounded narratives. Failed/ungrounded text is replaced with an offline explanation."""

    def __init__(self, api_key, model):
        from google import genai
        from google.genai import types

        settings = get_settings()
        self.client = genai.Client(
            api_key=api_key,
            http_options=types.HttpOptions(timeout=int(settings.llm_timeout_seconds * 1000)),
        )
        self.model = model
        self.usage = {
            "calls": 0,
            "input_tokens": 0,
            "output_tokens": 0,
            "failures": 0,
            "cost": None,
            "cost_note": "Token counts recorded; currency cost requires provider pricing/billing reconciliation",
        }
        self.degraded = False
        self.started = __import__("time").monotonic()

    @property
    def name(self):
        return f"Gemini/{self.model}"

    def is_available(self):
        return not self.degraded

    async def explain(self, evidence, task):
        import time

        from google.genai import types

        settings = get_settings()
        grounded = _numeric_evidence(evidence)
        remaining = settings.llm_run_timeout_seconds - (time.monotonic() - self.started)
        if self.usage["calls"] >= settings.llm_max_calls or remaining <= 0:
            self.degraded = True
            return "[Offline explanation: narrative call budget exhausted. Inspect structured evidence.]"
        self.usage["calls"] += 1
        started = time.monotonic()
        try:
            response = await asyncio.wait_for(
                self.client.aio.models.generate_content(
                    model=self.model,
                    contents=task + "\nNumeric evidence: " + json.dumps(grounded, allow_nan=False),
                    config=types.GenerateContentConfig(
                        max_output_tokens=300,
                        temperature=0,
                        system_instruction="Explain only supplied evidence. Do not invent causes or amounts. Narratives need human review.",
                    ),
                ),
                timeout=min(settings.llm_timeout_seconds, remaining),
            )
            tokens = response.usage_metadata
            if tokens:
                self.usage["input_tokens"] += tokens.prompt_token_count or 0
                self.usage["output_tokens"] += tokens.candidates_token_count or 0
            output = response.text or ""
            if not _numbers(output).issubset(_numbers(json.dumps(grounded))):
                raise ValueError("Narrative introduced an ungrounded number")
            return output
        except Exception:
            self.degraded = True
            self.usage["failures"] += 1
            return "[Offline explanation: narrative unavailable or numerical grounding failed. Inspect structured evidence.]"
        finally:
            self.usage["latency_seconds"] = round(
                self.usage.get("latency_seconds", 0) + time.monotonic() - started, 3
            )

    async def close(self):
        await self.client.aio.aclose()
        self.client.close()


def get_llm_provider():
    settings = get_settings()
    if settings.gemini_api_key and not settings.gemini_api_key.startswith("your_"):
        return GeminiProvider(settings.gemini_api_key, settings.gemini_model)
    return MockLLMProvider()


# ─── Agent Functions ─────────────────────────────────────────────────────────


def _make_run(pipeline_run_id: str, agent_type: AgentType) -> AgentRunDetail:
    return AgentRunDetail(
        id=str(uuid.uuid4()),
        pipeline_run_id=pipeline_run_id,
        agent_type=agent_type,
        status=AgentStatus.queued,
        started_at=None,
        completed_at=None,
        duration_seconds=None,
        input_summary={},
        output_summary={},
        confidence=None,
        error_message=None,
        retry_count=0,
    )


async def run_data_quality_agent(
    pipeline_run_id: str,
    dq_report: DataQualityReport,
    llm: LLMProvider,
) -> tuple[AgentRunDetail, bool]:
    """
    Agent 1: Data Quality.
    Determines if the dataset is usable. Fails pipeline if quality is insufficient.
    """
    run = _make_run(pipeline_run_id, AgentType.data_quality)
    run.status = AgentStatus.running
    run.started_at = utcnow()
    run.input_summary = {
        "dataset_id": dq_report.dataset_id,
        "total_rows": dq_report.total_rows,
    }

    usable = dq_report.overall_status.value != "FAIL"
    confidence = (
        0.95
        if dq_report.overall_status.value == "PASS"
        else (0.6 if dq_report.overall_status.value == "WARN" else 0.1)
    )

    evidence = {
        "overall_status": dq_report.overall_status.value,
        "total_rows": dq_report.total_rows,
        "valid_rows": dq_report.valid_rows,
        "duplicate_rows": dq_report.duplicate_rows,
        "issues": dq_report.issues,
        "warnings": dq_report.warnings,
        "currency_consistent": dq_report.currency_consistency,
    }

    explanation = await llm.explain(
        evidence,
        "Assess dataset quality and determine if it is safe to proceed with analysis.",
    )

    run.status = AgentStatus.degraded if getattr(llm, "degraded", False) else AgentStatus.succeeded
    run.completed_at = utcnow()
    run.duration_seconds = (run.completed_at - run.started_at).total_seconds()
    run.confidence = confidence
    run.output_summary = {
        "usable": usable,
        "status": dq_report.overall_status.value,
        "explanation": explanation[:500],
    }
    return run, usable


async def run_cost_attribution_agent(
    pipeline_run_id: str,
    attribution: CostAttributionReport,
    llm: LLMProvider,
) -> AgentRunDetail:
    """Agent 2: Cost Attribution. Identifies major cost drivers."""
    run = _make_run(pipeline_run_id, AgentType.cost_attribution)
    run.status = AgentStatus.running
    run.started_at = utcnow()

    evidence = {
        "total_cost": attribution.total_cost,
        "period": f"{attribution.period_start} to {attribution.period_end}",
        "top_drivers": [d.model_dump() for d in attribution.top_drivers[:5]],
        "concentration_score": attribution.concentration_score,
        "period_over_period_change_pct": attribution.period_over_period_change_pct,
    }

    explanation = await llm.explain(
        evidence,
        "Explain the major cost drivers and any notable patterns in the spend attribution.",
    )

    run.status = AgentStatus.degraded if getattr(llm, "degraded", False) else AgentStatus.succeeded
    run.completed_at = utcnow()
    run.duration_seconds = (run.completed_at - run.started_at).total_seconds()
    run.confidence = 0.9
    run.output_summary = {
        "total_cost": attribution.total_cost,
        "driver_count": len(attribution.top_drivers),
        "pop_change_pct": attribution.period_over_period_change_pct,
        "explanation": explanation[:500],
    }
    return run


async def run_anomaly_investigation_agent(
    pipeline_run_id: str,
    anomaly_report: AnomalyReport,
    attribution: CostAttributionReport,
    llm: LLMProvider,
) -> AgentRunDetail:
    """Agent 3: Anomaly Investigation. Investigates abnormal cost changes."""
    run = _make_run(pipeline_run_id, AgentType.anomaly_investigation)
    run.status = AgentStatus.running
    run.started_at = utcnow()

    critical = [a for a in anomaly_report.anomalies if a.severity.value == "critical"]
    high = [a for a in anomaly_report.anomalies if a.severity.value == "high"]

    evidence = {
        "total_anomalies": anomaly_report.total_anomalies,
        "critical_anomalies": len(critical),
        "high_anomalies": len(high),
        "top_anomalies": [
            {
                "entity": f"{a.entity_type}:{a.entity_value}",
                "actual": a.actual_cost,
                "expected": a.expected_cost,
                "deviation_pct": a.deviation_pct,
                "severity": a.severity.value,
                "method": a.method.value,
            }
            for a in (critical + high)[:5]
        ],
        "attribution_total": attribution.total_cost,
    }

    explanation = await llm.explain(
        evidence,
        "Investigate the detected anomalies. Which are most significant? What patterns suggest root causes?",
    )

    run.status = AgentStatus.degraded if getattr(llm, "degraded", False) else AgentStatus.succeeded
    run.completed_at = utcnow()
    run.duration_seconds = (run.completed_at - run.started_at).total_seconds()
    run.confidence = 0.8 if critical or high else 0.9
    run.output_summary = {
        "total_anomalies": anomaly_report.total_anomalies,
        "critical_count": len(critical),
        "high_count": len(high),
        "explanation": explanation[:500],
    }
    return run


async def run_opportunity_agent(
    pipeline_run_id: str,
    opp_report: OpportunityReport,
    llm: LLMProvider,
) -> AgentRunDetail:
    """Agent 4: Opportunity Identification."""
    run = _make_run(pipeline_run_id, AgentType.opportunity)
    run.status = AgentStatus.running
    run.started_at = utcnow()

    evidence = {
        "total_opportunities": opp_report.total_opportunities,
        "total_potential_savings_estimate": opp_report.total_potential_savings,
        "top_opportunities": [
            {
                "type": o.opportunity_type.value,
                "entity": o.entity,
                "description": o.description[:200],
                "priority_score": o.priority_score,
                "confidence": o.confidence,
            }
            for o in opp_report.opportunities[:5]
        ],
    }

    explanation = await llm.explain(
        evidence,
        "Summarize the top optimization opportunities identified from deterministic analysis.",
    )

    run.status = AgentStatus.degraded if getattr(llm, "degraded", False) else AgentStatus.succeeded
    run.completed_at = utcnow()
    run.duration_seconds = (run.completed_at - run.started_at).total_seconds()
    run.confidence = 0.75
    run.output_summary = {
        "total_opportunities": opp_report.total_opportunities,
        "estimated_savings": None,
        "explanation": explanation[:500],
    }
    return run


async def run_optimization_agent(
    pipeline_run_id: str,
    opp_report: OpportunityReport,
    attribution: CostAttributionReport,
    llm: LLMProvider,
) -> tuple[AgentRunDetail, list[OptimizationRecommendation]]:
    """Agent 5: Optimization. Produces ranked recommendations."""
    run = _make_run(pipeline_run_id, AgentType.optimization)
    run.status = AgentStatus.running
    run.started_at = utcnow()

    recommendations = []
    for i, opp in enumerate(opp_report.opportunities[:10]):
        action_desc = (
            f"Investigate {opp.entity}: review current usage patterns, "
            f"identify root cause of cost change, assess optimization options."
        )
        actions = [
            OptimizationAction(
                action_type="investigate",
                description=action_desc,
                rationale=opp.description,
                assumptions=[
                    "Investigation required before implementation",
                    "Billing data only — utilization data not available",
                ],
                confidence=opp.confidence,
            )
        ]

        explanation = await llm.explain(
            {"opportunity": opp.model_dump(), "rank": i + 1},
            "Formulate a specific optimization recommendation for this opportunity. Be honest about data limitations.",
        )

        rec = OptimizationRecommendation(
            id=str(uuid.uuid4()),
            opportunity_id=opp.id,
            dataset_id=opp.dataset_id,
            title=f"Investigate {opp.entity} ({opp.opportunity_type.value})",
            description=opp.description,
            actions=actions,
            priority_rank=i + 1,
            risk_level="low",  # Investigation only — no destructive actions
            evidence=opp.evidence,
            status=RecommendationStatus.pending,
            explanation=explanation,
        )
        recommendations.append(rec)

    run.status = AgentStatus.degraded if getattr(llm, "degraded", False) else AgentStatus.succeeded
    run.completed_at = utcnow()
    run.duration_seconds = (run.completed_at - run.started_at).total_seconds()
    run.confidence = 0.75
    run.output_summary = {"recommendation_count": len(recommendations)}
    return run, recommendations


async def run_savings_agent(
    pipeline_run_id: str,
    recommendations: list[OptimizationRecommendation],
    opp_report: OpportunityReport,
    llm: LLMProvider,
) -> tuple[AgentRunDetail, list[SavingsEstimate]]:
    """Agent 6: Savings Estimation. Deterministic calculations, LLM explains."""
    run = _make_run(pipeline_run_id, AgentType.savings)
    run.status = AgentStatus.running
    run.started_at = utcnow()

    # Billing anomalies do not establish an achievable saving. The user supplies
    # assumptions explicitly through the persisted scenario endpoint instead.
    savings_estimates = []
    total_est_savings = sum(e.estimated_savings for e in savings_estimates)

    evidence = {
        "recommendation_count": len(recommendations),
        "total_estimated_savings": total_est_savings,
        "note": "ESTIMATED SAVINGS — not realized savings. Requires implementation and validation.",
        "top_estimates": [
            {
                "entity": e.scenario_description,
                "savings": e.estimated_savings,
                "confidence": e.confidence,
            }
            for e in savings_estimates[:3]
        ],
    }

    explanation = await llm.explain(
        evidence,
        "Summarize the savings estimates. Clearly distinguish estimated from realized savings. Note all assumptions.",
    )

    run.status = AgentStatus.degraded if getattr(llm, "degraded", False) else AgentStatus.succeeded
    run.completed_at = utcnow()
    run.duration_seconds = (run.completed_at - run.started_at).total_seconds()
    run.confidence = 0.6
    run.output_summary = {
        "total_estimated_savings": round(total_est_savings, 2),
        "savings_count": len(savings_estimates),
        "note": "ESTIMATED",
        "explanation": explanation[:500],
    }
    return run, savings_estimates


async def run_critic_agent(
    pipeline_run_id: str,
    all_outputs: dict,
    recommendations: list[OptimizationRecommendation],
    llm: LLMProvider,
) -> tuple[AgentRunDetail, ValidationReport, FinalDecision]:
    """
    Agent 7: Critic / Validation.
    Validates evidence, detects contradictions, flags unsupported claims.
    Produces the final decision.
    """
    run = _make_run(pipeline_run_id, AgentType.critic)
    run.status = AgentStatus.running
    run.started_at = utcnow()

    checks_passed = []
    checks_failed = []
    contradictions = []
    missing_evidence = []
    unsupported_claims = []

    # Check 1: Data quality gate passed
    dq = all_outputs.get("data_quality_passed", False)
    if dq:
        checks_passed.append("Data quality gate: PASSED")
    else:
        checks_failed.append("Data quality gate: FAILED — pipeline should not have proceeded")

    # Check 2: Evidence present for each recommendation
    for rec in recommendations:
        if not rec.evidence:
            missing_evidence.append(f"Recommendation '{rec.title}' has no supporting evidence")
        else:
            checks_passed.append(f"Evidence present for: {rec.title[:50]}")

    # Each recommendation must retain its exact deterministic opportunity evidence.
    known = all_outputs.get("evidence_by_opportunity", {})
    for rec in recommendations:
        source = known.get(rec.opportunity_id)
        if source is None or rec.evidence != source:
            contradictions.append(f"Evidence does not match opportunity: {rec.id}")
        if not rec.actions:
            missing_evidence.append(f"No review action for recommendation: {rec.id}")

    # Check 3: Assumptions disclosed
    for rec in recommendations:
        for action in rec.actions:
            if action.assumptions:
                checks_passed.append(f"Assumptions disclosed for action: {action.action_type}")
            else:
                missing_evidence.append(f"No assumptions for action: {action.action_type}")

    # Check 4: No destructive actions
    for rec in recommendations:
        for action in rec.actions:
            destructive_keywords = [
                "delete",
                "terminate",
                "destroy",
                "shutdown",
                "remove",
            ]
            if any(kw in action.description.lower() for kw in destructive_keywords):
                checks_failed.append(
                    f"Recommendation contains potentially destructive action: {action.description[:100]}"
                )
            else:
                checks_passed.append(
                    f"Safety check: no destructive action in '{action.action_type}'"
                )

    # Check 5: Savings clearly labelled as ESTIMATED
    savings_data = all_outputs.get("savings_note", "")
    if "ESTIMATED" in str(savings_data).upper():
        checks_passed.append("Savings clearly labelled as ESTIMATED (not realized)")
    else:
        unsupported_claims.append("Savings estimates should be clearly labelled as ESTIMATED")

    recommendation_safe = not (
        checks_failed or missing_evidence or unsupported_claims or contradictions
    )
    confidence = 0.5 if recommendation_safe else 0.0  # checklist score, not calibrated probability

    validation = ValidationReport(
        checks_passed=checks_passed,
        checks_failed=checks_failed,
        contradictions=contradictions,
        missing_evidence=missing_evidence,
        unsupported_claims=unsupported_claims,
        recommendation_safe=recommendation_safe,
        confidence=round(confidence, 3),
    )

    # Final decision
    if not recommendation_safe:
        decision = DecisionOutcome.reject
        rationale = f"Critic rejected: {'; '.join(checks_failed[:3])}"
    elif recommendations:
        decision = DecisionOutcome.investigate
        rationale = f"{len(recommendations)} recommendations require human investigation; checklist score {confidence:.2f}"
    else:
        decision = DecisionOutcome.investigate
        rationale = "No actionable recommendations found. Further investigation recommended."

    evidence_summary = checks_passed[:5] + (
        [f"WARNINGS: {'; '.join(checks_failed[:2])}"] if checks_failed else []
    )
    top_rec_id = recommendations[0].id if recommendations else None

    final_decision = FinalDecision(
        pipeline_run_id=pipeline_run_id,
        recommendation_id=top_rec_id,
        decision=decision,
        rationale=rationale,
        evidence_summary=evidence_summary,
        confidence=round(confidence, 3),
        validated_by_critic=True,
        human_action=None,
        created_at=utcnow(),
    )

    critic_evidence = {
        "checks_passed": len(checks_passed),
        "checks_failed": len(checks_failed),
        "missing_evidence_items": len(missing_evidence),
        "recommendation_safe": recommendation_safe,
        "decision": decision.value,
    }

    explanation = await llm.explain(
        critic_evidence,
        "You are the critic agent. Provide a final validation summary. Be direct about any issues.",
    )

    run.status = AgentStatus.degraded if getattr(llm, "degraded", False) else AgentStatus.succeeded
    run.completed_at = utcnow()
    run.duration_seconds = (run.completed_at - run.started_at).total_seconds()
    run.confidence = confidence
    run.output_summary = {
        "decision": decision.value,
        "checks_passed": len(checks_passed),
        "checks_failed": len(checks_failed),
        "explanation": explanation[:500],
    }
    return run, validation, final_decision


async def run_pipeline(
    dataset_id: str,
    llm: LLMProvider | None = None,
) -> PipelineRunDetail:
    """Run the full 7-agent dependent pipeline for a dataset."""
    if llm is None:
        llm = get_llm_provider()

    pipeline_run_id = str(uuid.uuid4())
    started_at = utcnow()
    agent_runs = []

    # Pre-compute deterministic inputs

    import pandas as pd

    from .ingestion import validate_focus_data
    from .schemas import FocusVersion
    from .storage import download_dataset_parquet

    parquet_path = download_dataset_parquet(dataset_id)

    # Load data for validation
    df = pd.read_parquet(parquet_path)
    dq_report = validate_focus_data(df, FocusVersion.v1_0)
    dq_report.dataset_id = dataset_id

    # Agent 1: Data Quality
    dq_run, is_usable = await run_data_quality_agent(pipeline_run_id, dq_report, llm)
    agent_runs.append(dq_run)

    if not is_usable:
        return PipelineRunDetail(
            id=pipeline_run_id,
            dataset_id=dataset_id,
            status=AgentStatus.failed,
            started_at=started_at,
            completed_at=utcnow(),
            agent_runs=agent_runs,
            final_decision=None,
        )

    # Agent 2: Cost Attribution
    attribution = get_cost_drivers(dataset_id)
    attr_run = await run_cost_attribution_agent(pipeline_run_id, attribution, llm)
    agent_runs.append(attr_run)

    # Agent 3: Anomaly Investigation
    anomaly_report = run_anomaly_detection(dataset_id)
    anom_run = await run_anomaly_investigation_agent(
        pipeline_run_id, anomaly_report, attribution, llm
    )
    agent_runs.append(anom_run)

    # Agent 4: Opportunity
    opp_report = run_optimization_analysis(dataset_id, attribution, anomaly_report.anomalies)
    opp_run = await run_opportunity_agent(pipeline_run_id, opp_report, llm)
    agent_runs.append(opp_run)

    # Agent 5: Optimization
    opt_run, recommendations = await run_optimization_agent(
        pipeline_run_id, opp_report, attribution, llm
    )
    agent_runs.append(opt_run)

    # Agent 6: Savings
    sav_run, savings_estimates = await run_savings_agent(
        pipeline_run_id, recommendations, opp_report, llm
    )
    agent_runs.append(sav_run)

    # Agent 7: Critic
    all_outputs = {
        "data_quality_passed": is_usable,
        "evidence_by_opportunity": {o.id: o.evidence for o in opp_report.opportunities},
        "savings_note": "ESTIMATED SAVINGS",
        "total_estimated_savings": sum(e.estimated_savings for e in savings_estimates),
    }
    critic_run, validation, final_decision = await run_critic_agent(
        pipeline_run_id, all_outputs, recommendations, llm
    )
    agent_runs.append(critic_run)

    return PipelineRunDetail(
        id=pipeline_run_id,
        dataset_id=dataset_id,
        status=AgentStatus.degraded if getattr(llm, "degraded", False) else AgentStatus.succeeded,
        started_at=started_at,
        completed_at=utcnow(),
        agent_runs=agent_runs,
        final_decision=final_decision,
        recommendations=recommendations,
        savings_estimates=savings_estimates,
        validation=validation,
        llm_usage=getattr(llm, "usage", {"calls": 0, "provider": "offline"}),
    )
