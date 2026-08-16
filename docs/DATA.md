# finops-copilot — Data Provenance & Specification

## 1. Primary Specification: FOCUS
finops-copilot natively uses the **FinOps Open Cost and Usage Specification (FOCUS)** standard.

- **Specification URL**: https://focus.finops.org/
- **Specification Repository**: https://github.com/FinOps-Open-Cost-and-Usage-Spec/FOCUS_Spec
- **Supported Versions**: FOCUS 1.0, FOCUS 1.0.1

## 2. Canonical Cost Model Dimensions
Every raw FOCUS record is normalized into the canonical cost model:

### Dimensions
- `provider`: ProviderName (e.g. AWS, Azure, GCP)
- `account`: BillingAccountId
- `sub_account`: SubAccountId
- `service`: ServiceName
- `category`: ServiceCategory
- `resource`: ResourceId
- `region`: RegionId
- `sku`: SkuId
- `charge_category`: ChargeCategory (Usage, Purchase, Tax, Credit)
- `pricing_category`: PricingCategory (On-Demand, Committed, Dynamic)

### Measures
- `billed_cost`: Amount billed after discounts/credits.
- `effective_cost`: Amortized cost including upfront commitments.
- `list_cost`: Cost at list price before discounts.
- `contracted_cost`: Cost at contracted pricing rate.
- `quantity`: ConsumedQuantity.

### Time
- `charge_period_start`, `charge_period_end`
- `billing_period_start`, `billing_period_end`

## 3. Data Provenance & Validation
At ingestion time, finops-copilot records:
- Source URL / provider origin
- Content SHA-256 hash
- Total row count & valid row count
- Ingestion timestamp
- Date range coverage
- Currency consistency
- Field null rates

## 4. Synthetic Data Policy
Synthetic billing data is **STRICTLY FORBIDDEN** for analytics, training, evaluation, or business metrics. Synthetic fixtures are permitted only in `backend/tests/` for isolated unit tests and are labelled:
`SYNTHETIC TEST FIXTURE — NOT REAL BILLING DATA`
