import re
import sys
import time
import requests
import urllib3
from datetime import date, timedelta
from pathlib import Path
from urllib.parse import quote

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

OLD_BASE      = "https://report.grid-india.in/ReportData/Daily%20Report/PSP%20Report"
LISTING_URL   = "https://grid-india.in/en/reports/daily-psp-report"
HEADERS       = {"User-Agent": "Mozilla/5.0 (research data collection)"}
NEW_CDN_START = date(2025, 5, 28)

FULL_URL_RE = re.compile(
    r'(https://webcdn\.grid-india\.in/files/grdw/\d{4}/\d{2}/(\d{2}\.\d{2}\.\d{2})_NLDC_PSP_\d+\.(xls|pdf))'
)
OLD_CDN_URL_RE = re.compile(
    r'(https://webcdn\.grid-india\.in/files/grdw/uploads/daily-reports/psp-reports/\d{4}-\d{4}/(\d{2}\.\d{2}\.\d{2})(?:_\d+)?_NLDC_PSP(?:_\d+)?\.(xls|pdf))'
)


def fy_folder(d: date) -> str:
    if d.month >= 4:
        return f"{d.year}-{d.year + 1}"
    return f"{d.year - 1}-{d.year}"

def stem(d: date) -> str:
    return d.strftime("%d.%m.%y")

WEBCDN_OLD_BASE = "https://webcdn.grid-india.in/files/grdw/uploads/daily-reports/psp-reports"

def webcdn_old_url(d: date, ext="xls") -> str:
    return f"{WEBCDN_OLD_BASE}/{fy_folder(d)}/{stem(d)}_NLDC_PSP.{ext}"

def old_url(d: date, ext="xls") -> str:
    fy = quote(fy_folder(d))
    mo = quote(d.strftime("%B %Y"))
    fn = quote(f"{stem(d)}_NLDC_PSP.{ext}")
    return f"{OLD_BASE}/{fy}/{mo}/{fn}"


def extract_links(html, index):
    new_this = 0
    for m in FULL_URL_RE.finditer(html):
        full_url, file_stem, ext = m.group(1), m.group(2), m.group(3)
        if file_stem not in index or ext == "xls":
            index[file_stem] = full_url
            new_this += 1
    for m in OLD_CDN_URL_RE.finditer(html):
        full_url, file_stem, ext = m.group(1), m.group(2), m.group(3)
        if file_stem not in index or ext == "xls":
            index[file_stem] = full_url
            new_this += 1
    return new_this


def scrape_cdn_index() -> dict:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("ERROR: Playwright not installed.")
        print("Run:  pip install playwright && py -m playwright install chromium")
        sys.exit(1)

    index = {}

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        pg = browser.new_page()

        print("Loading listing page (may take 15-20 seconds)...")
        pg.goto(LISTING_URL, timeout=60000, wait_until="networkidle")
        pg.wait_for_timeout(2000)

        try:
            sel = pg.query_selector("select[aria-label='Choose a page size']")
            if sel:
                sel.select_option(value="100")
                pg.wait_for_timeout(1500)
                print("  Set page size to 100.")
        except Exception:
            pass

        fy_options = []
        try:
            pg.click("div.period_drp_select .my-select__control")
            pg.wait_for_timeout(800)
            opts = pg.query_selector_all(".my-select__option")
            fy_options = [o.inner_text().strip() for o in opts if re.match(r'\d{4}', o.inner_text().strip())]
            pg.keyboard.press("Escape")
            pg.wait_for_timeout(500)
        except Exception as e:
            print(f"  Could not read FY options ({e}), using defaults.")

        if not fy_options:
            fy_options = ["2026-27", "2025-26", "2024-25", "2023-24", "2022-23",
                          "2021-22", "2020-21", "2019-20", "2018-19"]

        print(f"  Financial years to scrape: {fy_options}")

        for fy in fy_options:
            print(f"\n  === Financial year: {fy} ===")

            try:
                pg.click("div.period_drp_select .my-select__control")
                pg.wait_for_timeout(800)
                matched = False
                for opt in pg.query_selector_all(".my-select__option"):
                    if opt.inner_text().strip() == fy:
                        opt.click()
                        matched = True
                        break
                if not matched:
                    pg.keyboard.press("Escape")
                    print(f"  Option '{fy}' not found, skipping.")
                    continue
                pg.wait_for_timeout(2000)
            except Exception as e:
                print(f"  Error selecting {fy}: {e}")
                continue

            try:
                sel = pg.query_selector("select[aria-label='Choose a page size']")
                if sel:
                    sel.select_option(value="100")
                    pg.wait_for_timeout(1500)
            except Exception:
                pass

            page_num = 1
            while True:
                html = pg.content()
                new_this = extract_links(html, index)
                print(f"    page {page_num}: {new_this} new links (total {len(index)})")

                next_btn = pg.query_selector("button[aria-label='Next Page']:not([disabled])")
                if not next_btn:
                    break

                next_btn.click()
                pg.wait_for_timeout(2000)
                page_num += 1

                if page_num > 50:
                    break

        browser.close()

    print(f"\nScraped {len(index)} unique dates total.\n")
    return index


def fetch_bytes(url: str):
    try:
        r = requests.get(url, headers=HEADERS, timeout=30, verify=False)
        if r.status_code == 200 and len(r.content) > 2000:
            return r.content
    except requests.RequestException:
        pass
    return None


def download_range(start: date, end: date, out_dir: Path, delay: float = 1.0):
    out_dir.mkdir(parents=True, exist_ok=True)

    cdn_index = scrape_cdn_index()

    d = start
    ok, failed = 0, []

    while d <= end:
        existing = list(out_dir.glob(f"{stem(d)}_NLDC_PSP*"))
        if existing:
            print(f"SKIP {d.isoformat()}  ({existing[0].name})")
            d += timedelta(days=1)
            continue

        content, ext = None, None
        s = stem(d)

        if s in cdn_index:
            url = cdn_index[s]
            ext = url.rsplit(".", 1)[-1]
            content = fetch_bytes(url)

        if not content:
            for e in ("xls", "pdf"):
                content = fetch_bytes(webcdn_old_url(d, e))
                if content:
                    ext = e
                    break

        if not content:
            for e in ("xls", "pdf"):
                content = fetch_bytes(old_url(d, e))
                if content:
                    ext = e
                    break

        if content:
            out_path = out_dir / f"{s}_NLDC_PSP.{ext}"
            out_path.write_bytes(content)
            ok += 1
            print(f"OK   {d.isoformat()}  [{ext}]  ({len(content):,} bytes)")
        else:
            failed.append(d.isoformat())
            if s in cdn_index:
                print(f"FAIL {d.isoformat()}  — download failed (URL: {cdn_index[s]})")
            else:
                print(f"FAIL {d.isoformat()}  — not in index + fallbacks failed (holiday/missing?)")

        time.sleep(delay)
        d += timedelta(days=1)

    print(f"\nDone. {ok} downloaded, {len(failed)} failed.")
    if failed:
        print("Failed dates:", failed[:20], ("..." if len(failed) > 20 else ""))
        (out_dir / "failed_dates.txt").write_text("\n".join(failed))


if __name__ == "__main__":
    if len(sys.argv) != 4:
        print("Usage: py download_psp.py START_DATE END_DATE OUT_DIR")
        print("Example: py download_psp.py 2019-04-01 2026-06-13 ./psp_raw")
        sys.exit(1)

    start   = date.fromisoformat(sys.argv[1])
    end     = date.fromisoformat(sys.argv[2])
    out_dir = Path(sys.argv[3])
    download_range(start, end, out_dir)
