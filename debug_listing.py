from playwright.sync_api import sync_playwright
import re

LISTING_URL = "https://grid-india.in/en/reports/daily-psp-report"
CDN_RE = re.compile(
    r'https://webcdn\.grid-india\.in/files/grdw/\d{4}/\d{2}/\d{2}\.\d{2}\.\d{2}_NLDC_PSP_\d+\.(xls|pdf)'
)

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page()
    print("Loading page...")
    page.goto(LISTING_URL, timeout=60000, wait_until="networkidle")
    print("Page loaded. Waiting extra 3s for JS...")
    page.wait_for_timeout(3000)

    html = page.content()
    print(f"HTML length: {len(html)} chars")

    # Check for webcdn links
    hits = CDN_RE.findall(html)
    print(f"webcdn links found: {len(hits)}")
    for h in hits[:5]:
        print(" ", h)

    # Check if key text exists
    for keyword in ["webcdn", "NLDC_PSP", "grdw", "psp_raw", "download"]:
        print(f"  '{keyword}' in HTML: {keyword.lower() in html.lower()}")

    # Save HTML for manual inspection
    with open("listing_debug.html", "w", encoding="utf-8") as f:
        f.write(html)
    print("\nFull HTML saved to listing_debug.html")

    browser.close()
