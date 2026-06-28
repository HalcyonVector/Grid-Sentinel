# Grid-Sentinel — Roadmap

_Last updated: 2026-06-29_

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
| **Study 2 — 15-min frequency-violation classifier** | `study2_scada.csv` | Binary: frequency violation in a 15-min slot? | 55,000+ × 165 | 2024-11-04 → present |

Study 1 also has an hourly variant (`study1_hourly.csv`, 46,728 rows × 151 cols, 2019-01-01 → 2024-04-30) joining PSP daily features with the Kaggle India hourly load data.

---

## Dataset inventory

| File | Rows | Cols | Date range | Source |
|------|------|------|------------|--------|
| `Dataset/study1_daily.csv` | 2,660 | 144 | 2018-12-31 → 2026-06-18 | `File2_Raw/` |
| `Dataset/study1_hourly.csv` | 46,728 | 151 | 2019-01-01 → 2024-04-30 | `File1_Raw/` + `hourlyLoadDataIndia.xlsx` |
| `Dataset/study2_scada.csv` | 55,068 | 165 | 2024-11-04 → 2026-06-18 | `File3_Raw/` |

### Build commands

```bash
# Rebuild study1_daily from File2_Raw
python Scrapings/parse_psp_pdf_xls_file2.py File2_Raw/ study1_daily.csv

# Rebuild f1_daily from File1_Raw, then join with hourly load
python Scrapings/parse_psp_pdf_xls_file1.py File1_Raw/ f1_daily.csv
# (join: hourlyLoadDataIndia.xlsx LEFT JOIN f1_daily on date)

# Rebuild study2_scada from File3_Raw
python Scrapings/parse_psp_xls_pdf_file3.py long File3_Raw/ study2_scada.csv

# Re-download missing dates
python Scrapings/download_psp_both.py START_DATE END_DATE File2_Raw/
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

## Phase 1 — Feature tables ready for modelling 🔲 IN PROGRESS

**Goal:** one command rebuilds everything; automated validation catches regressions; data dictionary published.

### 1a. `build_all.py` — single-command pipeline 🔲

Single script that:
- Calls each parser in order: File1 → `f1_daily`, File2 → `study1_daily`, File3 → `study2_scada`
- Joins `f1_daily` + `hourlyLoadDataIndia.xlsx` → `study1_hourly`
- Writes all outputs to `Dataset/`
- Prints row counts and null summary on completion

### 1b. Validation gate 🔲

Run after every rebuild. Checks:

| Check | Threshold |
|-------|-----------|
| Row count vs expected | ±5 rows |
| Date continuity (no new gaps vs baseline) | 0 new gaps |
| Null % per column vs baseline | <2% increase |
| `xb_export_*` ≥ 0 | 0 violations |
| `xb_net_* = import − export` per country | abs diff < 0.01 |
| `ir_*_net = import − export` per corridor | abs diff < 0.01 |
| study2 slots/day = 96 | ≤10 days with 95/98 allowed |
| study2_scada no 63-slot day | 0 |

### 1c. Data dictionary 🔲

`Dataset/data_dictionary.xlsx` with columns: `column_name`, `dataset`, `unit`, `source_section`, `schema_start_date`, `notes`. ~144 cols for study1, ~165 for study2.

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

**Dataset:** `study2_scada.csv` (55,068 rows × 165 cols, 96 slots/day, Nov 2024–present)

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
