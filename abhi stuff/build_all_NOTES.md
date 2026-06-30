# build_all.py — what it does

## The short version

One command rebuilds all three Grid-Sentinel datasets from the raw files on disk.

```bash
python build_all.py
```

---

## What runs, in order

### Step 1 — File1_Raw → f1_daily.csv
Calls `parse_psp_pdf_xls_file1.py` as a subprocess.  
Reads the older PDFs + early XLS files in `File1_Raw/` and writes a single daily
CSV to `f1_daily.csv` in the repo root. This is an intermediate file — it feeds
the hourly join in Step 4.

### Step 2 — File2_Raw → Dataset/study1_daily.csv
Calls `parse_psp_pdf_xls_file2.py` as a subprocess.  
Reads everything in `File2_Raw/` (the full 2019-present history, PDFs and XLS)
and writes `Dataset/study1_daily.csv` (2,660+ rows × 144 cols).

### Step 3 — File3_Raw → Dataset/study2_scada.csv
Calls `parse_psp_xls_pdf_file3.py long` as a subprocess.  
Reads the newer XLS files in `File3_Raw/` (FY2025+, the ones with a `TimeSeries`
sheet) and writes `Dataset/study2_scada.csv` in long format
(55,000+ rows × 165 cols, one row per 15-minute slot).

### Step 4 — f1_daily + hourlyLoadDataIndia.xlsx → Dataset/study1_hourly.csv
Done in-process (pure pandas, no subprocess).  
Left-joins `f1_daily.csv` onto `hourlyLoadDataIndia.xlsx` on the `date` column.
Each daily PSP row broadcasts onto all 24 hourly rows for that date.
Output: `Dataset/study1_hourly.csv` (46,000+ rows × 151 cols).

---

## Why subprocess for steps 1-3?

The three parser scripts are designed as CLI tools with their own argparse.
Calling them as subprocesses means build_all.py doesn't need to import them or
know their internals — it just passes the same args you'd type at the terminal.
This also means each parser's stdout/stderr flows straight to your console.

---

## Output summary

After all steps finish, the script prints for each dataset:
- row × column count
- date range
- overall null %
- the 8 worst-null columns

If any dataset has fewer rows than the baseline (from the roadmap), you'll see a
`⚠ WARNING`. This catches accidental regressions (e.g. a parser writing fewer rows
than before).

---

## Skip flags (for partial rebuilds)

| Flag | What it skips |
|------|---------------|
| `--skip-file1` | File1 parse (use if f1_daily.csv already exists and File1_Raw didn't change) |
| `--skip-file2` | File2 parse |
| `--skip-file3` | File3 parse |
| `--skip-hourly` | The pandas join |
| `--only-hourly` | Skips all three parses, only redoes the join |

Example: you added new files to File3_Raw and just want to rebuild study2_scada
and update the hourly join:

```bash
python build_all.py --skip-file1 --skip-file2
```

---

## What it does NOT do

- It does not run the Phase 1b validation gate (`validate.py` — that's a separate
  script, see roadmap §1b).
- It does not push to Kaggle (that's in `daily_scrape.yml`, step 6).
- It does not download any raw files (use `download_psp_both.py` for that).

---

## Expected run time

Depends on raw file count. A full rebuild over the entire history (~2,660 files)
typically takes 15-45 minutes. Incremental rebuilds with `--skip-file1/2` run in
under a minute.
