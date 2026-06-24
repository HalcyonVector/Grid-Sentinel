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
    r'https://webcdn\.grid-india\.in/files/grdw/\d{4}/\d{2}/(\d{2}\.\d{2}\.\d{2})_NLDC_PSP_\d+\.(xls|pdf)'
)


# ── old CDN ───────────────────────────────────────────────────────────────────

def fy_folder(d: date) -> str:
    if d.month >= 4:
        return f"{d.year}-{d.year + 1}"
    return f"{d.year - 1}-{d.year}"

def stem(d: date) -> str:
    return d.strftime("%d.%m.%y")

def old_url(d: date, ext="xls") -> str:
    fy = quote(fy_folder(d))
    mo = quote(d.strftime("%B %Y"))
    fn = quote(f"{stem(d)}_NLDC_PSP.{ext}")
    return f"{OLD_BASE}/{fy}/{mo}/{fn}"


# ── new CDN: scrape with Playwright ──────────────────────────────────────────

def extract_links(html, index):
    """Extract all PSP webcdn URLs from rendered HTML into index dict."""
    new_this = 0
    for m in FULL_URL_RE.finditer(html):
        full_url  = m.group(0)
        file_stem = m.group(1)
        ext       = m.group(2)
        if file_stem not in index or ext == "xls":
            index[file_stem] = full_url
            new_this += 1
    return new_this


def find_url_without_browser(target_date: date) -> str | None:
    """
    Try to find the CDN URL for target_date using only requests (no browser).
    Tries S3-compatible directory listing on webcdn.grid-india.in.
    Returns the full URL or None.
    """
    import xml.etree.ElementTree as ET

    s    = stem(target_date)
    year = target_date.strftime("%Y")
    mon  = target_date.strftime("%m")
    base = "https://webcdn.grid-india.in"
    prefix = f"files/grdw/{year}/{mon}/{s}_NLDC_PSP"

    for list_url in [
        f"{base}/?list-type=2&prefix={prefix}",
        f"{base}/?prefix={prefix}",
    ]:
        try:
            r = requests.get(list_url, headers=HEADERS, timeout=15, verify=False)
            if r.status_code == 200:
                # Try XML S3 response
                try:
                    root = ET.fromstring(r.content)
                    for elem in root.iter():
                        tag = elem.tag.split("}")[-1]  # strip namespace
                        if tag == "Key" and elem.text and s in elem.text and "_NLDC_PSP" in elem.text:
                            return f"{base}/{elem.text}"
                except ET.ParseError:
                    pass
                # Fallback: regex on raw text
                m = re.search(
                    rf'(files/grdw/{year}/{mon}/{re.escape(s)}_NLDC_PSP_\d+\.(xls|pdf))',
                    r.text
                )
                if m:
                    return f"{base}/{m.group(1)}"
        except requests.RequestException:
            pass

    return None


def scrape_cdn_index(fy_years: list[str] | None = None) -> dict[str, str]:
    """
    Use Playwright to render the listing page for each financial year,
    clicking through all pages. Returns { "28.05.25" -> full_url }.

    fy_years: limit scraping to these FY labels (e.g. ["2026-27"]).
              If None, scrapes all available years (slow — for bulk downloads).
    Returns empty dict if Playwright is unavailable or the site is unreachable.
    """
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("WARNING: Playwright not installed — CDN listing scrape unavailable.")
        return {}

    index = {}

    try:
      with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--no-sandbox", "--disable-setuid-sandbox"])
        pg = browser.new_page()

        print("Loading listing page (may take 15-20 seconds)...")
        pg.goto(LISTING_URL, timeout=60000, wait_until="networkidle")
        pg.wait_for_timeout(2000)

        # Set rows per page to 100
        try:
            sel = pg.query_selector("select[aria-label='Choose a page size']")
            if sel:
                sel.select_option(value="100")
                pg.wait_for_timeout(1500)
                print("  Set page size to 100.")
        except Exception:
            pass

        # Get available FY options from the react-select dropdown
        # Open the dropdown first
        fy_options = []
        try:
            pg.click("div.period_drp_select .my-select__control")
            pg.wait_for_timeout(800)
            opts = pg.query_selector_all(".my-select__option")
            fy_options = [o.inner_text().strip() for o in opts if re.match(r'\d{4}', o.inner_text().strip())]
            # Close dropdown by pressing Escape
            pg.keyboard.press("Escape")
            pg.wait_for_timeout(500)
        except Exception as e:
            print(f"  Could not read FY options ({e}), using defaults.")

        if not fy_options:
            fy_options = ["2026-27", "2025-26", "2024-25"]

        if fy_years:
            fy_options = [fy for fy in fy_options if fy in fy_years]

        print(f"  Financial years to scrape: {fy_options}")

        for fy in fy_options:
            print(f"\n  === Financial year: {fy} ===")

            # Open FY dropdown and select the year
            try:
                pg.click("div.period_drp_select .my-select__control")
                pg.wait_for_timeout(800)
                # Find and click the matching option
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

            # Re-set rows per page to 100 after FY change
            try:
                sel = pg.query_selector("select[aria-label='Choose a page size']")
                if sel:
                    sel.select_option(value="100")
                    pg.wait_for_timeout(1500)
            except Exception:
                pass

            # Scrape all pages
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

    except Exception as e:
        print(f"WARNING: Playwright scrape failed ({type(e).__name__}: {e}) — returning empty index.")
        return {}

    print(f"\nScraped {len(index)} unique dates total.\n")
    return index


# ── fetch ─────────────────────────────────────────────────────────────────────

def fetch_bytes(url: str) -> bytes | None:
    try:
        r = requests.get(url, headers=HEADERS, timeout=30, verify=False)
        if r.status_code == 200 and len(r.content) > 2000:
            return r.content
    except requests.RequestException:
        pass
    return None


# ── main loop ─────────────────────────────────────────────────────────────────

def download_range(start: date, end: date, out_dir: Path, delay: float = 1.0, fy_years: list[str] | None = None):
    out_dir.mkdir(parents=True, exist_ok=True)

    cdn_index = {}
    if end >= NEW_CDN_START:
        cdn_index = scrape_cdn_index(fy_years=fy_years)

    d = start
    ok, failed = 0, []

    while d <= end:
        existing = list(out_dir.glob(f"{stem(d)}_NLDC_PSP*"))
        if existing:
            print(f"SKIP {d.isoformat()}  ({existing[0].name})")
            d += timedelta(days=1)
            continue

        content, ext = None, None

        if d < NEW_CDN_START:
            for e in ("xls", "pdf"):
                content = fetch_bytes(old_url(d, e))
                if content:
                    ext = e
                    break
        else:
            s = stem(d)
            if s in cdn_index:
                url = cdn_index[s]
                ext = url.rsplit(".", 1)[-1]
                content = fetch_bytes(url)
            else:
                print(f"FAIL {d.isoformat()}  — not in listing (holiday/missing)")
                failed.append(d.isoformat())
                d += timedelta(days=1)
                time.sleep(delay)
                continue

        if content:
            out_path = out_dir / f"{stem(d)}_NLDC_PSP.{ext}"
            out_path.write_bytes(content)
            ok += 1
            print(f"OK   {d.isoformat()}  [{ext}]  ({len(content):,} bytes)")
        else:
            failed.append(d.isoformat())
            print(f"FAIL {d.isoformat()}  — download failed")

        time.sleep(delay)
        d += timedelta(days=1)

    print(f"\nDone. {ok} downloaded, {len(failed)} failed.")
    if failed:
        print("Failed dates:", failed[:20], ("..." if len(failed) > 20 else ""))
        (out_dir / "failed_dates.txt").write_text("\n".join(failed))


# ── entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    if len(sys.argv) != 4:
        print("Usage: py download_psp.py START_DATE END_DATE OUT_DIR")
        print("Example: py download_psp.py 2024-11-04 2026-06-13 ./psp_raw")
        sys.exit(1)

    start   = date.fromisoformat(sys.argv[1])
    end     = date.fromisoformat(sys.argv[2])
    out_dir = Path(sys.argv[3])
    download_range(start, end, out_dir)
