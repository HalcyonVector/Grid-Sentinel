"""
validate.py -- Post-build validation gate for Grid-Sentinel datasets.

Loads the three output CSVs and runs a fixed set of integrity checks.
Prints a result line (PASS / WARN / FAIL) for each check.
Exits with code 0 if no FAILs, code 1 if any check fails.

Usage:
    python Pipeline/validate.py                  # run all checks
    python Pipeline/validate.py --only study1    # run only study1_daily checks
    python Pipeline/validate.py --only study2    # run only study2_scada checks
    python Pipeline/validate.py --only hourly    # run only study1_hourly checks
"""

import argparse
import sys
from datetime import date, timedelta
from pathlib import Path

import pandas as pd

# ── Paths ─────────────────────────────────────────────────────────────────────
REPO_ROOT   = Path(__file__).resolve().parent.parent
DATASET_DIR = REPO_ROOT / "Dataset"

STUDY1_D = DATASET_DIR / "study1_daily.csv"
STUDY1_H = DATASET_DIR / "study1_hourly.csv"
STUDY2   = DATASET_DIR / "study2_scada.csv"

# ── Baseline thresholds ───────────────────────────────────────────────────────
BASELINE_ROWS = {
    "study1_daily":  2660,
    "study1_hourly": 46728,
    "study2_scada":  55068,
}

BASELINE_COLS = {
    "study1_daily":  144,
    "study1_hourly": 151,
    "study2_scada":  164,
}

# Maximum days a dataset's latest date is allowed to lag behind today
# before a warning is raised. Accounts for weekends and the 1-day
# publication lag in NLDC reports.
MAX_LAG_DAYS = 5

# ── Inter-regional corridors checked for net = import - export ───────────────
IR_CORRIDORS = [
    "ir_er_nr",
    "ir_er_wr",
    "ir_er_sr",
    "ir_er_ner",
    "ir_ner_nr",
    "ir_wr_nr",
    "ir_wr_sr",
]

# ── Cross-border countries ────────────────────────────────────────────────────
XB_COUNTRIES = ["bhutan", "nepal", "bangladesh", "myanmar"]

# ── Result tracking ───────────────────────────────────────────────────────────
_results: list[tuple[str, str, str]] = []  # (status, dataset, message)


def _record(status: str, dataset: str, message: str) -> None:
    _results.append((status, dataset, message))
    tag = f"[{status:4s}]"
    print(f"  {tag}  {dataset}: {message}")


def ok(dataset: str, message: str)   -> None: _record("PASS", dataset, message)
def warn(dataset: str, message: str) -> None: _record("WARN", dataset, message)
def fail(dataset: str, message: str) -> None: _record("FAIL", dataset, message)


# ── Loaders ───────────────────────────────────────────────────────────────────

def _load(path: Path, label: str) -> pd.DataFrame | None:
    if not path.exists():
        fail(label, f"file not found: {path}")
        return None
    df = pd.read_csv(path, low_memory=False)
    return df


# ── study1_daily checks ───────────────────────────────────────────────────────

def check_study1_daily() -> None:
    label = "study1_daily"
    df = _load(STUDY1_D, label)
    if df is None:
        return

    # Column count
    n_cols = len(df.columns)
    expected_cols = BASELINE_COLS[label]
    if n_cols != expected_cols:
        fail(label, f"column count changed: expected {expected_cols}, got {n_cols}")
    else:
        ok(label, f"column count = {n_cols}")

    # Row count
    n_rows = len(df)
    if n_rows < BASELINE_ROWS[label]:
        fail(label, f"row count {n_rows:,} is below baseline {BASELINE_ROWS[label]:,}")
    else:
        ok(label, f"row count = {n_rows:,}")

    # Duplicate dates
    dupes = df["date"].duplicated().sum() if "date" in df.columns else 0
    if dupes:
        fail(label, f"{dupes} duplicate date(s) found")
    else:
        ok(label, "no duplicate dates")

    # Data freshness
    if "date" in df.columns:
        latest = pd.to_datetime(df["date"]).max().date()
        lag = (date.today() - latest).days
        if lag > MAX_LAG_DAYS:
            warn(label, f"latest date is {latest} ({lag} days ago)")
        else:
            ok(label, f"latest date = {latest} ({lag} day(s) lag)")

    # xb_export columns must be non-negative
    xb_export_cols = [f"xb_export_{c}_mu" for c in XB_COUNTRIES]
    existing_export = [c for c in xb_export_cols if c in df.columns]
    for col in existing_export:
        n_neg = (df[col] < 0).sum()
        if n_neg:
            warn(label, f"{col}: {n_neg} negative value(s)")
        else:
            ok(label, f"{col} >= 0")

    # xb_net = import - export
    for country in XB_COUNTRIES:
        imp_col  = f"xb_import_{country}_mu"
        exp_col  = f"xb_export_{country}_mu"
        net_col  = f"xb_net_{country}_mu"
        if not all(c in df.columns for c in [imp_col, exp_col, net_col]):
            continue
        sub = df[[imp_col, exp_col, net_col]].dropna()
        expected_net = sub[imp_col] - sub[exp_col]
        n_mismatch = (abs(sub[net_col] - expected_net) > 0.01).sum()
        if n_mismatch:
            warn(label, f"xb_net_{country}_mu: {n_mismatch} row(s) where net != import - export")
        else:
            ok(label, f"xb_net_{country}_mu identity holds")

    # ir_*_net = import - export
    for corridor in IR_CORRIDORS:
        imp_col = f"{corridor}_import_mu"
        exp_col = f"{corridor}_export_mu"
        net_col = f"{corridor}_net_mu"
        if not all(c in df.columns for c in [imp_col, exp_col, net_col]):
            continue
        sub = df[[imp_col, exp_col, net_col]].dropna()
        expected_net = sub[imp_col] - sub[exp_col]
        n_mismatch = (abs(sub[net_col] - expected_net) > 0.01).sum()
        if n_mismatch:
            warn(label, f"{net_col}: {n_mismatch} row(s) where net != import - export")
        else:
            ok(label, f"{net_col} identity holds")


# ── study2_scada checks ───────────────────────────────────────────────────────

def check_study2_scada() -> None:
    label = "study2_scada"
    df = _load(STUDY2, label)
    if df is None:
        return

    # Column count
    n_cols = len(df.columns)
    expected_cols = BASELINE_COLS[label]
    if n_cols != expected_cols:
        fail(label, f"column count changed: expected {expected_cols}, got {n_cols}")
    else:
        ok(label, f"column count = {n_cols}")

    # Row count
    n_rows = len(df)
    if n_rows < BASELINE_ROWS[label]:
        fail(label, f"row count {n_rows:,} is below baseline {BASELINE_ROWS[label]:,}")
    else:
        ok(label, f"row count = {n_rows:,}")

    # Duplicate (date, hhmm) pairs
    if "date" in df.columns and "hhmm" in df.columns:
        dupes = df.duplicated(subset=["date", "hhmm"]).sum()
        if dupes:
            fail(label, f"{dupes} duplicate (date, hhmm) pair(s)")
        else:
            ok(label, "no duplicate (date, hhmm) pairs")

    # Data freshness
    if "date" in df.columns:
        latest = pd.to_datetime(df["date"]).max().date()
        lag = (date.today() - latest).days
        if lag > MAX_LAG_DAYS:
            warn(label, f"latest date is {latest} ({lag} days ago)")
        else:
            ok(label, f"latest date = {latest} ({lag} day(s) lag)")

    # Slots per day
    if "date" in df.columns:
        slots_per_day = df.groupby("date").size()

        # Legacy 63-slot days are a known parser bug -- must be zero
        n_63 = (slots_per_day == 63).sum()
        if n_63:
            fail(label, f"{n_63} day(s) with 63 slots (legacy parse error)")
        else:
            ok(label, "no 63-slot days")

        # Expected: 96 slots. Allow 95/97/98 (clock-change or partial day) as warnings.
        allowed = {95, 96, 97, 98}
        bad_days = slots_per_day[~slots_per_day.isin(allowed)]
        if len(bad_days) > 10:
            fail(label, f"{len(bad_days)} day(s) with unexpected slot count (allowed: {sorted(allowed)})")
        elif len(bad_days):
            warn(label, f"{len(bad_days)} day(s) with slot count outside 96 (allowed: {sorted(allowed)})")
        else:
            ok(label, "all days have 95-98 slots")

        n_not_96 = (slots_per_day != 96).sum()
        if n_not_96:
            warn(label, f"{n_not_96} day(s) do not have exactly 96 slots")
        else:
            ok(label, "all days have exactly 96 slots")

    # Frequency range sanity check
    if "freq_hz" in df.columns:
        freq = df["freq_hz"].dropna()
        n_out = ((freq < 47) | (freq > 52)).sum()
        if n_out:
            warn(label, f"freq_hz: {n_out} value(s) outside plausible range [47, 52] Hz")
        else:
            ok(label, "freq_hz values within [47, 52] Hz")


# ── study1_hourly checks ──────────────────────────────────────────────────────

def check_study1_hourly() -> None:
    label = "study1_hourly"
    df = _load(STUDY1_H, label)
    if df is None:
        return

    # Column count
    n_cols = len(df.columns)
    expected_cols = BASELINE_COLS[label]
    if n_cols != expected_cols:
        fail(label, f"column count changed: expected {expected_cols}, got {n_cols}")
    else:
        ok(label, f"column count = {n_cols}")

    # Row count
    n_rows = len(df)
    if n_rows < BASELINE_ROWS[label]:
        fail(label, f"row count {n_rows:,} is below baseline {BASELINE_ROWS[label]:,}")
    else:
        ok(label, f"row count = {n_rows:,}")

    # Datetime column
    date_col = "datetime" if "datetime" in df.columns else ("date" if "date" in df.columns else None)
    if date_col:
        latest = pd.to_datetime(df[date_col]).max()
        ok(label, f"latest {date_col} = {latest.date()}")
    else:
        warn(label, "no date or datetime column found")


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Validate Grid-Sentinel output datasets."
    )
    parser.add_argument(
        "--only",
        choices=["study1", "study2", "hourly"],
        help="Run checks for one dataset only.",
    )
    args = parser.parse_args()

    print(f"\n{'='*60}")
    print("  Grid-Sentinel -- validate.py")
    print(f"{'='*60}\n")

    if args.only == "study1":
        check_study1_daily()
    elif args.only == "study2":
        check_study2_scada()
    elif args.only == "hourly":
        check_study1_hourly()
    else:
        check_study1_daily()
        print()
        check_study2_scada()
        print()
        check_study1_hourly()

    # Summary
    n_pass = sum(1 for r in _results if r[0] == "PASS")
    n_warn = sum(1 for r in _results if r[0] == "WARN")
    n_fail = sum(1 for r in _results if r[0] == "FAIL")

    print(f"\n{'='*60}")
    print(f"  PASS: {n_pass}   WARN: {n_warn}   FAIL: {n_fail}")
    print(f"{'='*60}\n")

    if n_fail:
        print(f"  {n_fail} check(s) failed. Investigate before using the datasets.\n")
        sys.exit(1)
    elif n_warn:
        print(f"  All checks passed with {n_warn} warning(s).\n")
    else:
        print("  All checks passed.\n")


if __name__ == "__main__":
    main()
