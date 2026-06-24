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
import re
import sys
import tempfile
import time
from datetime import date, timedelta
from pathlib import Path

import pandas as pd
import requests
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ── Paths (relative to repo root) ────────────────────────────────────────────
REPO_ROOT    = Path(__file__).resolve().parent.parent
SCRAPERS_DIR = Path(__file__).resolve().parent
STUDY1_CSV   = REPO_ROOT / "Dataset" / "study1_daily.csv"
STUDY2_CSV   = REPO_ROOT / "Dataset" / "study2_scada.csv"
FILE2_RAW    = REPO_ROOT / "File2_Raw"
FILE3_RAW    = REPO_ROOT / "File3_Raw"

sys.path.insert(0, str(SCRAPERS_DIR))

# ── URL patterns (same logic as download_psp_both.py) ─────────────────────────
HEADERS         = {"User-Agent": "Mozilla/5.0 (research data collection)"}
NEW_CDN_START   = date(2025, 5, 28)
WEBCDN_OLD_BASE = "https://webcdn.grid-india.in/files/grdw/uploads/daily-reports/psp-reports"
OLD_BASE        = "https://report.grid-india.in/ReportData/Daily%20Report/PSP%20Report"
LISTING_URL     = "https://grid-india.in/en/reports/daily-psp-report"
FULL_URL_RE     = re.compile(
    r'(https://webcdn\.grid-india\.in/files/grdw/\d{4}/\d{2}/(\d{2}\.\d{2}\.\d{2})_NLDC_PSP_\d+\.(xls|pdf))'
)


def fy_folder(d: date) -> str:
    return f"{d.year}-{d.year+1}" if d.month >= 4 else f"{d.year-1}-{d.year}"


def stem(d: date) -> str:
    return d.strftime("%d.%m.%y")


def webcdn_old_url(d: date, ext: str) -> str:
    return f"{WEBCDN_OLD_BASE}/{fy_folder(d)}/{stem(d)}_NLDC_PSP.{ext}"


def fetch_bytes(url: str):
    try:
        r = requests.get(url, headers=HEADERS, timeout=30, verify=False)
        if r.status_code == 200 and len(r.content) > 2000:
            return r.content
    except requests.RequestException:
        pass
    return None


def find_new_cdn_url(target_stem: str) -> str | None:
    """
    Scrape the NLDC listing page with Playwright to find the CDN URL for
    target_stem (e.g. '25.06.26'). Only done for dates after NEW_CDN_START.
    """
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("ERROR: Playwright not installed. Run: pip install playwright && playwright install chromium")
        return None

    url_found = None
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        pg = browser.new_page()
        print(f"  Fetching NLDC listing page to find {target_stem}...")
        pg.goto(LISTING_URL, timeout=60000, wait_until="networkidle")
        pg.wait_for_timeout(3000)

        # Try current page first (most recent files are on page 1)
        for _ in range(3):
            html = pg.content()
            for m in FULL_URL_RE.finditer(html):
                if m.group(2) == target_stem:
                    url_found = m.group(1)
                    break
            if url_found:
                break
            # Try next page
            next_btn = pg.query_selector("button[aria-label='Next Page']:not([disabled])")
            if not next_btn:
                break
            next_btn.click()
            pg.wait_for_timeout(2000)

        browser.close()

    return url_found


def download_today(target_date: date, out_dir: Path) -> Path | None:
    """
    Download the PSP file for target_date into out_dir.
    Returns the local file path on success, None if not available yet.
    """
    s = stem(target_date)

    # ── 1. Try old CDN direct URLs (always works pre-NEW_CDN_START) ──────────
    for ext in ("xls", "pdf"):
        url = webcdn_old_url(target_date, ext)
        content = fetch_bytes(url)
        if content:
            dest = out_dir / f"{s}_NLDC_PSP.{ext}"
            dest.write_bytes(content)
            print(f"  Downloaded via old CDN: {dest.name} ({len(content):,} bytes)")
            return dest

    # ── 2. For new CDN dates, scrape the listing page ─────────────────────────
    if target_date >= NEW_CDN_START:
        url = find_new_cdn_url(s)
        if url:
            ext = url.rsplit(".", 1)[-1]
            content = fetch_bytes(url)
            if content:
                dest = out_dir / f"{s}_NLDC_PSP.{ext}"
                dest.write_bytes(content)
                print(f"  Downloaded via new CDN: {dest.name} ({len(content):,} bytes)")
                return dest
        else:
            print(f"  {s}: not found on listing page — likely not published yet.")
            return None

    print(f"  {s}: all download attempts failed.")
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
    existing["date"] = pd.to_datetime(existing["date"], dayfirst=True).dt.strftime("%Y-%m-%d")

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

    build_timeseries_long(str(raw_file), str(tmp_csv))
    new_rows = pd.read_csv(tmp_csv)
    tmp_csv.unlink(missing_ok=True)

    if new_rows.empty:
        print(f"  study2_scada: no TimeSeries sheet in {raw_file.name} — skipping.")
        return False

    # Standardise date to ISO
    new_rows["date"] = pd.to_datetime(new_rows["date"], dayfirst=True).dt.strftime("%Y-%m-%d")
    new_date = new_rows["date"].iloc[0]

    existing = pd.read_csv(STUDY2_CSV)
    existing["date"] = pd.to_datetime(existing["date"], dayfirst=True).dt.strftime("%Y-%m-%d")

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
    updated.to_csv(STUDY2_CSV, index=False)
    print(f"  study2_scada: appended {len(new_rows)} rows for {new_date}")
    return True


def validate(study1_changed: bool, study2_changed: bool):
    """Basic sanity checks on the updated CSVs."""
    errors = []

    if study1_changed:
        df1 = pd.read_csv(STUDY1_CSV)
        df1["date"] = pd.to_datetime(df1["date"], dayfirst=True)
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


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", help="Target data date (YYYY-MM-DD). Default: yesterday.")
    args = parser.parse_args()

    # NLDC files published on day N contain data for day N-1
    # So "today's file" (named today) reports yesterday's data.
    # We try: today's filename (data = yesterday) and yesterday's filename (data = day before).
    if args.date:
        target_data_date = date.fromisoformat(args.date)
        # File named (target_data_date + 1) reports target_data_date
        file_dates_to_try = [target_data_date + timedelta(1), target_data_date]
    else:
        today = date.today()
        # Normal run: try today's file (yesterday's data), and yesterday's file (day before)
        file_dates_to_try = [today, today - timedelta(1)]

    print(f"\n=== Grid-Sentinel daily update — {date.today()} ===\n")

    FILE2_RAW.mkdir(exist_ok=True)
    FILE3_RAW.mkdir(exist_ok=True)

    raw_file = None
    for file_date in file_dates_to_try:
        print(f"Trying file date: {stem(file_date)}")
        # Download into File3_Raw first
        raw_file = download_today(file_date, FILE3_RAW)
        if raw_file:
            # Copy the same file into File2_Raw
            import shutil
            file2_dest = FILE2_RAW / raw_file.name
            if not file2_dest.exists():
                shutil.copy2(raw_file, file2_dest)
                print(f"  Copied to File2_Raw: {raw_file.name}")
            break
    else:
        print("\nNo file available yet — will retry at next scheduled run.")
        sys.exit(1)

    # ── Parse and append to CSVs ─────────────────────────────────────────────
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
