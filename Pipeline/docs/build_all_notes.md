# Notes: build_all.py

**Script:** `Pipeline/build_all.py`
**Purpose:** Single-command full rebuild of all three Grid-Sentinel datasets from raw files on disk.

---

## What it does

Runs four steps in sequence. Steps 1 through 3 call the parser scripts as subprocesses so their output flows directly to the console. Step 4 runs in-process.

| Step | Input | Output | Script called |
|------|-------|--------|---------------|
| 1 | `Dataset/Raw/File1_Raw/` | `f1_daily.csv` (repo root) | `Scrapings/parse_psp_pdf_xls_file1.py` |
| 2 | `Dataset/Raw/File2_Raw/` | `Dataset/study1_daily.csv` | `Scrapings/parse_psp_pdf_xls_file2.py` |
| 3 | `Dataset/Raw/File3_Raw/` | `Dataset/study2_scada.csv` | `Scrapings/parse_psp_xls_pdf_file3.py long` |
| 4 | `f1_daily.csv` + `Reference/hourlyLoadDataIndia.xlsx` | `Dataset/study1_hourly.csv` | in-process pandas join |

Step 4 is a left join: every daily PSP row in `f1_daily.csv` broadcasts onto all 24 hourly rows for that date in the Kaggle hourly load file.

---

## Why subprocess for steps 1 to 3

The three parser scripts are standalone CLI tools with their own argument handling. Calling them as subprocesses means `build_all.py` does not import their internals and each parser's stdout and stderr reach the console without buffering. It also means partial rebuilds (via skip flags) cleanly skip only the subprocess call, not some internal function.

---

## Output summary printed on completion

After all steps, the script prints for each dataset:

- Row and column count
- Date range (earliest and latest value in the date column)
- Overall null percentage across all cells
- The 8 columns with the highest null rate

If any dataset has fewer rows than the baseline defined in `BASELINES`, a warning is printed. The baselines are the minimum expected row counts at the time the script was written and are allowed to grow as new daily data arrives but should never decrease.

---

## Skip flags

| Flag | Effect |
|------|--------|
| `--skip-file1` | Skips step 1. Use when `f1_daily.csv` already exists and `Dataset/Raw/File1_Raw/` has not changed. |
| `--skip-file2` | Skips step 2. |
| `--skip-file3` | Skips step 3. |
| `--skip-hourly` | Skips step 4. |
| `--only-hourly` | Skips steps 1, 2, and 3. Runs only the hourly join. |

Example: only `Dataset/Raw/File3_Raw/` has new files and you want to rebuild `study2_scada.csv`:

```
python Pipeline/build_all.py --skip-file1 --skip-file2
```

---

## What this script does not do

- It does not run the validation gate. Run `validate.py` separately after a rebuild.
- It does not push to Kaggle. That is handled by `daily_scrape.yml` step 6.
- It does not download raw files. Use `Scrapings/local_download.py` for that.

---

## Expected run time

A full rebuild over the entire history (approximately 2,660 raw files) takes between 15 and 45 minutes depending on hardware. Incremental rebuilds using skip flags complete in under a minute.

---

## Known issues fixed at deployment (2026-07-01)

The original draft from Abhi had `HOURLY_SRC = REPO_ROOT / "hourlyLoadDataIndia.xlsx"`. The file is at `Reference/hourlyLoadDataIndia.xlsx`, not the repo root. This was corrected on deployment. The hourly join step would have silently failed otherwise.
