# CloudSpend Intelligence — Machine Learning & Statistical Methods

## 1. Anomaly Detection Engine

Anomalies are detected purely through statistical and algorithmic methods without LLM involvement.

### Algorithms Implemented
1. **Robust Z-score (Median / MAD)**: Primary method. Uses median and Median Absolute Deviation (MAD) to detect spikes resistant to historical outliers.
   $$\text{Modified } Z = \frac{0.6745 \cdot (X_i - \text{Median})}{\text{MAD}}$$
2. **EWMA (Exponentially Weighted Moving Average)**: Tracks exponential trend and flags points exceeding span-based standard deviation bounds.
3. **Rolling Z-score**: 14-day rolling mean and standard deviation window.

### Severity Classification
- **Low**: Deviation < 25%
- **Medium**: Deviation 25% – 50%
- **High**: Deviation 50% – 100%
- **Critical**: Deviation > 100%

---

## 2. Time-Series Forecasting

### Model Progression
1. **Naive Baseline**: Uses last observed value.
2. **Moving Average**: 7-day rolling mean.
3. **Exponential Smoothing**: Holt-Winters exponential smoothing via `statsmodels`.
4. **LightGBM Regressor**: Gradient-boosted tree model trained on temporal lag and calendar features.

### Strict Temporal Leakage Prevention
To prevent temporal data leakage:
- Time-series records are **never randomly shuffled**.
- Split strategy: **Train (60%) → Validation (20%) → Test (20%)**.
- All lag features ($t-1, t-7, t-14, t-28$) and rolling means are computed strictly from historical timestamps $t' \le t$.
- If LightGBM fails to outperform naive/moving-average baseline on validation WAPE, the system automatically falls back to simpler models.

### Evaluation Metrics
- **MAE** (Mean Absolute Error)
- **RMSE** (Root Mean Squared Error)
- **WAPE** (Weighted Absolute Percentage Error):
  $$\text{WAPE} = \frac{\sum |y_i - \hat{y}_i|}{\sum |y_i|}$$
- **Bias**: Mean residual ($y_i - \hat{y}_i$).
