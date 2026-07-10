# Grid-Sentinel — Roadmap

_Last updated: 2026-07-10 (Phase 2 merged-blob fix implemented and verified; 2014 bogus-date bug found and fixed; Phase 3 naive-persistence anchor bug found, fixed, and re-verified)_

---

## What this project is

Grid-Sentinel is a machine learning project for **predicting and detecting stress on the Indian power grid**, built entirely on NLDC (National Load Despatch Centre) daily Power System Performance (PSP) reports scraped from the NLDC/Grid-India CDN.

### End goals

1. **GitHub dashboard** (public, live) — a real-time web dashboard hosted on GitHub Pages that shows both live NLDC data as it comes in and model predictions overlaid. Also includes an interactive explorer of the full historical dataset (2019–present). Intended as a portfolio/résumé artefact.
2. **Research paper** (conditional) — if model results are strong enough, publish to an IEEE Power & Energy conference or a journal like *Electric Power Systems Research*. Decision deferred until Phase 3/4 outputs are in hand.
3. **Kaggle dataset** (ongoing) — three cleaned CSVs published and auto-updated daily, serving as a public resource for the broader community.

### Two studies

| Study | Dataset | Target | Rows | Date range |
|-------|---------|--------|------|------------|
| **Study 1 — Daily load forecasting** | `study1_daily.csv` | Next-day peak demand (MW) / energy met (MU) | 2,660 × 144 | 2018-12-31 → present |
| **Study 2 — 15-min frequency-violation classifier** | `study2_scada.csv` | Binary: frequency violation in a 15-min slot? | 55,000+ × 164 | 2024-11-04 → present |

Study 1 also has an hourly variant (`study1_hourly.csv`, 46,728 rows × 151 cols, 2019-01-01 → 2024-04-30) joining PSP daily features with the Kaggle India hourly load data.

---

## Repository structure

```
Grid-Sentinel/
├── Dataset/            Output CSVs + Kaggle metadata (auto-updated daily by CI)
│   └── Raw/
│       ├── File1_Raw/  Historical PSP PDFs + early XLS (pre-2023)
│       ├── File2_Raw/  Full-history PSP files (2019-present), used for study1_daily
│       └── File3_Raw/  FY2025+ XLS files with TimeSeries sheet, used for study2_scada
├── Pipeline/           Build, validate, and data-dictionary scripts
│   ├── build_all.py        Full rebuild of all three datasets
│   ├── validate.py         Post-build integrity checks
│   ├── build_data_dict.py  Generates Dataset/data_dictionary.xlsx
│   └── docs/               Notes for each Pipeline script
├── Reference/          External source data (hourlyLoadDataIndia.xlsx from Kaggle)
├── Scrapings/          Parsers and download scripts
│   ├── local_download.py   Run locally (scheduled via run_download.bat)
│   ├── update_live.py      Incremental append — called by GitHub Actions daily
│   ├── parse_psp_pdf_xls_file1.py
│   ├── parse_psp_pdf_xls_file2.py
│   └── parse_psp_xls_pdf_file3.py
├── logs/               local_download.py run logs (gitignored)
├── .github/workflows/  daily_scrape.yml — CI pipeline
├── ROADMAP.md
└── run_download.bat    Windows Task Scheduler entry (runs at 12pm and 8pm)
```

---

## Dataset inventory

| File | Rows | Cols | Date range | Source |
|------|------|------|------------|--------|
| `Dataset/study1_daily.csv` | 2,660 | 144 | 2018-12-31 → 2026-06-18 | `Dataset/Raw/File2_Raw/` |
| `Dataset/study1_hourly.csv` | 46,728 | 151 | 2019-01-01 → 2024-04-30 | `Dataset/Raw/File1_Raw/` + `hourlyLoadDataIndia.xlsx` |
| `Dataset/study2_scada.csv` | 55,068 | 164 | 2024-11-04 → 2026-06-18 | `Dataset/Raw/File3_Raw/` |

### Build commands

```bash
# Full rebuild (all three datasets)
python Pipeline/build_all.py

# Partial rebuild — only File3_Raw changed
python Pipeline/build_all.py --skip-file1 --skip-file2

# Validate after any rebuild
python Pipeline/validate.py

# Regenerate data dictionary
python Pipeline/build_data_dict.py

# Re-download missing raw files
python Scrapings/local_download.py
```

---

## Phase 0 — Correct datasets ✅ COMPLETE (2026-06-24)

Everything here is done and verified. Datasets are as clean as the source data allows.

| Task | Status |
|------|--------|
| Parser fixes: diversity cols, max_demand_met, xb_export/import, concatenated-text PDFs, all-pages fallback | ✅ |
| IR-Line backport to file1/file2 — 21 `ir_*` corridor cols now emitted for every XLS with an IR-Line sheet | ✅ |
| Dedup by date (keep richest row) | ✅ |
| Date handling: PDF → subject-line date; XLS → "Date of Reporting" − 1 day | ✅ |
| Regenerate all three datasets | ✅ |
| Re-run downloader over full range — 70 gaps confirmed irreducible (source-level, not parser failures) | ✅ |
| Spot-check 8 dates × 44 fields (2019–2025) — 0 mismatches | ✅ |
| study1_hourly IR cols: 0 → 21 | ✅ |
| study2_scada: 2 stub rows dropped, dates normalised to ISO | ✅ |
| Live pipeline: `update_live.py` + GitHub Actions auto-push daily | ✅ |
| `run_download.bat` scheduled locally (12pm + 8pm) to catch up if GitHub Actions misses a day | ✅ |
| **Fallback extended to 5 days** — `local_download.py` now checks today through today−4 so missed days are caught even after the laptop is off for a weekend | ✅ |

### Known irreducible gaps in study1_daily (70 total)

| Category | Count |
|----------|-------|
| Duplicate subject-line dates (NLDC publishing irregularities, mostly 2020 COVID era) | 57 |
| Confirmed unavailable from NLDC server (public holidays) | 20 |
| Edge cases (2018-12-31, 2025-05-22/23) | 3 |
| **Total** | **70** |

Treat with forward-fill or time-series-aware imputation at model time.

### Residual parser gap ✅ CLOSED (2026-07-10)

**Originally measured 2026-07-09** as 12 rows (2019–2022) missing `gen_*`/`outage_*`. Root cause turned out to be two distinct bugs, not one "merged-text blob" as first assumed — see Phase 2 below for the fix. All 12 rows now have `gen_*`/`outage_*` fully populated, verified against the raw PDF text by hand.

| Date | Year |
|------|------|
| 2019-03-29, 2019-03-30 | 2019 |
| 2019-11-18, 2019-11-19 | 2019 |
| 2021-04-22, 2021-05-31, 2021-06-01, 2021-07-10, 2021-09-05, 2021-09-21, 2021-10-15 | 2021 |
| 2022-06-01 | 2022 |

---

## Phase 1 — Feature tables ready for modelling ✅ COMPLETE (2026-07-01)

**Goal:** one command rebuilds everything; automated validation catches regressions; data dictionary published.

### 1a. `build_all.py` — single-command pipeline ✅ COMPLETE (Abhi, 2026-06-29)

Script written and verified. Lives at `Pipeline/build_all.py`.

Implements all 4 steps:
- `Dataset/Raw/File1_Raw` → `f1_daily.csv` (subprocess)
- `Dataset/Raw/File2_Raw` → `Dataset/study1_daily.csv` (subprocess)
- `Dataset/Raw/File3_Raw` → `Dataset/study2_scada.csv` (subprocess)
- `f1_daily` + `hourlyLoadDataIndia.xlsx` → `Dataset/study1_hourly.csv` (in-process join)

Flags: `--skip-file1/2/3`, `--skip-hourly`, `--only-hourly`

Post-run prints row × col counts, date range, overall null %, 8 worst-null cols, and warns if any dataset falls below baseline row count. Does **not** run the validation gate (1b) or push to Kaggle — those are separate.

> **Bug fixed on deploy:** original had `HOURLY_SRC = REPO_ROOT / "hourlyLoadDataIndia.xlsx"` — corrected to `Reference/hourlyLoadDataIndia.xlsx` where the file actually lives. Also fixes `_print_summary` to handle `datetime` col in `study1_hourly.csv`.

### 1b. Validation gate ✅ COMPLETE (2026-07-01)

Script: `Pipeline/validate.py`. Run after every rebuild. Exits 0 on all pass, 1 on any FAIL.

| Check | Dataset | Level if triggered |
|-------|---------|-------------------|
| Column count unchanged | all three | FAIL |
| Row count >= baseline | all three | FAIL |
| No duplicate dates / (date, hhmm) pairs | all three | FAIL |
| Data freshness (latest date within 5 days) | study1_daily, study2_scada | WARN |
| `xb_export_*` >= 0 | study1_daily | WARN |
| `xb_net_* = import − export` per country (abs diff < 0.01) | study1_daily | WARN |
| `ir_*_net = import − export` per corridor (abs diff < 0.01) | study1_daily | WARN |
| No 63-slot days | study2_scada | FAIL |
| Days with slot count outside {95, 96, 97, 98}: > 10 days | study2_scada | FAIL |
| Days with slot count outside {95, 96, 97, 98}: <= 10 days | study2_scada | WARN |
| `freq_hz` outside [47, 52] Hz | study2_scada | WARN |

Checks not yet implemented: null % per column vs stored baseline; date continuity against the known 70-gap list (gap list is prose in this roadmap, not machine-readable).

> **Col count note:** study2_scada baseline set to 164 (observed). Roadmap previously stated 165. Discrepancy not yet traced to a specific missing column.

### 1c. Data dictionary ✅ COMPLETE (2026-07-01)

Script: `Pipeline/build_data_dict.py`. Generates `Dataset/data_dictionary.xlsx`.

Four sheets: `study1_daily` (144 cols), `study2_scada` (164 cols), `study1_hourly` (151 cols), `master` (union of all unique columns). Fields: `column_name`, `datasets`, `unit`, `source_section`, `schema_start_date`, `notes`. All columns have unit and source section populated. Notes cover all domain-specific columns (derivation, caveats, schema gaps).

### 1d. Kaggle publish ✅ COMPLETE

Three CSVs auto-pushed to Kaggle on every daily update via GitHub Actions (`kaggle datasets version`). `KAGGLE_USERNAME` / `KAGGLE_KEY` secrets are set and working.

---

## Phase 2 — Coverage expansion 🔶 PARTIALLY COMPLETE (2026-07-10)

**Owner:** Sagnik — this is scraper/parser work, same skillset as Phase 0/1, not delegated.

| Task | Priority | Status |
|------|----------|--------|
| Text-regex fallback for generation/outage on 12 merged-blob PDFs (last ~0.5% of rows) | Medium | ✅ Done |
| §C state-level table → `study3_states.csv` (~40 state entities, daily) — optional separate study | Low | 🔲 Not started |
| Backfill 2025-05-22/23 if NLDC re-publishes | Low | 🔲 Blocked on NLDC (not actionable by us) |

### What was actually wrong (found by inspecting raw PDFs directly, 2026-07-10)

The original "merged-text blob with no column grid" theory was wrong. Two distinct, unrelated bugs were found instead:

1. **Some 2019 PDFs (e.g. 29/30.03.19) DO have a well-structured Section G table** — `pdfplumber.extract_tables()` detects it fine — but the "All India" header cell renders as a stray `'0'` character. The parser's `_pdf_generation()` only matched by searching the header text for "all india", so it silently skipped an otherwise-perfectly-good table.
2. **Some 2021 PDFs never produce a detected table for Section F/G at all** (no visible gridlines in that part of the page), even though `extract_text()` returns the section as normal, cleanly whitespace-delimited rows.

### What was built

A single new function, `_pdf_gen_outage_text_fallback()`, added to both `Scrapings/parse_psp_pdf_xls_file1.py` and `parse_psp_pdf_xls_file2.py` (the two files are byte-identical, so both got the same edit). It works directly on `extract_text()` output — bypassing `extract_tables()`'s column-header matching entirely — and matches row labels by stripping everything but letters (handles labels that gain/lose internal spaces across report eras, e.g. "Gas, Naptha & Diesel" vs "Gas,Naptha&Diesel"), then pulls data columns *positionally* from the numbers found on each line, since a trailing %Share column exists in some report eras and not others. Wired into `parse_pdf()` as a last resort, only filling keys still missing after the existing table-based passes — never overwrites a correctly-parsed value.

**Bonus fix, found along the way:** rebuilding surfaced two new all-null rows dated 2014-08-14/17 that hadn't existed in the previously-committed dataset. Root cause: `15.08.20_NLDC_PSP.pdf` and `18.08.20_NLDC_PSP.pdf` are old enough to lack a subject line, so the parser falls back to the PDF's own "Date of Reporting" field — which itself has a genuine NLDC-side typo, literally printing "15-Aug-**14**" instead of "15-Aug-**20**". Added a `MIN_VALID_DATE` guard (2018-12-01, the dataset's documented start) in `build_dataset()` that drops any row dated earlier and logs what it dropped, since such a date can only be a source/parse artifact.

### Verification (2026-07-10)

- All 12 originally-affected dates confirmed populated (`gen_total_mu`, `outage_total_total_mw`, and individual `gen_coal_mu` etc.), cross-checked by hand against raw PDF text for 3 dates.
- The 2 bogus 2014 rows confirmed dropped; `study1_daily`'s date range is back to the documented 2018-12-31 start.
- `Pipeline/validate.py`: all `study1_daily`/`study1_hourly` checks pass (2 pre-existing WARNs on `xb_net` identity, unrelated). The only FAIL is the already-documented, unrelated `study2_scada` 2025-10-02 63-slot day (File3/XLS parser, untouched by this work).

### Still open (both low priority, unchanged from original scope)

1. §C state-level table → `study3_states.csv` — a genuinely separate mini-project (new parser section, new output CSV, new `build_all.py` step, new `validate.py` checks), not started.
2. 2025-05-22/23 backfill — not actionable until/unless NLDC re-publishes those dates on their own end.

### Where the code lives

- Parsers: `Scrapings/parse_psp_pdf_xls_file1.py`, `parse_psp_pdf_xls_file2.py` (identical files, both patched)
- Pipeline entry point: `Pipeline/build_all.py`
- Validation: `Pipeline/validate.py`

### Environment

Local Python, same as the existing `Scrapings`/`Pipeline` scripts — no Colab/ML environment needed, this is pure data engineering, not modelling.

---

## ML Development Environment

This section covers decisions made for how the ML work across Phase 3 and Phase 4 will be developed, shared, and deployed. These decisions account for two collaborators working on the same codebase.

### Environment choice: GitHub + Google Colab

Development will be done in Google Colab, with notebooks version-controlled in this repository. This was chosen over local development for two reasons: the project has two collaborators, and local development requires both to maintain identical environments and hardware. Colab eliminates that friction entirely. Anyone with access to the repository can open a notebook in Colab and run it immediately with no setup.

Local development was considered and rejected as the primary environment despite adequate hardware (Ryzen 9 8945HS, RTX 4060, 16GB RAM) because the collaboration requirement outweighs the hardware advantage. The datasets are small enough (study1_daily: 2,660 rows; study2_scada: 55,068 rows) that Colab's free T4 GPU is sufficient for all models planned, including LSTM. Training times are expected to be in the range of seconds to a few minutes for both studies.

Kaggle notebooks were also considered. They were rejected as the primary development environment because collaboration between two accounts on Kaggle is awkward (notebooks fork rather than share a single source), and the 30 GPU hours per week quota becomes limiting during active iteration. Kaggle will instead be used as a public mirror: once a notebook is complete and clean, it will be uploaded to the existing Kaggle dataset page so that dataset users can find the accompanying analysis. This serves the portfolio goal without making Kaggle the development bottleneck.

### Workflow

```
GitHub repo (ML/ folder)
    |-- open notebook in Colab from GitHub
    |-- load dataset via Kaggle API (one line, credentials already set up)
    |-- develop, train, iterate
    |-- commit updated notebook back to repo via git
    |-- on merge: GitHub Actions runs predict.py to generate daily inference JSON
    |-- Kaggle: upload clean finished notebooks as dataset companion notebooks (portfolio)
```

### Code format

Jupyter notebooks for EDA and model training. Python scripts for the production inference pipeline that GitHub Actions runs daily. The split is intentional: notebooks allow interactive exploration and visualisation during development; scripts are reproducible, testable, and CI-friendly.

Feature engineering logic that is shared between training notebooks and the inference script lives in a standalone Python module (`ML/Study1/features.py`, `ML/Study2/features.py`) so that the same transformations are applied at train time and inference time without duplication.

### Repository structure for ML work

```
ML/
├── Study1/
│   ├── notebooks/
│   │   ├── 01_eda.ipynb            EDA: demand trends, seasonality, generation mix, missing data
│   │   ├── 02_features.ipynb       Feature engineering: lags, rolling stats, seasonality encoding
│   │   └── 03_baseline.ipynb       LightGBM baseline, time-aware split, metrics, feature importance
│   ├── features.py                 Shared feature engineering module (used by notebooks and predict.py)
│   ├── predict.py                  GitHub Actions inference script: loads model, outputs predictions JSON
│   └── models/                     Trained model artifacts (gitignored, not committed to repo)
└── Study2/
    └── (same structure, Phase 4)
```

Model artifacts are gitignored. The trained model will be stored separately (options: Git LFS, a GitHub release asset, or a small model committed directly if under 50MB) and documented here once Phase 3 training is complete.

### Environment file

`ML/environment.yml` defines the conda environment for reproducibility. Key dependencies: Python 3.11, pandas, numpy, scikit-learn, lightgbm, torch, matplotlib, plotly, kaggle, jupyterlab.

---

## Central research question (2026-07-09) — spans Phases 3, 4, 5, 6

**As India's grid monitoring granularity and renewable penetration have both increased 2019→2026, how has the observability and predictability of grid stress (demand ramps, frequency deviations) evolved — and once corridor/cross-border visibility exists in the data, do inter-regional congestion and cross-border exchange meaningfully predict short-term grid stress?**

This supersedes treating Study 1 and Study 2 as two unrelated baselines. It's answered across **three eras**, each analyzed using the dataset that actually covers it — all three CSVs are load-bearing, none is decorative:

| Era | Window | What's available | What it answers | Dataset(s) used |
|---|---|---|---|---|
| **1 — Pre-corridor** | 2019–2022 | Daily features (full range) + hourly demand curve | Intra-day ramp characteristics; RES-share growth trend; establishes the baseline "ramp shocks becoming more frequent" evidence | `study1_daily.csv` + `study1_hourly.csv` |
| **2 — Corridor-visible** | 2023–Oct 2024 | Daily features + IR-line (from 2023-01-01) + cross-border (from 2023-07-06) | Daily-resolution first pass: does corridor congestion / cross-border exchange correlate with daily frequency-band stress (`freq_pct_*`)? | `study1_daily.csv` |
| **3 — Live full-visibility** | Nov 2024–present | 15-min SCADA + full corridor/cross-border broadcast + real frequency violations | Live, high-resolution, early-warning (lead-time) classifier: corridor/cross-border-aware ramp-shock + frequency-violation prediction | `study2_scada.csv` |

**Why three eras, not one uniform model:** verified directly against the data (2026-07-09) — IR-line columns are null before 2023-01-01 (only 1,253 of 2,677 daily rows populated) and cross-border columns before 2023-07-06. There is no way to test the corridor/cross-border relationship across the full 2019–2026 span because the columns simply don't exist for most of it. Rather than pretending otherwise, the study is structured around what each era's data actually supports — this is a feature of the design, not a workaround.

**Cross-phase dependency (accepted 2026-07-09):** phases run sequentially where the research question requires it — Phase 4's Era 3 model consumes Phase 3's forecast-residual signal, and Era 2's findings inform Era 3's feature design. Both collaborators are fine waiting on each other where the design calls for it; this is no longer being avoided for parallelism's sake.

**Novelty check (verified via web search, 2026-07-09) — what already exists vs. what doesn't:**
- Corridor-congestion → frequency-stability modelling: **exists** for European grids (explainable-AI studies on Germany and three European synchronous areas) — established method, **not done for India**.
- Cross-border-exchange → grid-stability modelling: **only qualitative/policy discussion found** (e.g. the real April 2020 "9pm9minute" event, where neighbouring countries' hydro ramped up to help balance India's grid) — no quantitative model found for India or elsewhere in this specific form.
- RE-penetration driving rising Indian grid stress: **a macro-level claim already exists** — an EAC-PM policy paper reported 2026-07-07 (two days before this analysis) makes almost this exact claim. This project's contribution must be positioned as a **granular, reproducible, ML-based complement to that finding**, not a discovery claim.
- A three-era, evolving-observability design tied to one country's actual operational dataset: **no matching paper found** (related but distinct: PSML multi-scale benchmark dataset, Smart5Grid observability platform — neither is this specific design).
- Second, targeted search for "India + frequency violation + ramp event + corridor congestion + ML" returned **no matching papers** — this specific combination, for India, appears genuinely open.

---

## Phase 3 — Study 1: daily forecasting + Era 1 ramp characterization ✅

**Owner:** collaborator (handed off 2026-07-09, completed 2026-07-10).

**Datasets used:** `study1_daily.csv` (2,660 rows × 144 cols, 2019–present) for the forecasting model and the full-history RES-share trend; `study1_hourly.csv` (46,728 rows × 151 cols, 2019–2024, frozen) for the **Era 1** intra-day ramp characterization — this is a real analytical deliverable, not a dashboard-only afterthought.

**Targets:**
1. Next-day national demand/energy regression. **Note:** confirm the exact column before building — the CSV header currently has `max_demand_met_total_mw` / `evening_peak_demand_total_mw` and `energy_met_total_mu`, not `peak_demand_met_total_mw` as earlier prose in this doc said.
2. Era 1 (2019–2022) intra-day demand-ramp magnitude/frequency characterization from the hourly curve, correlated against `share_res_pct` — a historical analysis, not a live model.

### Goal

Predict next-day national (and ideally per-region) demand/energy from `study1_daily.csv`, output a forecast-residual signal for Phase 4 to consume, and produce the Era 1 historical ramp-characterization analysis from `study1_hourly.csv` that motivates the whole project's central research question.

### What already exists

`ML/environment.yml`, `ML/Study1/features.py`, and all four notebooks (`01_eda.ipynb`, `02_features.ipynb`, `03_baseline.ipynb`, `04_era1_ramp_characterization.ipynb`) are built and committed under `ML/Study1/notebooks/`. `predict.py` not yet built (deferred, per "Done when" below).

Confirmed target column: `max_demand_met_total_mw`.

### Bug found and fixed (2026-07-10, after initial "done" claim)

The first committed version of `03_baseline.ipynb` had a real off-by-one bug: it used `TARGET_lag1` as both the delta-training anchor and the naive-persistence comparison baseline. But `TARGET_lag1` was computed from lag features built **before** the target got shifted forward to represent "tomorrow's demand" — so after the shift, `lag1` ended up anchored **two days** before the forecast date instead of one. This wasn't caught by re-reading the notebook; it was found by actually re-running the code against the live data.

**Verified empirically:** a correctly-anchored (1-day-lag) naive-persistence baseline (MAPE 0.0242, RMSE 6,978.5) actually **beat** the originally-reported LightGBM result (MAPE 0.0247, RMSE 7,387.8) — meaning the "model beats naive persistence" claim, as first reported, was not true; the comparison itself was broken.

**Fix:** added `make_next_day_target()` to `features.py` — a single function that shifts the target *and* preserves today's true value as `{TARGET}_today` before doing so, so the correct anchor can never again be silently destroyed by an in-place overwrite. `03_baseline.ipynb` updated to use it. Re-verified by re-running the corrected pipeline end-to-end against the live dataset:

**Corrected results (2026-07-10, verified):**
- LightGBM: **MAPE 0.0175, RMSE 5,242.9, MAE 3,800.8**
- Naive persistence (correct 1-day anchor): MAPE 0.0242, RMSE 6,978.5, MAE 5,258.4
- LightGBM genuinely and comfortably beats naive persistence — a *larger* margin than the original (invalid) comparison claimed.

Also fixed while verifying: `01_eda.ipynb` had its single cell's content accidentally duplicated ~15x (harmless but messy — deduped to one clean copy); `04_era1_ramp_characterization.ipynb` sorted the hourly frame by `"date"` alone before computing hour-to-hour deltas, which isn't guaranteed to preserve correct within-day hour order under an unstable sort — changed to sort by `"datetime"`.

Other results (unaffected by the bug above, verified sound on review):
- Era 1 ramp magnitude/frequency vs `share_res_pct`: correlation -0.367 / -0.429 respectively (monthly-aggregated, 2019–2022) — chart and `era1_ramp_vs_res_share.csv` produced. Note: both series share strong annual seasonality, so this correlation may be partly confounded by season rather than a clean RES-driven effect.
- 69 missing dates found in `study1_daily.csv` (vs ~70 expected — consistent with Phase 0 documentation).
- `ir_*`/`xb_*` corridor columns (only populated from 2023+) excluded from Study 1 features; revisit only if later feature importance suggests value.

### What needs to be built

```
ML/
├── environment.yml                        conda env: Python 3.11, pandas, numpy, scikit-learn,
│                                           lightgbm, torch, matplotlib, plotly, kaggle, jupyterlab
└── Study1/
    ├── notebooks/
    │   ├── 01_eda.ipynb                   Demand trends, seasonality, generation mix shift, missing data
    │   ├── 02_features.ipynb              Lag features, rolling stats, calendar/seasonality encoding
    │   ├── 03_baseline.ipynb              LightGBM baseline, time-aware split, metrics, feature importance
    │   └── 04_era1_ramp_characterization.ipynb   Intra-day ramp magnitude/frequency from study1_hourly
    │                                              (2019–2022), correlated against share_res_pct — the Era 1 deliverable
    ├── features.py                        Shared feature-engineering functions
    └── predict.py                         Outputs the next-day forecast AND the forecast-residual signal
                                            (actual − predicted, once actual is known) that Phase 4 consumes
```

### Where the data lives

`Dataset/study1_daily.csv` — one `date` column + 143 feature columns:

| Group | Example columns | Availability |
|-------|-------------|--------------|
| Regional demand/energy | `evening_peak_demand_*_mw`, `energy_met_*_mu`, `max_demand_met_*_mw` | Full range |
| Generation mix | `gen_coal_mu`, `gen_hydro_mu`, `gen_nuclear_mu`, `gen_res_mu`, `hydro_gen_*_mu`, `wind_gen_*_mu`, `solar_gen_*_mu` | Full range |
| Shortages | `peak_shortage_*_mw`, `energy_shortage_*_mu` | Full range |
| Frequency | `freq_fvi`, `freq_pct_below_497` … `freq_pct_above_5005` | Full range |
| IR-Line corridor flows | 21 `ir_*` cols (export/import/net per corridor) | From 2023-01-01 (verified) |
| Cross-border exchange | 12 `xb_*` cols (Bhutan/Nepal/Bangladesh/Myanmar) | From 2023-07-06 (verified) |
| Diversity / RES share | `diversity_regional`, `share_res_pct` | Full range |

`Dataset/study1_hourly.csv` — used specifically for Era 1 (2019–2022, though the file runs to April 2024):

| Group | Example columns | Notes |
|-------|-------------|-------|
| Hourly national + regional demand | `National Hourly Demand`, `Northern/Western/Eastern/Southern/North-Eastern Region Hourly Demand` | The only genuinely hourly signal in this file — everything else is `study1_daily`'s features broadcast across 24 rows |

70 daily rows have known irreducible gaps (documented under Phase 0) — forward-fill or exclude, don't blindly interpolate.

### Step by step

1. **`01_eda.ipynb`** — plot demand over time, check yearly/weekly/festival seasonality, quantify missingness, confirm the exact target column.
2. **`02_features.ipynb` + `features.py`** — lag features (t−1, t−7, t−365), 7-day/30-day rolling mean/std, calendar features. Every reusable transform goes into `features.py`, never pasted inline.
3. **`03_baseline.ipynb`** — time-aware split (2019–2022 train, 2023 val, 2024–2026 test). Train LightGBM/XGBoost. Compare against naive persistence. Compute and expose the forecast residual as a reusable artifact (needed by Phase 4).
4. **`04_era1_ramp_characterization.ipynb`** — using `study1_hourly.csv` restricted to 2019–2022: compute hour-to-hour demand deltas per region, define a ramp-magnitude metric, plot its trend over time against `share_res_pct` from `study1_daily`. This is the chart that establishes the project's central motivating claim and feeds Phase 6's introduction.
5. **(Stretch, later)** — LSTM or Temporal Fusion Transformer for the demand forecast, once the LightGBM baseline and its feature importances are understood.
6. **Metrics** — MAPE, RMSE, MAE for the forecast; magnitude/frequency trend statistics for the Era 1 ramp analysis.

### Outputs

- Next-day national + regional demand forecast, plus its residual signal (feeds Phase 4)
- Era 1 (2019–2022) ramp-characterization trend vs. RES-share growth (feeds Phase 5's "Era 1" dashboard tab and Phase 6's introduction)
- Feature importance ranking

### Environment

Google Colab (see "ML Development Environment" above) — notebooks committed to the repo, dataset loaded via the Kaggle API, `ML/environment.yml` created first. Model artifact gitignored; storage method (Git LFS / GitHub release asset / direct commit if <50MB) decided once training is done.

### Done when

~~`ML/environment.yml`, `ML/Study1/features.py`, and all four notebooks are committed; the baseline model beats naive persistence on MAPE/RMSE on the 2024–2026 test window; the Era 1 ramp-characterization trend is produced and charted.~~ **All done and independently re-verified as of 2026-07-10** (see "Bug found and fixed" above — the first pass had a broken naive-persistence comparison; corrected and re-run against live data before being marked complete here). `predict.py` and GitHub Actions wiring can follow after.

---

## Phase 4 — Study 2: corridor-aware grid-stress early-warning classifier 🔲

**Owner:** TBD — starts after Phase 3 by design (consumes Phase 3's forecast-residual signal; the two collaborators have agreed sequencing is fine).

**Datasets used:** `study1_daily.csv` for the Era 2 (2023–Oct 2024) daily-resolution pre-check; `study2_scada.csv` (55,068 rows × 164/165 cols, 96 slots/day, Nov 2024–present) for the Era 3 live model.

**Targets (two, sharing most feature engineering):**
1. Binary — did a frequency violation (Hz outside [49.7, 50.2]) occur, predicted **1–4 slots (15–60 min) ahead**, not just classified retrospectively.
2. Binary — was there a "ramp shock" (a sudden, sharp swing in demand or net load between consecutive slots), same lead-time framing.

**Measured 2026-07-09 against the live data:** frequency-violation rate in `study2_scada.csv` is 0.88% (503 of 56,892 rows) — a workable, non-degenerate class balance for both targets.

### Goal

Answer the Era 2 + Era 3 parts of the central research question: does corridor congestion (`ir_*`) or cross-border exchange (`xb_*`) predict grid stress, first at daily resolution where only daily data has corridor visibility (Era 2), then live at 15-minute resolution with lead time once SCADA data exists (Era 3). The two binary targets are causally linked — a sudden generation-demand imbalance (ramp shock) is what produces a frequency deviation (violation) — so they're modelled together, not as separate studies, and Study 1's forecast-residual becomes an explicit input feature (an unusually large residual is itself a leading indicator of stress).

**Why this replaced the original `study1_hourly`-based ramp-shock idea:** classifying sudden demand swings was originally scoped against the frozen, hourly-only `study1_hourly.csv` (2019–2024). That dataset can't feed a live dashboard and is coarser than what's available live. `study2_scada` gives 15-minute resolution and updates daily from Nov 2024 onward — a strict upgrade for this target. `study1_hourly`'s ramp signal is retained in Phase 3 (Era 1 analysis) and Phase 5 (dashboard tab) as historical motivating evidence, not as a modelling deliverable.

### What already exists

Nothing yet — no `ML/Study2/` directory.

### What needs to be built

```
ML/Study2/
├── notebooks/
│   ├── 00_era2_daily_correlation.ipynb   Era 2 (2023–Oct 2024) pre-check on study1_daily: does ir_*/xb_*
│   │                                      correlate with freq_pct_* stress indicators at daily resolution?
│   ├── 01_eda.ipynb                      Era 3 SCADA EDA: violation + ramp-shock rate by hour/season/gen-mix/corridor
│   ├── 02_features.ipynb                 Slot-level + lag-1 features, ramp-magnitude features, Study 1's
│   │                                      forecast-residual broadcast in as a feature, class-imbalance handling
│   ├── 03_violation_baseline.ipynb       LightGBM baseline for the lead-time frequency-violation target
│   └── 04_ramp_shock_baseline.ipynb      LightGBM baseline for the lead-time ramp-shock target (shares features.py)
├── features.py                           Shared feature-engineering functions (same pattern as Study1)
└── predict.py                            GitHub Actions inference script — outputs both targets
```

### Where the data lives

`Dataset/study1_daily.csv` (Era 2 pre-check, 2023–Oct 2024 subset): `ir_*` (21 cols), `xb_*` (12 cols), `freq_pct_*` bands.

`Dataset/study2_scada.csv` (Era 3, one row per 15-min block):

| Group | Key columns | Notes |
|-------|-------------|-------|
| Timestamp | `date`, `time`, `hhmm` | |
| Real-time generation mix | `nuclear_mw`, `wind_mw`, `solar_mw`, `hydro_mw`, `gas_mw`, `thermal_mw`, `total_gen_mw` | Per 15-min slot |
| Demand | `demand_met_mw`, `net_demand_met_mw` | Per slot — ramp-shock label derives from the slot-to-slot delta of these |
| Net transmission | `net_trans_exchange_mw` | Per slot |
| Evening peak by region | NR/WR/SR/ER/NER | Broadcast from daily |
| IR-Line + cross-border | 21 `ir_*` + 12 `xb_*` cols | Broadcast from daily — fully populated for all of `study2_scada`'s Nov 2024–present range (verified 2026-07-09: corridor data has existed since 2023, before SCADA data starts) |
| Frequency | `freq_hz`, `freq_fvi`, `freq_pct_*` bands | Per slot — used to derive the violation label |
| Study 1 residual | *(new, produced by Phase 3's `predict.py`)* | Broadcast per day, same pattern as other daily-to-slot broadcasts |

One known bad day (2025-10-02, 63 slots) must be dropped before training; a handful of other days have 95/98 slots (DST/truncation edge cases) — handle explicitly, don't silently drop or pad.

### Step by step

1. **`00_era2_daily_correlation.ipynb`** — on `study1_daily.csv` restricted to 2023–Oct 2024, test whether `ir_*`/`xb_*` levels correlate with `freq_pct_*` stress indicators at daily resolution. This is a real analysis, not a placeholder — its findings inform which corridor/cross-border features matter most for Era 3's feature engineering.
2. Define the violation label from `freq_hz` against the 49.7–50.2 Hz nominal band (NLDC grid code), shifted to a 1–4-slot lead-time target.
3. Define the ramp-shock label: a threshold on the slot-to-slot change in `demand_met_mw`/`net_demand_met_mw`, same lead-time shift.
4. **`01_eda.ipynb`** — both event rates by hour, season, generation mix, corridor stress in the live SCADA data.
5. **`02_features.ipynb` + `features.py`** — slot-level + lag-1-slot features, ramp-magnitude features, Study 1's forecast-residual as an input feature; address class imbalance (SMOTE or class-weighted loss — both targets are rare events, ~0.88% base rate for violations).
6. **`03_violation_baseline.ipynb`** — time-aware split: 2024-11→2025-06 train, 2025-07→2025-12 val, 2026 test. LightGBM baseline.
7. **`04_ramp_shock_baseline.ipynb`** — same split, same feature pipeline, LightGBM baseline.
8. **(Stretch)** — temporal CNN or LSTM over the 96-slot daily window.
9. **Metrics** — PR-AUC, recall at 95% precision, F1 for both targets.

### Outputs

- Era 2 daily-resolution corridor/cross-border-vs-stress correlation findings
- 15–60-min-ahead frequency-violation probability
- 15–60-min-ahead ramp-shock probability
- Feature importance: which corridor / cross-border level / forecast-residual is most predictive of each
- Risk heatmap: time-of-day × day-of-week event frequency (dashboard panel)
- Threshold analysis: precision-recall curve, for both targets

### Environment

Same as Phase 3 — Google Colab, `ML/environment.yml`, dataset via Kaggle API.

---

## Phase 5 — Dashboard 🔲

**Vision:** public GitHub Pages site combining live data feed + model inference + historical explorer.

### The Historical Explorer mirrors the three-era research design (2026-07-09)

Rather than one undifferentiated set of time-series charts, the Historical Explorer is structured around the same three eras used in Phases 3/4/6 — each tab uses the dataset that actually covers it, and each is a real analytical output from those phases, not raw unprocessed charting:

- **Era 1 tab (2019–2022, non-live):** intra-day ramp magnitude/frequency trend vs. rising `share_res_pct`, from Phase 3's `04_era1_ramp_characterization.ipynb`. Source: `study1_hourly.csv`. Framed explicitly as motivating evidence for the live Phase 4 classifier, not a prediction of its own.
- **Era 2 tab (2023–Oct 2024, non-live):** daily-resolution corridor/cross-border-vs-stress correlation, from Phase 4's `00_era2_daily_correlation.ipynb`. Source: `study1_daily.csv`.
- **Era 3 (live, this is the "Study 2 risk" panel below, not a Historical Explorer tab):** today's live corridor-aware risk timeline. Source: `study2_scada.csv`.

This means all three CSVs appear in the dashboard for the era each one actually covers — `study1_hourly` and the Era 2 daily subset are never presented as live or current, only as historical, clearly dated evidence.

### Panels

| Panel | Description | Data source |
|-------|-------------|-------------|
| **Live grid status** | Today's key metrics (peak demand, generation mix, frequency stats) as they arrive | `study1_daily.csv` latest row |
| **Study 1 forecast** | Next-day demand forecast (national + regional) with confidence interval | Study 1 model output |
| **Study 2 risk** | Today's 96-slot corridor-aware frequency-violation + ramp-shock risk timeline (Era 3, live) | Study 2 model output on today's SCADA |
| **Historical explorer** | Interactive time-series charts: demand trends, generation mix, IR-line flows, cross-border exchange | Full `study1_daily.csv` |
| ↳ *Era 1: Ramp-shock history* (tab) | Intra-day ramp trend 2019–2022 vs. rising RES share — motivating evidence, non-live | `study1_hourly.csv` |
| ↳ *Era 2: Corridor-stress correlation* (tab) | Daily-resolution corridor/cross-border vs. frequency-stress correlation, 2023–Oct 2024, non-live | `study1_daily.csv` (2023+ subset) |
| **Anomaly log** | Days where actual demand deviated >X% from forecast, or violation/ramp-shock rate was elevated | Derived |

### What already exists

Nothing — no dashboard code, no frontend, no `predict.py` inference scripts yet. Entirely blocked on Phase 3 and Phase 4 producing trained models first.

### What needs to be built

- `ML/Study1/predict.py` and `ML/Study2/predict.py` — load the trained model, run on the latest data, write a predictions JSON
- A GitHub Actions job (alongside the existing daily scrape workflow) that runs both `predict.py` scripts daily and commits the output JSON to the repo
- A static frontend (plain HTML/JS + a charting library) that reads the committed JSON/CSVs directly — no backend, no API server

### Where the data/code will live

- Inference scripts: `ML/Study1/predict.py`, `ML/Study2/predict.py` (per Phase 3/4 structure)
- Predictions output: new committed JSON files, e.g. `Dataset/predictions/study1_forecast.json`, `Dataset/predictions/study2_risk.json` (path TBD)
- Frontend: new top-level `docs/` or `dashboard/` folder, served via GitHub Pages
- CI: extend `.github/workflows/daily_scrape.yml` or add a new workflow file for the inference step

### Step by step

1. Once Phase 3's baseline model is trained, write `ML/Study1/predict.py` to load it and output a forecast JSON for the next day.
2. Once Phase 4's baseline model is trained, write `ML/Study2/predict.py` similarly for the 96-slot risk timeline.
3. Wire both into a GitHub Actions workflow that runs after the daily scrape, so predictions are always based on the freshest data.
4. Build the static dashboard: start with the Historical Explorer panel (needs no model, can be built in parallel with Phase 3/4), then add the Live/Forecast/Risk panels once JSON output exists.
5. Deploy via GitHub Pages, pointed at the new frontend folder.

### Technical stack

- Static site on GitHub Pages (free hosting, no server)
- Python model inference runs in GitHub Actions each day → outputs JSON predictions committed to repo
- Frontend: lightweight JS (Plotly.js or Observable Plot) reading the committed JSON/CSV
- No backend required — all data is in the repo

### Environment

Frontend needs no build environment (plain HTML/JS, or a minimal static-site setup — decide framework, if any, when this phase starts). Inference scripts reuse `ML/environment.yml`, though the GitHub Actions job may want a slimmer inference-only requirements file to keep CI fast (training-only deps like `jupyterlab` aren't needed at inference time).

### Milestones

1. Historical Explorer panel live (no model dependency — can start anytime)
2. Phase 3 model done → export daily forecast JSON from GitHub Actions
3. Phase 4 model done → export slot-level risk JSON
4. Full dashboard consuming both + raw CSVs
5. Launch publicly on GitHub Pages

---

## Phase 6 — Research paper (conditional) 🔲

**Decision gate:** after Phase 3 + 4 are complete, assess whether results are strong enough to publish.

### Goal

Publish the dataset methodology and/or the two studies' modelling results, if results warrant it.

### What already exists

Nothing — no draft, no venue chosen, no writing environment set up. This phase can't meaningfully start until Phase 3/4 produce results to write about.

### Central claim

Using a novel, openly-published, multi-granularity NLDC dataset (7 years, three complementary resolutions), this project traces how the observability and predictability of grid stress in India has evolved as both monitoring granularity and renewable penetration increased — and shows, for the first time (per the novelty check below), that inter-regional corridor congestion and cross-border exchange have measurable predictive value for short-term grid stress once that visibility exists in the data (2023 onward).

### Where the material will come from

- Era 1 evidence: Phase 3's `04_era1_ramp_characterization.ipynb` (`study1_hourly.csv`, 2019–2022)
- Era 2 evidence: Phase 4's `00_era2_daily_correlation.ipynb` (`study1_daily.csv`, 2023–Oct 2024)
- Era 3 results: Phase 4's `03_violation_baseline.ipynb` + `04_ramp_shock_baseline.ipynb` (`study2_scada.csv`, Nov 2024–present), informed by Phase 3's forecast-residual signal
- Dataset methodology section: this roadmap's Phase 0 (parser fixes, spot-check log) and Phase 1 (validation gate, data dictionary) sections, plus `Dataset/README.md`
- Feature-importance / corridor-specific narrative: derived from Phase 4's per-corridor, per-country feature-importance rankings

### Related work / prior art (verified via web search, 2026-07-09 — starting point for the literature review, re-verify before submission since this is a fast-moving area)

| Claim | Status | Source |
|---|---|---|
| Corridor congestion predicts frequency stability | Done for European grids, not India | [Revealing drivers and risks for power grid frequency stability with explainable AI](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC8600233/); [Identifying drivers and mitigators for congestion in the German grid with XAI](https://www.sciencedirect.com/science/article/pii/S0306261923017154) |
| Cross-border exchange helps grid stability, India-specific | Only qualitative/policy evidence found (the April 2020 "9pm9minute" event), no quantitative model | [Cross-Border Electricity Cooperation in Southern Asia](https://www.mdpi.com/2227-9717/12/11/2324) |
| Rising RES share is stressing India's grid | Macro-level claim already made, very recently | [India's rising solar penetration is causing power grid stress: EAC-PM paper](https://www.business-standard.com/industry/news/india-s-rising-solar-penetration-is-causing-power-grid-stress-eac-pm-paper-126070701352_1.html) (reported 2026-07-07) |
| Multi-resolution / evolving-observability grid datasets | Exists in different form (PSML benchmark, Smart5Grid) — not this three-era, single-country design | [PSML multi-scale dataset](https://www.nature.com/articles/s41597-022-01455-7); [Smart5Grid observability](https://pmc.ncbi.nlm.nih.gov/articles/PMC10521069/) |
| India + frequency violation + ramp event + corridor congestion + ML (combined) | No matching paper found | Targeted search, 2026-07-09 — appears genuinely open |
| Plain gradient-boosting demand forecasting | Heavily saturated globally, including India-specific | [MANIT Bhopal-style India load forecasting work](https://www.frontiersin.org/journals/energy-research/articles/10.3389/fenrg.2024.1408119/full) — this is why Study 1's forecast is positioned as infrastructure, not a novelty claim |

### If yes, target venues

- IEEE NPSC (National Power Systems Conference) — India-focused, good fit for an applied/regional contribution
- *Electric Power Systems Research* (Elsevier) — broader journal, viable if Era 2/3 results are strong
- IEEE Transactions on Power Systems — higher bar; only pursue if results substantially exceed baseline expectations, since the underlying techniques (LightGBM, SHAP-style feature importance) are not themselves novel

### Paper structure (draft)

1. Introduction: why Indian grid forecasting matters (RE integration, frequency instability); state the central research question; motivate with Era 1's `study1_hourly` ramp-shock evidence (2019–2022 trend vs. rising RES share) and explicitly position relative to the EAC-PM finding (complements it with granular ML evidence, doesn't claim to discover the phenomenon)
2. Dataset: novel contribution — NLDC PSP reports scraped 2019–present, three complementary resolutions, methodology, gaps, verified corridor/cross-border onset dates
3. Era 2: daily-resolution corridor/cross-border-vs-stress correlation (2023–Oct 2024) — first quantitative pass before live modelling
4. Era 3: live corridor-aware, forecast-residual-informed, lead-time frequency-violation + ramp-shock classifier — features, models, results, real-time applicability
5. Discussion: which corridors / which cross-border partners are most predictive; how Era 1→2→3 evidence connects; comparison against the related work above
6. Conclusion + future work (e.g. state-level study, sequence models over the 96-slot window)

Dataset itself (NLDC PSP scraped + parsed, 7 years, three-resolution) is a secondary publishable contribution regardless of model results.

### Environment

Not yet decided — Overleaf (LaTeX) is the typical choice for IEEE/Elsevier venue templates; flagging as an open decision to make once this phase actually starts, not assuming it now.

---

## Appendix: Parser fixes log

| # | Symptom | Fix |
|---|---------|-----|
| 1 | Diversity cols empty pre-2020 | Single "All India Demand Diversity Factor" → `diversity_regional`; split kept for newer files |
| 2 | `max_demand_met_*` empty in 2019 PDFs | Time-row guard relaxed so "(MW) & time" row is kept |
| 3 | `xb_export`/`xb_import` had wrong values | Cross-border section scan bounded to its own block |
| 5a | Concatenated-text PDFs parsed empty | All PDF label matching is space-stripped |
| 5b | Section A on non-standard page | All-pages fallback in `parse_pdf` (fills only missing keys) |
| — | IR-Line not parsed for 2023–24 | `_xls_parse_ir_line` backported to file1/file2 → 21 `ir_*` cols now emitted for every XLS with an IR-Line sheet |
| — | Duplicate-date rows | `build_dataset` dedups by date, keeping richest (most non-null) row |

## Appendix: Spot-check log (Phase 0, 2026-06-24)

8 dates × 44 field comparisons — **0 mismatches**.

| Date | Era | Result |
|------|-----|--------|
| 2019-03-15 | PDF | ✓ |
| 2020-06-07 | PDF | ✓ |
| 2021-03-22 | PDF | ✓ |
| 2022-08-11 | PDF | ✓ |
| 2023-02-18 | XLS | ✓ |
| 2023-10-06 | XLS | ✓ |
| 2024-01-02 | XLS | ✓ |
| 2025-01-21 | XLS | ✓ |
