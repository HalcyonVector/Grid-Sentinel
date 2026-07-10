# Notes: update_live.py

**Script:** `Scrapings/update_live.py`
**Purpose:** Daily incremental update for the live pipeline — downloads the newest PSP report, parses it, and appends to all four datasets without a full rebuild. This is what `.github/workflows/daily_scrape.yml` actually runs every day; `Pipeline/build_all.py` is for full/partial local rebuilds, not daily automation.

---

## Why this file exists

`build_all.py` re-parses the entire raw archive (~2,700+ files, growing daily) every time — 15-45 minutes per dataset. That's fine for a local rebuild after a parser fix, but far too slow to run on every CI trigger just to add one new day's data. `update_live.py` instead downloads and parses exactly one file, appends the resulting rows to the existing CSVs, and exits — seconds, not minutes.

---

## What it does

### Two run modes

| Mode | Trigger | Behavior |
|------|---------|----------|
| Download mode (default) | `workflow_dispatch` or scheduled cron | Downloads today's (or yesterday's, or a `--date`-specified) file from NLDC, parses it, appends one day's rows to all three CSVs that have per-file appends |
| Scan mode (`--scan`) | Triggered on `push` to `Dataset/Raw/File2_Raw` or `File3_Raw` (i.e. someone manually added raw files) | Parses every raw file in `File3_Raw` dated within the last 10 days that isn't already reflected in the CSVs — catches up after a manual backfill or a missed day |

### Download fallback chain (`download_today()`)

Tries three methods in order, each covering a different NLDC CDN era:
1. **Old CDN** (`report.grid-india.in`) — plain `requests` GET, works for older dates, no browser needed. Uses `verify=False` internally since NLDC's site has a TLS cert issue.
2. **New CDN listing, browser-free** (`webcdn.grid-india.in`, dates ≥ `NEW_CDN_START` = 2025-05-28) — scrapes an S3-style file listing.
3. **Playwright fallback** — only reached if both of the above fail; works locally but may fail in CI (no browser available there by default).

### Three append functions, one per dataset

| Function | Appends to | Source parser |
|----------|-----------|---------------|
| `append_study1()` | `study1_daily.csv` (1 row) | `parse_psp_pdf_xls_file2.parse_file()` |
| `append_study2()` | `study2_scada.csv` (up to 96 rows) | `parse_psp_xls_pdf_file3.build_timeseries_long()` |
| `append_study3()` | `study3_states.csv` (~37 rows) | `parse_psp_states.parse_file()`, added 2026-07-10 |

Each is independent: a failure in one (caught and logged, not raised) doesn't block the other two in scan mode. Each checks whether that date is already present before appending — running the script twice on the same day is a safe no-op, not a duplicate.

### `append_study3()` specifically

Uses the same static `STATE_TO_REGION` map and `STATE_NAME_ALIASES` as the full-rebuild path in `parse_psp_states.py`, imported directly rather than reimplemented — this is what makes a single day's incremental append resolvable correctly without needing the whole archive present for a majority vote. See `parse_psp_states_notes.md` for why the static map is the primary resolution method, not a fallback.

### Validation after append

`validate()` runs lightweight sanity checks (duplicate dates/keys, null-rate jump for study1) on whichever datasets actually changed. This is a fast subset of `Pipeline/validate.py`'s checks, run inline so a bad append fails the CI job immediately (exit code 2) rather than silently corrupting the committed CSV.

---

## Verification (2026-07-10)

All three append functions independently tested by removing a known date from a test copy of its CSV, re-running the actual function against that copy, and diffing the result against the full-rebuild original. **All three byte-identical** — confirms the incremental path produces the same result as a from-scratch rebuild, not just "doesn't crash."

---

## Usage

```
python Scrapings/update_live.py                        # download today/yesterday, append
python Scrapings/update_live.py --date 2026-06-24       # backfill a specific date
python Scrapings/update_live.py --scan                  # catch up on manually-added raw files
```

Depends on `download_psp_new.py` (same folder) for the CDN fetch logic, and imports `parse_file`/`build_timeseries_long`/`parse_file` from the three per-dataset parsers at call time (not at module load) to avoid unnecessary import cost when only one dataset needs updating.
