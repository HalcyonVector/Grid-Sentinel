# Grid-Sentinel — Roadmap

_Last updated: 2026-07-01 (Phase 1 complete)_

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

### Residual parser gap (~1%)

~27 rows (2019–2022) still miss generation/outage/inter-regional/transnational because those PDF sections render as one merged-text blob with no column grid. Demand, energy, max-demand, frequency, diversity and RES-share **are** recovered. Closing this needs a text-regex fallback — deferred to Phase 2.

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

## Phase 2 — Coverage expansion 🔲

| Task | Priority |
|------|----------|
| Text-regex fallback for generation/outage on ~27 merged-blob PDFs (last ~1% of rows) | Medium |
| §C state-level table → `study3_states.csv` (~40 state entities, daily) — optional separate study | Low |
| Backfill 2025-05-22/23 if NLDC re-publishes | Low |

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

## Phase 3 — Study 1: Daily load forecasting 🔲

**Dataset:** `study1_daily.csv` (2,660 rows × 144 cols, 2019–present)

**Targets:** `peak_demand_met_total_mw` (next-day) and/or `energy_met_total_mu` (next-day)

### Feature groups

| Group | Key columns | Availability |
|-------|-------------|--------------|
| Generation mix | `gen_coal_mu`, `gen_hydro_mu`, `gen_nuclear_mu`, `gen_res_mu`, `gen_gas_mu` | Full range |
| Outages | `outage_central_*_mw`, `outage_state_*_mw` per region | Full range |
| IR-Line corridor flows | 21 `ir_*` cols (export/import/net per corridor) | ~2023 onward |
| Cross-border exchange | 12 `xb_*` cols (Bhutan/Nepal/Bangladesh/Myanmar) | ~2023 onward |
| Frequency | `freq_fvi`, `freq_pct_*` bands | Full range |
| Diversity | `diversity_regional`, `diversity_state` | Full range |
| RES share | `share_res_pct`, `share_nonfossil_pct` | Full range |
| Regional demand | `peak_demand_met_*_mw`, `energy_met_*_mu` per region | Full range |

### Modelling plan

1. EDA: seasonal decomposition, demand trends by region, generation mix shifts 2019→2026
2. Time-aware split: 2019–2022 train, 2023 val, 2024–2026 test (no leakage)
3. Baseline: gradient boosting (XGBoost / LightGBM) with lag features (t−1, t−7, t−365)
4. Sequence model: LSTM or Temporal Fusion Transformer
5. Metrics: MAPE, RMSE, MAE on held-out test set; compare vs naive persistence baseline

### Outputs

- Next-day national + regional peak demand forecast
- Feature importance ranking (which generation source / corridor / outage level drives demand)
- Rolling forecast plots for dashboard

---

## Phase 4 — Study 2: 15-min frequency-violation classifier 🔲

**Dataset:** `study2_scada.csv` (55,068 rows × 164 cols, 96 slots/day, Nov 2024–present)

**Target:** binary — did a frequency violation (Hz outside [49.7, 50.2]) occur in a given 15-min slot?

### Feature groups

| Group | Key columns | Notes |
|-------|-------------|-------|
| Real-time generation mix | `nuclear_mw`, `wind_mw`, `solar_mw`, `hydro_mw`, `gas_mw`, `thermal_mw` | Per 15-min slot |
| Demand | `demand_met_mw`, `net_demand_met_mw`, `total_gen_mw` | Per slot |
| Net transmission | `net_trans_exchange_mw` | Per slot |
| Evening peak by region | NR/WR/SR/ER/NER | Broadcast from daily |
| IR-Line corridor flows | 21 `ir_*` cols | Broadcast from daily |
| Cross-border exchange | `xb_*` cols | Broadcast from daily |
| Time features | `hhmm`, time-of-day, day-of-week, season | Derived |

### Modelling plan

1. Define violation label (NLDC grid code: 49.7–50.2 Hz nominal band)
2. EDA: violation rate by hour, season, generation mix, corridor stress
3. Handle class imbalance: SMOTE or class-weighted loss
4. Time-aware split: 2024-11 → 2025-06 train, 2025-07 → 2025-12 val, 2026 test
5. Baseline: LightGBM with slot-level + lag-1 slot features
6. Sequence model: temporal CNN or LSTM over the 96-slot daily window
7. Metrics: PR-AUC, recall at 95% precision, F1

### Outputs

- 15-min-ahead frequency violation probability
- Feature importance: which generation source / corridor imbalance is most predictive
- Risk heatmap: time-of-day × day-of-week violation frequency (good dashboard panel)
- Threshold analysis: precision-recall curve

---

## Phase 5 — Dashboard 🔲

**Vision:** public GitHub Pages site combining live data feed + model inference + historical explorer.

### Panels

| Panel | Description | Data source |
|-------|-------------|-------------|
| **Live grid status** | Today's key metrics (peak demand, generation mix, frequency stats) as they arrive | `study1_daily.csv` latest row |
| **Study 1 forecast** | Next-day demand forecast (national + regional) with confidence interval | Study 1 model output |
| **Study 2 risk** | Today's 96-slot frequency-violation risk timeline | Study 2 model output on today's SCADA |
| **Historical explorer** | Interactive time-series charts: demand trends, generation mix, IR-line flows, cross-border exchange | Full `study1_daily.csv` |
| **Anomaly log** | Days where actual demand deviated >X% from forecast, or violation rate was elevated | Derived |

### Technical stack (proposed)

- Static site on GitHub Pages (free hosting, no server)
- Python model inference runs in GitHub Actions each day → outputs JSON predictions committed to repo
- Frontend: lightweight JS (Plotly.js or Observable Plot) reading the committed JSON/CSV
- No backend required — all data is in the repo

### Milestones

1. Phase 3 model done → export daily forecast JSON from GitHub Actions
2. Phase 4 model done → export slot-level risk JSON
3. Build static dashboard consuming both + raw CSVs
4. Launch publicly on GitHub Pages

---

## Phase 6 — Research paper (conditional) 🔲

Decision gate: after Phase 3 + 4 are complete, assess whether results are strong enough to publish.

### If yes, target venues

- IEEE NPSC (National Power Systems Conference) — India-focused, good fit
- *Electric Power Systems Research* (Elsevier) — broader journal
- IEEE Transactions on Power Systems — higher bar, stronger results needed

### Paper structure (draft)

1. Introduction: why Indian grid forecasting matters (RE integration, frequency instability)
2. Dataset: novel contribution — NLDC PSP reports scraped 2019–present, methodology, gaps
3. Study 1: demand forecasting — features, model, results vs baseline
4. Study 2: frequency-violation classifier — features, model, results, real-time applicability
5. Discussion: feature importance findings, grid stress patterns
6. Conclusion + future work (e.g. state-level study, intra-day forecasting)

Dataset itself (NLDC PSP scraped + parsed, 7 years, multi-study) is a secondary publishable contribution regardless of model results.

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
