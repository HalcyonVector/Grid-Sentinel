# Notes: parse_psp_pdf_xls_file1.py / parse_psp_pdf_xls_file2.py

**Scripts:** `Scrapings/parse_psp_pdf_xls_file1.py`, `Scrapings/parse_psp_pdf_xls_file2.py`
**Purpose:** Core parser for NLDC daily PSP reports — Sections A, B, D-H (demand, generation, outages, frequency, inter-regional/cross-border exchange, diversity). Feeds `tmp/f1_daily.csv` (file1, → `study1_hourly.csv`) and `Dataset/study1_daily.csv` (file2) respectively.

---

## Why two files that are byte-identical

**These two files are byte-for-byte identical.** Confirmed with `diff Scrapings/parse_psp_pdf_xls_file1.py Scrapings/parse_psp_pdf_xls_file2.py` — zero output. They exist as two copies because they run against two different raw folders with different date coverage (`File1_Raw` = historical PDFs + early XLS, pre-2023; `File2_Raw` = full 2019-present history), producing two different outputs (`tmp/f1_daily.csv` feeds the hourly join; `Dataset/study1_daily.csv` is a published dataset). Since the codebase already had this duplication before this session, the working convention (not a hard rule enforced by tooling) is: **any fix to one must be applied identically to the other, and re-verified with `diff` afterward.** This was done twice in Phase 2 (2026-07-10) — see below.

---

## What it does

Dispatches by file extension: `.pdf` → `parse_pdf()` (pdfplumber, table + text extraction), `.xls`/`.xlsx` → `parse_xls()` (pandas/xlrd, reads the `MOP_E`/`IR-Line`/`CrossBorder` sheets). Both produce one dict per file (one row per day) with the same ~144-column schema, later assembled by `build_dataset()` into the final CSV with dedup and a date-sanity guard.

---

## Two real bugs found and fixed, 2026-07-10 (Phase 2)

The dataset's "residual parser gap" was originally attributed to PDF sections rendering as unstructured text blobs. Wrong — found by actually opening the raw PDFs, not by trusting that theory:

1. **Some 2019 PDFs have a well-structured Section G table** (`pdfplumber.extract_tables()` detects it fine) but the "All India" header cell renders as a stray `'0'` character. `_pdf_generation()` only matched by searching header text for "all india", so it silently skipped an otherwise-good table.
2. **Some 2021 PDFs never produce a detected table for Section F/G at all** (no visible gridlines in that part of the page), even though `extract_text()` returns the section as normal, whitespace-delimited text.

**Fix:** `_pdf_gen_outage_text_fallback()`, added to both files identically. Works directly on `extract_text()` output, bypassing `extract_tables()`'s column-header matching entirely. Matches row labels by stripping everything but letters (handles labels that gain/lose internal spaces across report eras, e.g. `"Gas, Naptha & Diesel"` vs `"Gas,Naptha&Diesel"`), then pulls data columns *positionally* from the numbers found on each line — a trailing %Share column exists in some report eras and not others, so position from the end/start is more robust than a fixed column index. Wired into `parse_pdf()` as a last resort: only fills keys still missing after the existing table-based passes, never overwrites a correctly-parsed value.

**Second, unrelated fix found while verifying the first:** two all-null rows dated 2014-08-14/17 appeared in a fresh rebuild that hadn't existed in the previously-committed dataset. Root cause: `15.08.20_NLDC_PSP.pdf` and `18.08.20_NLDC_PSP.pdf` are old enough to lack a subject line, so the parser falls back to the PDF's own "Date of Reporting" field — which itself has a genuine NLDC-side typo, printing `"15-Aug-14"` instead of `"15-Aug-20"`. **Fix:** `MIN_VALID_DATE` (2018-12-01) guard in `build_dataset()`, drops any parsed row dated earlier and logs what it dropped, since such a date can only be a source/parse artifact, never real data.

Verification: all 12 originally-affected rows confirmed populated after the fix, cross-checked by hand against raw PDF text for 3 dates; the 2 bogus 2014 rows confirmed dropped. See `ROADMAP.md`'s Phase 2 section for the full account, plus a further 74 fresh field-by-field spot-checks (0 mismatches) done in the subsequent Phase 0-1 audit.

---

## Usage

```
python Scrapings/parse_psp_pdf_xls_file2.py Dataset/Raw/File2_Raw/ Dataset/study1_daily.csv
python Scrapings/parse_psp_pdf_xls_file2.py single_file.pdf   # prints parsed dict, no CSV
```

Called as steps 1 and 2 of `Pipeline/build_all.py` (subprocess), and incrementally by `append_study1()` in `Scrapings/update_live.py`. Depends on `pdfplumber` (PDF era) and `pandas` + `xlrd` (XLS era).
