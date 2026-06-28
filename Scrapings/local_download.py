"""
local_download.py — Run locally (on Windows) to download today's PSP file and
push it to the repo. GitHub Actions will then parse and update the CSVs.

Usage:
    python Scrapings/local_download.py                    # today + yesterday
    python Scrapings/local_download.py --date 2026-06-19  # specific file date
"""

import argparse
import shutil
import subprocess
import sys
from datetime import date, timedelta
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))

from download_psp_new import download_range, stem, scrape_cdn_index, fetch_bytes, NEW_CDN_START

FILE2_RAW = REPO_ROOT / "File2_Raw"
FILE3_RAW = REPO_ROOT / "File3_Raw"


def git(*args):
    subprocess.run(["git", "-C", str(REPO_ROOT), *args], check=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", help="File date to download (YYYY-MM-DD). Default: today and yesterday.")
    args = parser.parse_args()

    LOOKBACK_DAYS = 5  # check up to this many days back for missed downloads

    if args.date:
        file_dates = [date.fromisoformat(args.date)]
    else:
        today = date.today()
        file_dates = [today - timedelta(i) for i in range(LOOKBACK_DAYS)]

    FILE2_RAW.mkdir(exist_ok=True)
    FILE3_RAW.mkdir(exist_ok=True)

    new_files = []

    for file_date in file_dates:
        s = stem(file_date)

        # Already downloaded — skip this day but keep checking older ones
        existing = list(FILE3_RAW.glob(f"{s}_NLDC_PSP*"))
        if existing:
            print(f"Already have {existing[0].name} — skipping.")
            continue

        # Only scrape the FY that contains this date — much faster
        year = file_date.year if file_date.month >= 4 else file_date.year - 1
        fy = f"{year}-{str(year + 1)[-2:]}"
        print(f"\nDownloading {s} (FY {fy} only)...")
        download_range(file_date, file_date, FILE3_RAW, fy_years=[fy])

        result = list(FILE3_RAW.glob(f"{s}_NLDC_PSP*"))
        if result:
            raw_file = result[0]
            dest2 = FILE2_RAW / raw_file.name
            if not dest2.exists():
                shutil.copy2(raw_file, dest2)
                print(f"Copied to File2_Raw: {raw_file.name}")
            new_files.append(raw_file.name)

    if not new_files:
        print("\nNo new files downloaded — nothing to push.")
        return

    # Commit and push so GitHub Actions picks it up for parsing
    git("add", "File2_Raw/", "File3_Raw/")
    status = subprocess.run(
        ["git", "-C", str(REPO_ROOT), "status", "--porcelain"],
        capture_output=True, text=True
    ).stdout.strip()

    if not status:
        print("Nothing new to commit.")
        return

    git("commit", "-m", f"chore: add raw PSP file(s) {', '.join(new_files)}")
    git("push")
    print("\nPushed to GitHub — Actions will parse and update CSVs shortly.")


if __name__ == "__main__":
    main()
