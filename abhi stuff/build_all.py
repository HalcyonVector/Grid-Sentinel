"""
build_all.py — Single-command rebuild for all Grid-Sentinel datasets.

Runs in order:
  1. File1_Raw  → f1_daily.csv          (parse_psp_pdf_xls_file1.py)
  2. File2_Raw  → Dataset/study1_daily.csv (parse_psp_pdf_xls_file2.py)
  3. File3_Raw  → Dataset/study2_scada.csv (parse_psp_xls_pdf_file3.py)
  4. f1_daily + hourlyLoadDataIndia.xlsx → Dataset/study1_hourly.csv (in-process join)

Usage:
  python build_all.py                    # full rebuild
  python build_all.py --skip-file1       # skip File1 parse (f1_daily.csv already exists)
  python build_all.py --skip-file2       # skip File2 parse
  python build_all.py --skip-file3       # skip File3 parse
  python build_all.py --skip-hourly      # skip hourly join
  python build_all.py --only-hourly      # only redo the hourly join
"""

import argparse
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd

# ── Paths ─────────────────────────────────────────────────────────────────────
REPO_ROOT    = Path(__file__).resolve().parent
SCRAPERS_DIR = REPO_ROOT / "Scrapings"
DATASET_DIR  = REPO_ROOT / "Dataset"

FILE1_RAW    = REPO_ROOT / "File1_Raw"
FILE2_RAW    = REPO_ROOT / "File2_Raw"
FILE3_RAW    = REPO_ROOT / "File3_Raw"

F1_DAILY     = REPO_ROOT / "f1_daily.csv"
HOURLY_SRC   = REPO_ROOT / "hourlyLoadDataIndia.xlsx"

OUT_STUDY1_D = DATASET_DIR / "study1_daily.csv"
OUT_STUDY1_H = DATASET_DIR / "study1_hourly.csv"
OUT_STUDY2   = DATASET_DIR / "study2_scada.csv"

# ── Expected baseline row counts (from roadmap) ───────────────────────────────
# Allowed to grow (new daily data added), but never shrink below these.
BASELINES = {
    "study1_daily":  2660,
    "study1_hourly": 46728,
    "study2_scada":  55068,
}

# ── Helpers ───────────────────────────────────────────────────────────────────

def _run(cmd: list[str], label: str) -> bool:
    """Run a subprocess; return True on success."""
    print(f"\n{'─'*60}")
    print(f"  [{label}] Running: {' '.join(str(c) for c in cmd)}")
    print(f"{'─'*60}")
    result = subprocess.run(cmd, check=False)
    if result.returncode != 0:
        print(f"\n  ✗  [{label}] exited with code {result.returncode}")
        return False
    print(f"\n  ✓  [{label}] done")
    return True


def _null_summary(df: pd.DataFrame, top_n: int = 8) -> str:
    """Return a compact null-% string for the worst columns."""
    null_pct = df.isnull().mean().sort_values(ascending=False)
    worst = null_pct[null_pct > 0].head(top_n)
    if worst.empty:
        return "    no nulls"
    lines = [f"    {col}: {pct:.1%}" for col, pct in worst.items()]
    return "\n".join(lines)


def _print_summary(label: str, path: Path):
    """Print row count and null summary for a CSV."""
    if not path.exists():
        print(f"  ⚠  {label}: file not found at {path}")
        return
    df = pd.read_csv(path, low_memory=False)
    print(f"\n  {label}")
    print(f"    rows × cols : {len(df):,} × {len(df.columns)}")
    print(f"    date range  : {df['date'].min()} → {df['date'].max()}" if "date" in df.columns else "")
    print(f"    overall null: {df.isnull().mean().mean():.1%}")
    print(f"    worst cols  :")
    print(_null_summary(df))

    # Baseline check
    key = path.stem  # e.g. "study1_daily"
    if key in BASELINES and len(df) < BASELINES[key]:
        print(f"\n  ⚠  WARNING: {key} has {len(df):,} rows — below baseline {BASELINES[key]:,}!")


# ── Step 4: hourly join ───────────────────────────────────────────────────────

def build_study1_hourly():
    """
    Left-join f1_daily (PSP features, daily) onto hourlyLoadDataIndia (hourly load).
    Each daily PSP row broadcasts onto all 24 hourly rows for that date.
    Output: Dataset/study1_hourly.csv
    """
    print(f"\n{'─'*60}")
    print("  [hourly-join] Building study1_hourly.csv")
    print(f"{'─'*60}")

    if not F1_DAILY.exists():
        print(f"  ✗  f1_daily.csv not found at {F1_DAILY} — run File1 parse first.")
        return False
    if not HOURLY_SRC.exists():
        print(f"  ✗  hourlyLoadDataIndia.xlsx not found at {HOURLY_SRC}")
        return False

    print("    Reading f1_daily.csv...")
    f1 = pd.read_csv(F1_DAILY, low_memory=False)
    f1["date"] = pd.to_datetime(f1["date"], format="mixed", dayfirst=True).dt.strftime("%Y-%m-%d")

    print("    Reading hourlyLoadDataIndia.xlsx...")
    hourly = pd.read_excel(HOURLY_SRC)

    # The hourly file uses "datetime" (with time component); extract date only.
    if "datetime" not in hourly.columns:
        date_cols = [c for c in hourly.columns if "date" in c.lower()]
        if not date_cols:
            print("  ✗  hourlyLoadDataIndia.xlsx has no recognisable date column.")
            print(f"     Columns found: {list(hourly.columns)}")
            return False
        hourly.rename(columns={date_cols[0]: "datetime"}, inplace=True)
    hourly["date"] = pd.to_datetime(hourly["datetime"], format="mixed", dayfirst=True).dt.strftime("%Y-%m-%d")

    print(f"    Merging: {len(hourly):,} hourly rows × {len(f1):,} daily PSP rows...")
    merged = hourly.merge(f1, on="date", how="left", suffixes=("", "_psp"))
    dup_cols = [c for c in merged.columns if c.endswith("_psp")]
    if dup_cols:
        print(f"    Dropping {len(dup_cols)} duplicate suffix columns.")
        merged.drop(columns=dup_cols, inplace=True)
    # Put date + datetime first
    front = [c for c in ("date", "datetime") if c in merged.columns]
    merged = merged[front + [c for c in merged.columns if c not in front]]

    DATASET_DIR.mkdir(exist_ok=True)
    merged.to_csv(OUT_STUDY1_H, index=False)
    print(f"    ✓  Wrote {len(merged):,} rows → {OUT_STUDY1_H}")
    return True


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--skip-file1",  action="store_true", help="Skip File1 → f1_daily parse")
    parser.add_argument("--skip-file2",  action="store_true", help="Skip File2 → study1_daily parse")
    parser.add_argument("--skip-file3",  action="store_true", help="Skip File3 → study2_scada parse")
    parser.add_argument("--skip-hourly", action="store_true", help="Skip f1_daily + hourly join")
    parser.add_argument("--only-hourly", action="store_true", help="Only run the hourly join (implies --skip-file1/2/3)")
    args = parser.parse_args()

    if args.only_hourly:
        args.skip_file1 = args.skip_file2 = args.skip_file3 = True

    DATASET_DIR.mkdir(exist_ok=True)
    start = datetime.now()
    print(f"\n{'='*60}")
    print(f"  Grid-Sentinel — build_all.py — {start.strftime('%Y-%m-%d %H:%M')}")
    print(f"{'='*60}")

    errors = []

    # ── Step 1: File1 → f1_daily ──────────────────────────────────────────────
    if not args.skip_file1:
        ok = _run(
            [sys.executable, str(SCRAPERS_DIR / "parse_psp_pdf_xls_file1.py"),
             str(FILE1_RAW), str(F1_DAILY)],
            "file1→f1_daily"
        )
        if not ok:
            errors.append("file1 parse failed")

    # ── Step 2: File2 → study1_daily ─────────────────────────────────────────
    if not args.skip_file2:
        ok = _run(
            [sys.executable, str(SCRAPERS_DIR / "parse_psp_pdf_xls_file2.py"),
             str(FILE2_RAW), str(OUT_STUDY1_D)],
            "file2→study1_daily"
        )
        if not ok:
            errors.append("file2 parse failed")

    # ── Step 3: File3 → study2_scada ─────────────────────────────────────────
    if not args.skip_file3:
        ok = _run(
            [sys.executable, str(SCRAPERS_DIR / "parse_psp_xls_pdf_file3.py"),
             "long", str(FILE3_RAW), str(OUT_STUDY2)],
            "file3→study2_scada"
        )
        if not ok:
            errors.append("file3 parse failed")

    # ── Step 4: hourly join ───────────────────────────────────────────────────
    if not args.skip_hourly:
        ok = build_study1_hourly()
        if not ok:
            errors.append("hourly join failed")

    # ── Summary ───────────────────────────────────────────────────────────────
    print(f"\n{'='*60}")
    print("  OUTPUT SUMMARY")
    print(f"{'='*60}")

    for label, path in [
        ("study1_daily",  OUT_STUDY1_D),
        ("study1_hourly", OUT_STUDY1_H),
        ("study2_scada",  OUT_STUDY2),
    ]:
        _print_summary(label, path)

    elapsed = (datetime.now() - start).seconds
    print(f"\n  Elapsed: {elapsed}s")

    if errors:
        print(f"\n  ✗  Finished with {len(errors)} error(s):")
        for e in errors:
            print(f"     • {e}")
        sys.exit(2)
    else:
        print("\n  ✓  All steps completed successfully.")
        sys.exit(0)


if __name__ == "__main__":
    main()
