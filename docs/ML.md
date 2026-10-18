# Statistical methods and forecast evaluation

Anomaly baselines use previous observations only. Robust median/MAD uses up to 28 prior observations; rolling/EWMA methods also shift history first. A constant prior history uses an explicit deviation rule. Scores are heuristics, not calibrated probabilities. Missing observed days are not presumed zero. Anomaly counts do not measure precision or recall; no labeled real-data performance is claimed.

Forecast input must contain at least five unique finite daily observations with complete calendar coverage. Missing days cause an actionable error. Values are not silently filled with zeros.

Candidates: last-value naive, seven-observation moving average, eligible Holt-Winters and LightGBM. LightGBM requires at least 60 training observations and shares one feature generator between training and recursive inference, including sample standard deviation. Models use a 60/20/20 temporal split. Each validation candidate predicts recursively from the same fixed origin; selection uses validation MAE, not test data. The selected candidate is fit on train+validation to predict the untouched test window. Final future predictions refit on all observed data.

Returned metrics are untouched-test MAE, RMSE, WAPE and predicted-minus-actual bias; zero-denominator WAPE is unavailable. Baseline metrics use the same test window. Metadata records validation/test horizons and failures. Those horizons can differ from the user-requested future horizon; the UI discloses this, and no claim of validated 90-day accuracy follows from a shorter test.

This is a single fixed-origin evaluation, not a full rolling-origin study or calibrated prediction interval. Real billing history is needed before asserting model superiority or anomaly usefulness. See EVALUATION.

Candidates with failed numerical optimization are excluded and recorded. Nonfinite final predictions are rejected. Net-cost forecasts may be negative when credits dominate; predictions are not silently clipped to zero.
