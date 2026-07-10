"""
predict.py -- Daily inference for Study 1 (next-day national demand forecast).

Retrains the LightGBM baseline fresh on every run rather than loading a saved
model artifact. Training takes only a few seconds on this dataset size
(~2,700 rows), which sidesteps an open question the roadmap flagged and left
unresolved (how to version/store a trained model -- Git LFS? a GitHub release
asset? commit directly?) by not needing a stored artifact at all. A daily
retrain also means the model always reflects the latest data, with no risk of
a stale cached model silently drifting out of date.

Maintains a persistent forecast/residual log at
Dataset/predictions/study1_forecast.csv:
  - Each run appends a new forecast row for "tomorrow" (the day after the
    latest date currently in study1_daily.csv), if not already present.
  - Each run also back-fills actual_mw/residual_mw for any earlier row whose
    target_date has since arrived in study1_daily.csv. This residual signal
    (actual - predicted) is what Phase 4 is designed to consume as an
    anomaly-detection input feature.

Safe to run more than once on the same day: if a forecast for tomorrow
already exists in the log, it's left alone rather than duplicated or
overwritten (matches update_live.py's idempotency convention).

Usage:
    python ML/Study1/predict.py
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import lightgbm as lgb

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))

from features import build_feature_table, make_next_day_target, TARGET  # noqa: E402

STUDY1_CSV = REPO_ROOT / "Dataset" / "study1_daily.csv"
FORECAST_LOG = REPO_ROOT / "Dataset" / "predictions" / "study1_forecast.csv"

FORECAST_COLS = ["prediction_made_date", "target_date", "predicted_mw", "actual_mw", "residual_mw"]

FEATURE_PREFIXES = (f"{TARGET}_lag", f"{TARGET}_roll")
CALENDAR_COLS = ("dow", "month", "year", "is_weekend", "day_of_year")


def _load_log() -> pd.DataFrame:
    if FORECAST_LOG.exists():
        return pd.read_csv(FORECAST_LOG, parse_dates=["prediction_made_date", "target_date"])
    return pd.DataFrame(columns=FORECAST_COLS)


def _backfill_actuals(log: pd.DataFrame, daily: pd.DataFrame) -> pd.DataFrame:
    """Fill actual_mw/residual_mw for any past forecast whose target_date now has real data."""
    if log.empty:
        return log
    daily_lookup = daily.set_index("date")[TARGET]
    unresolved = log["actual_mw"].isna()
    for idx in log.index[unresolved]:
        tdate = log.at[idx, "target_date"]
        if tdate in daily_lookup.index:
            actual = daily_lookup.loc[tdate]
            log.at[idx, "actual_mw"] = actual
            log.at[idx, "residual_mw"] = actual - log.at[idx, "predicted_mw"]
    return log


def train_and_predict(df: pd.DataFrame):
    """Returns (forecast_mw, today_date, tomorrow_date)."""
    feat_df = build_feature_table(df)
    feat_df = make_next_day_target(feat_df)

    feature_cols = [c for c in feat_df.columns if
                     c.startswith(FEATURE_PREFIXES) or c in CALENDAR_COLS]

    trainable = feat_df.dropna(subset=[f"{TARGET}_lag365"]).reset_index(drop=True)
    train_rows = trainable[trainable[TARGET].notna()]
    predict_row = feat_df.iloc[[-1]]  # today's row: TARGET is NaN here (no "tomorrow" yet)

    if predict_row[f"{TARGET}_lag365"].isna().any():
        raise RuntimeError("Not enough history for the latest row to build lag365 -- cannot predict.")

    # Time-aware holdout for early stopping only -- last 90 days of the trainable range.
    # Not a backtest split (that's what 03_baseline.ipynb is for); this is production
    # training that uses every available day to make the single live prediction.
    cutoff = train_rows["date"].max() - pd.Timedelta(days=90)
    tr = train_rows[train_rows["date"] <= cutoff]
    val = train_rows[train_rows["date"] > cutoff]

    X_train, y_train = tr[feature_cols], tr[TARGET] - tr[f"{TARGET}_today"]
    X_val, y_val = val[feature_cols], val[TARGET] - val[f"{TARGET}_today"]

    model = lgb.LGBMRegressor(n_estimators=500, learning_rate=0.05, random_state=42, verbosity=-1)
    model.fit(
        X_train, y_train,
        eval_set=[(X_val, y_val)],
        callbacks=[lgb.early_stopping(30, verbose=False)],
    )

    pred_delta = model.predict(predict_row[feature_cols])[0]
    forecast = pred_delta + predict_row[f"{TARGET}_today"].values[0]

    today = pd.Timestamp(predict_row["date"].values[0])
    tomorrow = today + pd.Timedelta(days=1)
    return forecast, today, tomorrow


def main():
    if not STUDY1_CSV.exists():
        print(f"ERROR: {STUDY1_CSV} not found. Run the daily scrape / build_all.py first.")
        sys.exit(1)

    df = pd.read_csv(STUDY1_CSV, parse_dates=["date"])
    df = df.sort_values("date").reset_index(drop=True)

    forecast, today, tomorrow = train_and_predict(df)
    print(f"Prediction made on data through {today.date()}")
    print(f"Forecast for {tomorrow.date()}: {forecast:,.1f} MW")

    log = _load_log()
    log = _backfill_actuals(log, df)

    already_predicted = (log["target_date"] == tomorrow).any() if not log.empty else False
    if already_predicted:
        print(f"Forecast for {tomorrow.date()} already exists in the log -- not duplicating.")
    else:
        new_row = pd.DataFrame([{
            "prediction_made_date": today,
            "target_date": tomorrow,
            "predicted_mw": forecast,
            "actual_mw": np.nan,
            "residual_mw": np.nan,
        }])
        log = pd.concat([log, new_row], ignore_index=True)

    log = log.sort_values("target_date").reset_index(drop=True)
    FORECAST_LOG.parent.mkdir(parents=True, exist_ok=True)
    log.to_csv(FORECAST_LOG, index=False)

    n_backfilled = log["actual_mw"].notna().sum()
    print(f"Wrote {len(log)} row(s) -> {FORECAST_LOG} ({n_backfilled} with a known actual/residual)")


if __name__ == "__main__":
    main()
