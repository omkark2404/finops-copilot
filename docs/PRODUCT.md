# CloudSpend Intelligence — Product Documentation

## 1. Problem Statement
Modern multi-cloud environments generate massive billing datasets containing millions of line items. Engineering teams and FinOps analysts struggle to:
1. Identify where technology spend is going.
2. Understand why spend changed month-over-month.
3. Detect anomalous cost spikes before receiving end-of-month bills.
4. Formulate technically sound, auditable optimization recommendations.
5. Estimate savings without relying on black-box AI claims.

## 2. Target Users & Jobs-to-be-Done (JTBD)
- **FinOps Practitioners**: Need automated FOCUS data ingestion, statistical anomaly detection, and auditable optimization workflows.
- **Engineering Managers**: Need clear visibility into service-level spend drivers without manual SQL querying.
- **Executives & VPs of Infrastructure**: Need high-level forecasting and budget variance tracking.

## 3. Core Product Loop
```
OBSERVE → EXPLAIN → DETECT → DIAGNOSE → OPTIMIZE → ESTIMATE → VALIDATE → DECIDE
```

## 4. Key Value Propositions
- **Public FOCUS Specification Support**: Schema-aware ingestion for FOCUS 1.0 and 1.0.1.
- **Deterministic Truth**: Every number originates from SQL or statistical algorithms — zero hallucinated financial figures.
- **Auditable Agent Pipeline**: 7-stage agent reasoning pipeline with a dedicated Critic agent to prevent unsupported claims.
- **Human-in-the-Loop Safety**: CloudSpend is a decision-support platform; it never automatically modifies or deletes production infrastructure.

## 5. Non-Goals
- Cloud resource execution/deletion (safety rule).
- Real-time streaming billing (FOCUS is billing-period based).
- Training custom LLMs from scratch.
