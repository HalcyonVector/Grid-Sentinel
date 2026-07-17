"""Build the data file the Phase 5 dashboard (dashboard/) consumes.

The dashboard is a static React app with no backend, it fetches JSON
directly from the browser. study1_hourly.csv (36MB) and study2_scada.csv
(60MB) are far too large to fetch client-side just to show a monthly trend
or a single day's timeline, so this script precomputes the small aggregates
the frontend actually needs and writes one JSON file to
dashboard/public/data/. Re-run whenever the source datasets update (wired
into daily_scrape.yml).

Output: dashboard/public/data/dashboard.json, containing:
  dailySlim         -- study1_daily.csv trimmed to the ~15 columns the
                        Historical Explorer and Live Grid Status panels use,
                        full 2019-present date range (144 cols -> 15 shrinks
                        the payload from ~2.1MB to a few hundred KB, not the
                        36-60MB the raw hourly/SCADA files would cost).
  era1Monthly       -- same monthly ramp-magnitude/frequency vs RES-share
                        aggregation as 04_era1_ramp_characterization.ipynb.
  era2CorridorCorr  -- same per-corridor/per-country correlation-vs-stress
                        numbers as 00_era2_daily_correlation.ipynb.
  forecast          -- Dataset/predictions/study1_forecast.csv, as records.
  risk              -- Dataset/predictions/study2_risk.csv, as records.
  hourDowHeatmap    -- violation/ramp rate by hour x day-of-week, same
                        pivot as 01_eda.ipynb's appendix cell (the Sunday
                        decoupling finding).
  monthSeasonality  -- violation/ramp rate by month, same as 01_eda.ipynb.
  solarHourRates    -- violation/ramp rate, solar vs non-solar hour.
  resShareFindings  -- pooled violation-rate-by-quintile (the project's
                        central-thesis chart) and the pooled-vs-within-month
                        ramp-rate reversal (the season-confounding finding).
  featureImportance -- real, freshly retrained feature_importances_ for all
                        three models (Study 1 demand baseline, Study 2
                        violation classifier, Study 2 ramp-shock classifier),
                        same training procedure as the baseline notebooks,
                        plus each classifier's VAL-selected best-F1
                        threshold (same methodology-fix pattern as
                        03_violation_baseline.ipynb/04_ramp_shock_baseline.ipynb:
                        selected on VAL, not on the same data being judged).
  study3Latest      -- study3_states.csv's latest date, per-state demand and
                        shortage, sorted by demand descending.
"""

import importlib.util
import json
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import precision_recall_curve

REPO_ROOT = Path(__file__).resolve().parent.parent
DATASET_DIR = REPO_ROOT / "Dataset"
OUT_DIR = REPO_ROOT / "dashboard" / "public" / "data"
OUT_FILE = OUT_DIR / "dashboard.json"

STUDY1_DIR = REPO_ROOT / "ML" / "Study1"
STUDY2_DIR = REPO_ROOT / "ML" / "Study2"

STUDY1_DAILY_SLIM_COLS = [
    "date",
    "max_demand_met_total_mw",
    "energy_met_total_mu",
    "share_res_pct",
    "gen_coal_mu",
    "gen_lignite_mu",
    "gen_hydro_mu",
    "gen_nuclear_mu",
    "gen_gas_mu",
    "gen_res_mu",
    "gen_total_mu",
    "freq_fvi",
    "freq_pct_below_499",
    "freq_pct_above_5005",
]


def _load_module(name, path):
    """Both ML/Study1/features.py and ML/Study2/features.py are literally
    named features.py -- a plain sys.path import would silently return
    whichever one Python happened to import first. Load each by explicit
    file path instead, same pattern ML/Study2/features.py itself uses to
    load Study 1's module for the residual signal."""
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def clean_records(df):
    """NaN isn't valid JSON, convert to None so json.dump emits `null`."""
    return json.loads(df.to_json(orient="records", date_format="iso"))


def build_daily_slim():
    df = pd.read_csv(DATASET_DIR / "study1_daily.csv", parse_dates=["date"])
    df = df.sort_values("date")
    slim = df[STUDY1_DAILY_SLIM_COLS].copy()
    slim["date"] = slim["date"].dt.strftime("%Y-%m-%d")
    return clean_records(slim)


def build_era1_monthly():
    """Reproduces 04_era1_ramp_characterization.ipynb's monthly aggregation
    from the 36MB study1_hourly.csv, without shipping that file to the browser."""
    hourly = pd.read_csv(DATASET_DIR / "study1_hourly.csv")
    hourly["datetime"] = pd.to_datetime(hourly["datetime"], format="%Y-%m-%d %H:%M:%S")
    hourly["date"] = hourly["datetime"].dt.normalize()
    daily = pd.read_csv(DATASET_DIR / "study1_daily.csv", parse_dates=["date"])

    hourly = hourly[hourly["date"].dt.year.between(2019, 2022)].copy()
    daily_era1 = daily[daily["date"].dt.year.between(2019, 2022)][["date", "share_res_pct"]]

    DEMAND_COL = "National Hourly Demand"
    hourly = hourly.sort_values("datetime").reset_index(drop=True)
    hourly["ramp"] = hourly[DEMAND_COL].diff()

    daily_ramp = hourly.groupby(hourly["date"].dt.date)["ramp"].apply(lambda x: x.abs().max())
    daily_ramp = daily_ramp.reset_index()
    daily_ramp.columns = ["date", "ramp_magnitude"]
    daily_ramp["date"] = pd.to_datetime(daily_ramp["date"])

    threshold = hourly["ramp"].abs().quantile(0.9)
    daily_freq = hourly.groupby(hourly["date"].dt.date)["ramp"].apply(lambda x: (x.abs() > threshold).sum())
    daily_freq = daily_freq.reset_index()
    daily_freq.columns = ["date", "ramp_frequency"]
    daily_freq["date"] = pd.to_datetime(daily_freq["date"])

    merged = daily_ramp.merge(daily_freq, on="date").merge(daily_era1, on="date", how="left")
    merged["month"] = merged["date"].dt.to_period("M")
    monthly = merged.groupby("month").agg(
        ramp_magnitude=("ramp_magnitude", "mean"),
        ramp_frequency=("ramp_frequency", "mean"),
        share_res_pct=("share_res_pct", "mean"),
    ).reset_index()
    monthly["month"] = monthly["month"].dt.to_timestamp().dt.strftime("%Y-%m-%d")
    return clean_records(monthly)


def build_era2_corridor_corr():
    """Reproduces 00_era2_daily_correlation.ipynb's per-corridor/per-country
    correlation-vs-stress numbers as a small static table."""
    df = pd.read_csv(DATASET_DIR / "study1_daily.csv", parse_dates=["date"])
    df = df.sort_values("date").reset_index(drop=True)

    era2 = df[(df["date"] >= "2023-01-01") & (df["date"] <= "2024-10-31")].copy()
    IR_COLS = [c for c in df.columns if c.startswith("ir_") and c.endswith("_net_mu")]
    XB_COLS = [c for c in df.columns if c.startswith("xb_net_")]
    era2["stress_pct"] = era2["freq_pct_below_499"] + era2["freq_pct_above_5005"]

    ir_sub = era2.dropna(subset=IR_COLS + ["stress_pct"])
    ir_abs_sum = ir_sub[IR_COLS].abs().sum(axis=1)

    rows = []
    for c in IR_COLS:
        rows.append({"group": "corridor", "name": c, "corr": np.corrcoef(ir_sub[c].abs(), ir_sub["stress_pct"])[0, 1]})
    rows.append({"group": "corridor", "name": "ALL (summed |ir_net|)", "corr": np.corrcoef(ir_abs_sum, ir_sub["stress_pct"])[0, 1]})

    xb_win = era2[era2["date"] >= "2023-07-06"].copy()
    xb_sub = xb_win.dropna(subset=XB_COLS + ["stress_pct"])
    for c in XB_COLS:
        v = xb_sub[c].abs()
        corr = np.corrcoef(v, xb_sub["stress_pct"])[0, 1] if v.std() > 0 else float("nan")
        rows.append({"group": "cross_border", "name": c, "corr": corr})
    rows.append({
        "group": "cross_border", "name": "ALL (summed |xb_net|)",
        "corr": np.corrcoef(xb_sub[XB_COLS].abs().sum(axis=1), xb_sub["stress_pct"])[0, 1],
    })

    out_df = pd.DataFrame(rows).dropna(subset=["corr"])
    return clean_records(out_df)


def build_study3_latest():
    """study3_states.csv is otherwise unused anywhere in the dashboard --
    it's a full third study (state-level PSP breakdown), published on
    Kaggle and updated daily by CI, but had zero representation here.
    Ships just the latest date's per-state snapshot, not full history --
    99,489 rows of state-level history would be a needless payload for a
    single "state status" panel; a historical per-state explorer would be
    a bigger, separate feature."""
    df = pd.read_csv(DATASET_DIR / "study3_states.csv", parse_dates=["date"])
    latest_date = df["date"].max()
    latest = df[df["date"] == latest_date].copy()
    latest = latest.sort_values("max_demand_met_mw", ascending=False)

    states = clean_records(
        latest[["region", "state", "max_demand_met_mw", "shortage_max_demand_mw", "energy_shortage_mu"]]
    )
    totals = {
        "date": latest_date.strftime("%Y-%m-%d"),
        "totalDemand": float(latest["max_demand_met_mw"].sum()),
        "totalShortage": float(latest["shortage_max_demand_mw"].sum()),
        "stateCount": int(len(latest)),
        "statesWithShortage": int((latest["shortage_max_demand_mw"] > 0).sum()),
    }
    return {"date": totals["date"], "totals": totals, "states": states}


def build_predictions():
    forecast = pd.read_csv(DATASET_DIR / "predictions" / "study1_forecast.csv")
    risk = pd.read_csv(DATASET_DIR / "predictions" / "study2_risk.csv")
    return clean_records(forecast), clean_records(risk)


def _load_study2_base_df(f):
    """Common Era-3 EDA setup shared by every finding below -- same four
    calls 01_eda.ipynb opens with."""
    scada = pd.read_csv(DATASET_DIR / "study2_scada.csv", parse_dates=["date"])
    scada = scada.sort_values(["date", "time"]).reset_index(drop=True)
    df = f.drop_bad_days(scada)
    df = f.add_datetime(df)
    df = f.add_violation_label(df)
    df = f.add_ramp_label(df)
    df = f.add_time_features(df)
    return df


def build_hour_dow_heatmap(df):
    """Reproduces 01_eda.ipynb's appendix cell: violations concentrate hardest
    on Sunday, while ramp-shocks show the OPPOSITE day-of-week pattern -- the
    decoupling finding."""
    viol = df.pivot_table(index="dow", columns="hour", values="violation", aggfunc="mean")
    ramp = df.pivot_table(index="dow", columns="hour", values="ramp", aggfunc="mean")
    return {
        "hours": [int(h) for h in viol.columns],
        "violation": viol.values.tolist(),
        "ramp": ramp.values.tolist(),
    }


def build_month_seasonality(df):
    by_month = df.groupby("month")[["violation", "ramp"]].mean().reset_index()
    return clean_records(by_month)


def build_solar_hour_rates(df):
    by_solar = df.groupby("is_solar_hr")[["violation", "ramp"]].mean()
    return {
        "nonSolar": {"violation": by_solar.loc[0, "violation"], "ramp": by_solar.loc[0, "ramp"]},
        "solar": {"violation": by_solar.loc[1, "violation"], "ramp": by_solar.loc[1, "ramp"]},
    }


def build_res_share_findings(df):
    """Reproduces two 01_eda.ipynb findings: (1) violation rate rises
    monotonically with RES share, pooled -- the project's strongest single
    piece of SCADA-resolution evidence for its central thesis; (2) the pooled
    ramp-rate-vs-RES-share relationship reverses sign once season is
    controlled for (rank RES share within each month first)."""
    df = df.copy()
    df["res_bin"] = pd.qcut(df["share_res_pct"], 5, duplicates="drop")
    pooled = df.groupby("res_bin", observed=True)[["violation", "ramp"]].mean().reset_index(drop=True)
    pooled.insert(0, "quintile", ["Q1 (low)", "Q2", "Q3", "Q4", "Q5 (high)"][: len(pooled)])

    df["res_rank_in_month"] = df.groupby("month")["share_res_pct"].rank(pct=True)
    df["res_bin_within_month"] = pd.cut(df["res_rank_in_month"], 5, labels=False)
    within_month = df.groupby("res_bin_within_month", observed=True)[["violation", "ramp"]].mean().reset_index(drop=True)
    within_month.insert(0, "quintile", ["Q1 (low)", "Q2", "Q3", "Q4", "Q5 (high)"][: len(within_month)])

    return {
        "pooledViolationByResShare": clean_records(pooled[["quintile", "violation"]]),
        "rampReversal": clean_records(
            pd.DataFrame({
                "quintile": pooled["quintile"],
                "pooled": pooled["ramp"],
                "withinMonth": within_month["ramp"],
            })
        ),
    }


def build_feature_importance(study2_f):
    """Freshly retrains all three models (same procedure as the baseline
    notebooks -- time-aware split, same hyperparameters) purely to extract
    feature_importances_. Training takes seconds on this data size (same
    rationale predict.py documents for retraining fresh on every run)."""
    import lightgbm as lgb

    study1_f = _load_module("study1_features", STUDY1_DIR / "features.py")

    # --- Study 1: next-day demand forecast ---
    daily = pd.read_csv(DATASET_DIR / "study1_daily.csv", parse_dates=["date"])
    daily = daily.sort_values("date").reset_index(drop=True)
    feat_df = study1_f.build_feature_table(daily)
    feat_df = study1_f.make_next_day_target(feat_df)
    TARGET = study1_f.TARGET
    feature_cols = [
        c for c in feat_df.columns
        if c.startswith(f"{TARGET}_lag") or c.startswith(f"{TARGET}_roll")
        or c in ("dow", "month", "year", "is_weekend", "day_of_year")
    ]
    feat_df = feat_df.dropna(subset=[f"{TARGET}_lag365", TARGET]).reset_index(drop=True)
    train = feat_df[feat_df["year"] <= 2022]
    val = feat_df[feat_df["year"] == 2023]
    X_train, y_train = train[feature_cols], train[TARGET] - train[f"{TARGET}_today"]
    X_val, y_val = val[feature_cols], val[TARGET] - val[f"{TARGET}_today"]
    model1 = lgb.LGBMRegressor(n_estimators=500, learning_rate=0.05, random_state=42, verbosity=-1)
    model1.fit(X_train, y_train, eval_set=[(X_val, y_val)], callbacks=[lgb.early_stopping(30, verbose=False)])
    study1_importance = (
        pd.Series(model1.feature_importances_, index=feature_cols)
        .sort_values(ascending=False).head(10).reset_index()
    )
    study1_importance.columns = ["feature", "importance"]

    # --- Study 2: violation + ramp-shock classifiers ---
    scada = pd.read_csv(DATASET_DIR / "study2_scada.csv", parse_dates=["date"])
    scada = scada.sort_values(["date", "time"]).reset_index(drop=True)
    feat_df2 = study2_f.build_feature_table(scada)

    def train_classifier(target):
        df = feat_df2.dropna(subset=[target]).copy()
        train = df[(df["date"] >= "2024-11-04") & (df["date"] <= "2025-06-30")]
        val = df[(df["date"] >= "2025-07-01") & (df["date"] <= "2025-12-31")]
        model = lgb.LGBMClassifier(n_estimators=500, learning_rate=0.05, random_state=42, verbosity=-1)
        model.fit(
            train[study2_f.FEATURE_COLS], train[target],
            eval_set=[(val[study2_f.FEATURE_COLS], val[target])],
            eval_metric="average_precision",
            callbacks=[lgb.early_stopping(50, verbose=False)],
        )
        imp = (
            pd.Series(model.feature_importances_, index=study2_f.FEATURE_COLS)
            .sort_values(ascending=False).head(10).reset_index()
        )
        imp.columns = ["feature", "importance"]

        # Best-F1 threshold selected on VAL, not on TEST/live data -- same
        # methodology-fix pattern as 03_violation_baseline.ipynb (2026-07-14):
        # picking the threshold on the same data it's later applied to is a
        # hindsight-optimistic leak. This is genuinely out-of-sample.
        proba_val = model.predict_proba(val[study2_f.FEATURE_COLS])[:, 1]
        precision_val, recall_val, thresh_val = precision_recall_curve(val[target], proba_val)
        f1s_val = 2 * precision_val * recall_val / (precision_val + recall_val + 1e-12)
        best_idx_val = np.nanargmax(f1s_val[:-1])
        best_threshold = float(thresh_val[best_idx_val])

        return imp, best_threshold

    violation_importance, violation_threshold = train_classifier("violation_lead")
    ramp_importance, ramp_threshold = train_classifier("ramp_lead")

    return {
        "study1Demand": clean_records(study1_importance),
        "study2Violation": clean_records(violation_importance),
        "study2Ramp": clean_records(ramp_importance),
        "thresholds": {"violation": violation_threshold, "ramp": ramp_threshold},
    }


if __name__ == "__main__":
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    study2_f = _load_module("study2_features", STUDY2_DIR / "features.py")
    era3_df = _load_study2_base_df(study2_f)

    forecast, risk = build_predictions()
    payload = {
        "dailySlim": build_daily_slim(),
        "era1Monthly": build_era1_monthly(),
        "era2CorridorCorr": build_era2_corridor_corr(),
        "forecast": forecast,
        "risk": risk,
        "hourDowHeatmap": build_hour_dow_heatmap(era3_df),
        "monthSeasonality": build_month_seasonality(era3_df),
        "solarHourRates": build_solar_hour_rates(era3_df),
        "resShareFindings": build_res_share_findings(era3_df),
        "featureImportance": build_feature_importance(study2_f),
        "study3Latest": build_study3_latest(),
    }
    with open(OUT_FILE, "w", encoding="utf-8") as fh:
        json.dump(payload, fh)
    size_kb = OUT_FILE.stat().st_size / 1024
    print(f"wrote {OUT_FILE} ({size_kb:.1f} KB)")
    for key, val in payload.items():
        n = len(val) if isinstance(val, list) else "object"
        print(f"  {key}: {n}")
