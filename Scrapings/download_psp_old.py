import sys
import time
import requests
from datetime import date, timedelta
from pathlib import Path


BASE_URL = "https://report.grid-india.in/index.php"
HEADERS = {"User-Agent": "Mozilla/5.0 (research data collection)"}


def fy_folder(d: date) -> str:
    # Indian financial year: April - March
    if d.month >= 4:
        return f"{d.year}-{d.year + 1}"
    return f"{d.year - 1}-{d.year}"


def month_folder(d: date) -> str:
    return d.strftime("%B %Y")  # e.g. "May 2025"


def filename(d: date) -> str:
    return d.strftime("%d.%m.%y") + "_NLDC_PSP.xls"


def build_url(d: date) -> str:
    p_param = f"Daily Report/PSP Report/{fy_folder(d)}/{month_folder(d)}"
    return f"{BASE_URL}?p={requests.utils.quote(p_param)}&dl={filename(d)}"


def download_range(start: date, end: date, out_dir: Path, delay=1.0):
    out_dir.mkdir(parents=True, exist_ok=True)
    d = start
    ok, failed = 0, []

    while d <= end:
        url = build_url(d)
        out_path = out_dir / filename(d)

        if out_path.exists():
            d += timedelta(days=1)
            continue

        try:
            resp = requests.get(url, headers=HEADERS, timeout=30)
            if resp.status_code == 200 and len(resp.content) > 1000:
                out_path.write_bytes(resp.content)
                ok += 1
                print(f"OK   {d.isoformat()}  ({len(resp.content)} bytes)")
            else:
                failed.append(d.isoformat())
                print(f"FAIL {d.isoformat()}  status={resp.status_code} len={len(resp.content)}")
        except requests.RequestException as e:
            failed.append(d.isoformat())
            print(f"ERR  {d.isoformat()}  {e}")

        time.sleep(delay)
        d += timedelta(days=1)

    print(f"\nDone. {ok} downloaded, {len(failed)} failed.")
    if failed:
        print("Failed dates:", failed[:20], "..." if len(failed) > 20 else "")
        (out_dir / "failed_dates.txt").write_text("\n".join(failed))


if __name__ == "__main__":
    if len(sys.argv) != 4:
        print("Usage: python download_psp.py START_DATE END_DATE OUT_DIR")
        print("Example: python download_psp.py 2024-11-04 2026-06-13 ./psp_raw")
        sys.exit(1)

    start = date.fromisoformat(sys.argv[1])
    end = date.fromisoformat(sys.argv[2])
    out_dir = Path(sys.argv[3])

    download_range(start, end, out_dir)