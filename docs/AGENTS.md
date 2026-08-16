# CloudSpend Intelligence — Multi-Agent Pipeline Documentation

## 1. Agent Architecture

CloudSpend uses a 7-stage dependent pipeline where each agent receives structured Pydantic outputs from previous agents.

```
1. Data Quality Agent
       ↓
2. Cost Attribution Agent
       ↓
3. Anomaly Investigation Agent
       ↓
4. Opportunity Agent
       ↓
5. Optimization Agent
       ↓
6. Savings Agent
       ↓
7. Critic / Validation Agent → Final Decision
```

---

## 2. Agent Responsibilities

| Agent | Responsibility | Downstream Contract |
|---|---|---|
| **1. Data Quality** | Assesses dataset completeness, null rates, and currency uniformity | `is_usable: bool` |
| **2. Cost Attribution** | Identifies top cost drivers and concentration (HHI) | `CostAttributionReport` |
| **3. Anomaly Investigation** | Investigates statistical spikes and flags root-cause patterns | `AnomalyReport` |
| **4. Opportunity** | Formulates optimization candidates based on rule triggers | `OpportunityReport` |
| **5. Optimization** | Ranks actionable optimization recommendations with risk levels | `list[OptimizationRecommendation]` |
| **6. Savings** | Computes scenario projections (labelled as ESTIMATED SAVINGS) | `list[SavingsEstimate]` |
| **7. Critic / Validator** | Performs safety, evidence, and assumption verification | `ValidationReport`, `FinalDecision` |

---

## 3. Why Agents Are Distinct From Analytics
Analytics engines compute numerical truth (sums, z-scores, forecast matrices). Agents perform contextual reasoning over those pre-computed numerical contracts, explaining findings in natural language, checking cross-agent logic consistency, and ensuring recommendations are safe and non-destructive.

---

## 4. Critic Validation Rules
The Critic Agent checks:
1. Did the data quality gate pass?
2. Is evidence present for every recommendation?
3. Are assumptions explicitly disclosed?
4. Are any proposed actions destructive (e.g. resource deletion)?
5. Are savings figures clearly labelled as `ESTIMATED SAVINGS`?
