"""ML/Study1/features.py — shared feature engineering, reused by notebooks + predict.py"""

import pandas as pd

TARGET = "max_demand_met_total_mw"

# Corridor/cross-border cols excluded from Phase 3 baseline (only populated from 2023+,
# out of scope for pure demand forecasting — revisit only if feature importance calls for it)
EXCLUDE_PREFIXES = ("ir_", "xb_")


def drop_out_of_scope_cols(df: pd.DataFrame) -> pd.DataFrame:
    cols = [c for c in df.columns if not c.startswith(EXCLUDE_PREFIXES)]
    return df[cols]


def add_calendar_features(df: pd.DataFrame, date_col: str = "date") -> pd.DataFrame:
    df = df.copy()
    df["dow"] = df[date_col].dt.dayofweek
    df["month"] = df[date_col].dt.month
    df["year"] = df[date_col].dt.year
    df["is_weekend"] = df["dow"].isin([5, 6]).astype(int)
    df["day_of_year"] = df[date_col].dt.dayofyear
    return df


def add_lag_features(df: pd.DataFrame, col: str = TARGET, lags=(1, 7, 365)) -> pd.DataFrame:
    df = df.copy()
    for lag in lags:
        df[f"{col}_lag{lag}"] = df[col].shift(lag)
    return df


def add_rolling_features(df: pd.DataFrame, col: str = TARGET, windows=(7, 30)) -> pd.DataFrame:
    df = df.copy()
    for w in windows:
        df[f"{col}_roll{w}_mean"] = df[col].shift(1).rolling(w).mean()
        df[f"{col}_roll{w}_std"] = df[col].shift(1).rolling(w).std()
    return df


def build_feature_table(df: pd.DataFrame) -> pd.DataFrame:
    """Full pipeline: assumes df sorted by date ascending, date column parsed as datetime."""
    df = drop_out_of_scope_cols(df)
    df = add_calendar_features(df)
    df = add_lag_features(df)
    df = add_rolling_features(df)
    return df
