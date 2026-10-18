# Staged evidence workflow

The historical API uses agent names for compatibility, but these are seven workflow functions, not autonomous collaborating agents.

1. Data quality decides whether analysis may continue.
2. Cost attribution reports deterministic spend and service HHI.
3. Statistical anomaly evidence identifies unusual prior-baseline deviations.
4. Opportunity ranking creates investigation candidates, not automatic savings estimates.
5. Investigation recommendations carry original opportunity evidence and explicit assumptions.
6. Scenario boundary states that savings need user-supplied assumptions; the pipeline invents none.
7. A deterministic checklist verifies dataset quality, exact evidence matching, action assumptions and non-destructive descriptions. Missing/contradictory evidence rejects the checklist. Passing requires human investigation, not automatic approval.

The checklist is not independent proof of root cause, numerical model validity or narrative truth. Its heuristic score is not a probability. Human approval is recorded through an authenticated endpoint and never modifies cloud resources.

Gemini is optional and receives numeric/bool aggregates only. A per-run call budget, request deadline and output-token bound apply. Unknown narrative numbers are rejected. Runtime failures or budget exhaustion produce degraded offline text and usage counters, not false successful reasoning. Text still requires review. No hallucination-free guarantee is made.
