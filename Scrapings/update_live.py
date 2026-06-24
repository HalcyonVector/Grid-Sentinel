"""
update_live.py — Daily incremental update for Grid-Sentinel live pipeline.

Downloads today's PSP file from NLDC, parses it, and appends new rows to:
  - Dataset/study1_daily.csv   (one daily row)
  - Dataset/study2_scada.csv   (96 fifteen-minute rows, only if TimeSeries sheet present)

Exit codes:
  0  — success, CSVs updated
  1  — file not published yet (safe to retry later)
  2  — unexpected error

Usage:
  python Scrapings/update_live.py
  python Scrapings/update_live.py --date 2026-06-24   # override date (for backfill)
"""

import argparse
import shutil
import sys
import tempfile
from datetime import date, timedelta
from pathlib import Path

import pandas as pd

# ── Paths (relative to repo root) ────────────────────────────────────────────
REPO_ROOT    = Path(__file__).resolve().parent.parent
SCRAPERS_DIR = Path(__file__).resolve().parent
STUDY1_CSV   = REPO_ROOT / "Dataset" / "study1_daily.csv"
STUDY2_CSV   = REPO_ROOT / "Dataset" / "study2_scada.csv"
FILE2_RAW    = REPO_ROOT / "File2_Raw"
FILE3_RAW    = REPO_ROOT / "File3_Raw"

sys.path.insert(0, str(SCRAPERS_DIR))


def download_today(target_date: date, out_dir: Path) -> Path | None:
    """
    Download the PSP file for target_date into out_dir.
    Tries in order:
      1. Old CDN direct URL (report.grid-india.in) — no browser needed
      2. CDN S3 listing (webcdn.grid-india.in) — no browser needed
      3. Playwright listing scrape — fallback for local runs
    Returns the local file path on success, None if not found.
    """
    from download_psp_new import (
        stem, fetch_bytes, old_url, find_url_without_browser,
        download_range, NEW_CDN_START,
    )

    s = stem(target_date)

    # Return early if already downloaded
    existing = list(out_dir.glob(f"{s}_NLDC_PSP*"))
    if existing:
        print(f"  Already present: {existing[0].name}")
        return existing[0]

    # ── 1. Old CDN (requests only, always fast) ───────────────────────────────
    for ext in ("xls", "pdf"):
        url = old_url(target_date, ext)
        content = fetch_bytes(url)
        if content:
            dest = out_dir / f"{s}_NLDC_PSP.{ext}"
            dest.write_bytes(content)
            print(f"  Downloaded via old CDN: {dest.name} ({len(content):,} bytes)")
            return dest

    # ── 2. New CDN: browser-free S3 listing ──────────────────────────────────
    if target_date >= NEW_CDN_START:
        url = find_url_without_browser(target_date)
        if url:
            ext = url.rsplit(".", 1)[-1]
            content = fetch_bytes(url)
            if content:
                dest = out_dir / f"{s}_NLDC_PSP.{ext}"
                dest.write_bytes(content)
                print(f"  Downloaded via CDN listing: {dest.name} ({len(content):,} bytes)")
                return dest

        # ── 3. Playwright fallback (works locally, may fail in CI) ────────────
        print("  Trying Playwright listing scrape (may fail in CI)...")
        download_range(target_date, target_date, out_dir, delay=0)
        result = list(out_dir.glob(f"{s}_NLDC_PSP*"))
        if result:
            return result[0]

    print(f"  {s}: not found on any CDN.")
    return None


def append_study1(raw_file: Path) -> bool:
    """Parse raw_file, append one daily row to study1_daily.csv. Returns True if new row added."""
    from parse_psp_pdf_xls_file2 import parse_file

    row = parse_file(str(raw_file))
    if not row or not row.get("date"):
        print(f"  parse_file returned empty for {raw_file.name}")
        return False

    row_date = str(row["date"])
    existing = pd.read_csv(STUDY1_CSV)
    existing["date"] = pd.to_datetime(existing["date"], format="mixed", dayfirst=True).dt.strftime("%Y-%m-%d")

    if row_date in existing["date"].values:
        print(f"  study1_daily: {row_date} already present — skipping.")
        return False

    new_row = pd.DataFrame([row])
    # Align columns — add missing cols as NaN, drop extra cols
    for col in existing.columns:
        if col not in new_row.columns:
            new_row[col] = float("nan")
    new_row = new_row[existing.columns]

    updated = pd.concat([existing, new_row], ignore_index=True)
    updated.to_csv(STUDY1_CSV, index=False)
    print(f"  study1_daily: appended {row_date} ({sum(v is not None and str(v) != 'nan' for v in row.values())} non-null fields)")
    return True


def append_study2(raw_file: Path) -> bool:
    """Parse raw_file timeseries, append 96 rows to study2_scada.csv. Returns True if rows added."""
    from parse_psp_xls_pdf_file3 import build_timeseries_long

    with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as tmp:
        tmp_csv = Path(tmp.name)

    try:
        build_timeseries_long(str(raw_file), str(tmp_csv))
    except Exception as e:
        print(f"  study2_scada: parser error for {raw_file.name} — {e}")
        tmp_csv.unlink(missing_ok=True)
        return False

    try:
        new_rows = pd.read_csv(tmp_csv)
    except (pd.errors.EmptyDataError, Exception) as e:
        print(f"  study2_scada: no TimeSeries data in {raw_file.name} — {e}")
        tmp_csv.unlink(missing_ok=True)
        return False
    finally:
        tmp_csv.unlink(missing_ok=True)

    if new_rows.empty:
        print(f"  study2_scada: no TimeSeries sheet in {raw_file.name} — skipping.")
        return False

    # Standardise date to ISO
    new_rows["date"] = pd.to_datetime(new_rows["date"], format="mixed", dayfirst=True).dt.strftime("%Y-%m-%d")
    new_date = new_rows["date"].iloc[0]

    existing = pd.read_csv(STUDY2_CSV)
    existing["date"] = pd.to_datetime(existing["date"], format="mixed", dayfirst=True).dt.strftime("%Y-%m-%d")

    if new_date in existing["date"].values:
        print(f"  study2_scada: {new_date} already present — skipping.")
        return False

    # Drop stub days (< 10 slots)
    if len(new_rows) < 10:
        print(f"  study2_scada: {new_date} has only {len(new_rows)} slots — stub, skipping.")
        return False

    # Align columns
    for col in existing.columns:
        if col not in new_rows.columns:
            new_rows[col] = float("nan")
    new_rows = new_rows[existing.columns]

    updated = pd.concat([existing, new_rows], ignore_index=True)
    before = len(updated)
    updated = updated.drop_duplicates(subset=["date", "hhmm"], keep="last")
    if len(updated) < before:
        print(f"  study2_scada: dropped {before - len(updated)} duplicate rows.")
    updated.to_csv(STUDY2_CSV, index=False)
    print(f"  study2_scada: appended {len(new_rows)} rows for {new_date}")
    return True


def validate(study1_changed: bool, study2_changed: bool):
    """Basic sanity checks on the updated CSVs."""
    errors = []

    if study1_changed:
        df1 = pd.read_csv(STUDY1_CSV)
        df1["date"] = pd.to_datetime(df1["date"], format="mixed", dayfirst=True)
        dups = df1.duplicated("date").sum()
        if dups > 0:
            errors.append(f"study1_daily: {dups} duplicate dates after append")
        null_pct = df1.isnull().mean().mean()
        if null_pct > 0.35:
            errors.append(f"study1_daily: null % jumped to {null_pct:.1%} (threshold 35%)")

    if study2_changed:
        df2 = pd.read_csv(STUDY2_CSV)
        dups = df2.duplicated(["date", "hhmm"]).sum()
        if dups > 0:
            errors.append(f"study2_scada: {dups} duplicate (date, hhmm) rows after append")

    if errors:
        for e in errors:
            print(f"  VALIDATION ERROR: {e}")
        return False

    print("  Validation passed.")
    return True


def _parse_file_date(path: Path) -> date | None:
    """Extract date from filename like 19.06.25_NLDC_PSP.xls → date(2025, 6, 19)."""
    try:
        parts = path.name.split("_")[0].split(".")
        return date(2000 + int(parts[2]), int(parts[1]), int(parts[0]))
    except Exception:
        return None


def scan_and_parse(lookback_days: int = 10) -> tuple[bool, bool]:
    """
    Parse recent raw files in FILE3_RAW not yet reflected in the CSVs.
    Only considers files dated within the last `lookback_days` days.
    Returns (study1_changed, study2_changed).
    """
    cutoff = date.today() - timedelta(days=lookback_days)
    all_files = sorted(FILE3_RAW.glob("*_NLDC_PSP*"))
    raw_files = [f for f in all_files if (d := _parse_file_date(f)) and d >= cutoff]

    if not raw_files:
        print(f"No raw files found in File3_Raw within the last {lookback_days} days.")
        return False, False

    print(f"Scanning {len(raw_files)} file(s) from {cutoff} onward (of {len(all_files)} total).")
    s1_any = False
    s2_any = False
    for raw_file in raw_files:
        print(f"\nParsing {raw_file.name}...")
        s1 = append_study1(raw_file)
        s2 = append_study2(raw_file)
        s1_any = s1_any or s1
        s2_any = s2_any or s2

    return s1_any, s2_any


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", help="Target data date (YYYY-MM-DD). Default: yesterday.")
    parser.add_argument("--scan", action="store_true",
                        help="Parse all unparsed files in File3_Raw (used for push-triggered runs).")
    args = parser.parse_args()

    from download_psp_new import stem

    print(f"\n=== Grid-Sentinel daily update — {date.today()} ===\n")

    FILE2_RAW.mkdir(exist_ok=True)
    FILE3_RAW.mkdir(exist_ok=True)

    # ── Scan mode: parse whatever is already in File3_Raw ────────────────────
    if args.scan:
        print("Scan mode: parsing all unparsed files in File3_Raw...")
        s1_changed, s2_changed = scan_and_parse()
    else:
        # ── Download mode: fetch a specific or today's file ──────────────────
        if args.date:
            target_data_date = date.fromisoformat(args.date)
            file_dates_to_try = [target_data_date + timedelta(1), target_data_date]
        else:
            today = date.today()
            file_dates_to_try = [today, today - timedelta(1)]

        raw_file = None
        for file_date in file_dates_to_try:
            print(f"Trying file date: {stem(file_date)}")
            raw_file = download_today(file_date, FILE3_RAW)
            if raw_file:
                file2_dest = FILE2_RAW / raw_file.name
                if not file2_dest.exists():
                    shutil.copy2(raw_file, file2_dest)
                    print(f"  Copied to File2_Raw: {raw_file.name}")
                break
        else:
            print("\nNo file available yet — will retry at next scheduled run.")
            sys.exit(1)

        print(f"\nParsing {raw_file.name}...")
        s1_changed = append_study1(raw_file)
        s2_changed = append_study2(raw_file)

    if not s1_changed and not s2_changed:
        print("\nNo new data added (already up to date).")
        sys.exit(0)

    print("\nRunning validation...")
    ok = validate(s1_changed, s2_changed)
    if not ok:
        sys.exit(2)

    print("\nDone. CSVs updated successfully.")
    sys.exit(0)


if __name__ == "__main__":
    main()
