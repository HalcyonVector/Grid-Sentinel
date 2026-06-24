# Grid-Sentinel — Roadmap

_Last updated: 2026-06-24_

## What this project is

Grid-Sentinel is an ML project for **predicting / detecting stress on the Indian
power grid**, built on NLDC (National Load Despatch Centre) daily PSP reports.
Two studies:

- **Study 1 — Daily load forecasting.** Daily features scraped from the PSP
  PDF/XLS reports (peak demand, generation mix, outages, IR-line corridor flows,
  cross-border exchange, etc.) joined with the hourly Kaggle India load data
  aggregated to daily. Target: forecast grid load.
- **Study 2 — 15-minute frequency-violation classifier.** The `TimeSeries` sheet
  from the newer XLS files (FY2025+) — 96 readings/day of frequency, demand and
  generation mix — enriched with the MOP_E daily features + IR-Line corridor data
  + CrossBorder broadcast onto each 15-min row. Target: classify whether a
  frequency violation occurred in a given 15-min block.

Raw data: **Phase 1** = older PDFs + early XLS; **Phase 2** = newer XLS with the
`TimeSeries` sheet.

---

## Dataset inventory

| Dataset | File | Rows | Cols | Date range | Source folder |
|---------|------|------|------|------------|---------------|
| **study1_daily** | `Dataset/study1_daily.csv` | 2,660 | 144 | 2018-12-31 → 2026-06-18 | `File2_Raw/` |
| **study1_hourly** | `Dataset/study1_hourly.csv` | 46,728 | 151 | 2019-01-01 → 2024-04-30 | `File1_Raw/` + `hourlyLoadDataIndia.xlsx` |
| **study2_scada** | `Dataset/study2_scada.csv` | 55,068 | 165 | 2024-11-04 → 2026-06-18 | `File3_Raw/` |

Root-level files (`study1_daily.csv`, `study1_hourly.csv`, `study2_scada.csv`) are
mirrors of `Dataset/` and are the source of truth.  `f1_daily.csv` (intermediate
parse of File1_Raw before the hourly join) remains in root for reference.

### Build commands

```bash
# Rebuild study1_daily from File2_Raw
python Scrapings/parse_psp_pdf_xls_file2.py File2_Raw/ study1_daily.csv

# Rebuild f1_daily from File1_Raw, then join with hourly load
python Scrapings/parse_psp_pdf_xls_file1.py File1_Raw/ f1_daily.csv
# (join is done in Python: hourlyLoadDataIndia.xlsx LEFT JOIN f1_daily on date)

# Rebuild study2_scada from File3_Raw
python Scrapings/parse_psp_xls_pdf_file3.py long File3_Raw/ study2_scada.csv

# Re-download missing dates (both CDN formats)
python Scrapings/download_psp_both.py START_DATE END_DATE File2_Raw/
```

---

## 1. Parser fixes applied (verified against raw values)

| # | Symptom | Fix |
|---|---------|-----|
| 1 | diversity cols empty pre-2020 | Single "All India Demand Diversity Factor" → `diversity_regional`; split kept for newer files |
| 2 | `max_demand_met_*` empty in 2019 PDFs | Time-row guard relaxed (`not label.startswith("time")`) so the "(MW) & time" row is kept |
| 3 | `xb_export`/`xb_import` held wrong section's values | Cross-border section scan bounded to its own block |
| 5a | concatenated-text PDFs parsed empty | All PDF label matching is now space-stripped |
| 5b | Section A on a non-standard page | All-pages fallback in `parse_pdf` (fills only missing keys, never overwrites) |
| — | **IR-Line not parsed for 2023-24** | `_xls_parse_ir_line` backported to file1/file2 → 21 `ir_*` corridor columns now emitted for every XLS with an IR-Line sheet |
| — | duplicate-date rows | `build_dataset` now dedups by date, keeping the richest (most non-null) row |

### Date handling (as required)
- **PDF** → data date comes **only from the subject line** ("…for the date DD.MM.YYYY").
  This is the true data date and differs from the filename (e.g. `01.01.19` →
  **2018-12-31**). Fallback, only if a subject line is absent: **"Date of Reporting" − 1 day**
  (never the raw token, which was the publication date and off by one).
- **XLS** → **"Date of Reporting" − 1 day**.
  Note: XLS filename date = data date (Date of Reporting in the file = filename date + 1).

### Residual (~1% of rows, 2019-2022 only)
~27 rows still miss generation / outage / inter-regional / transnational, because
in those specific PDFs those sections render as one merged-text blob with no column
grid. Demand, energy, max-demand, frequency, diversity and RES-share **are** now
recovered for them. Closing the last 1% needs a text-regex fallback (Phase 2).

---

## 2. Data gaps — final audit (2026-06-24)

### study1_daily: 70 missing dates, all irreducible

Re-running `download_psp_both.py` over the full range confirmed: all 57 dates that
have a raw file in `File2_Raw/` were correctly parsed — the files exist but their
subject-line dates resolve to different calendar dates (NLDC occasionally published
duplicate-date reports, leaving the next date uncovered). These are source-level
gaps, not parser failures.

| Category | Count | Explanation |
|----------|-------|-------------|
| Source gaps — duplicate subject-line dates in NLDC reports | 57 | Concentrated in 2020 (COVID-era publishing irregularities). Permanent. |
| Confirmed unavailable from NLDC server | 20 | Mostly 15th/16th of month (public holidays). Permanent. |
| Edge / known | 3 | 2018-12-31 (no named file), 2025-05-22/23 (server down) |
| **Total** | **70** | All irreducible — dataset is as complete as possible |

Missing dates by year: 2019 (7), 2020 (46), 2021 (5), 2022 (9), 2025 (2), edge (3).
Recommend treating gaps with forward-fill or time-series-aware imputation at model time.

### study1_hourly: 1,680 hourly rows with NaN PSP features
These correspond to the 70 missing daily dates broadcast across 24 hours each.
Not a separate issue — downstream of study1_daily gaps.

### study2_scada: minor slot irregularities
2 stub rows (2024-11-20, 2025-04-01 — single-slot days) have been dropped.

| Slots/day | Days | Action |
|-----------|------|--------|
| 98 | 1 (2024-11-16) | Likely duplicate row — clip to 96 at model time |
| 95 | 5 | DST / file-truncation edge cases — acceptable |
| 63 | 1 (2025-10-02) | Severely truncated — **drop before training** |
| 96 | 567 | Normal |

### Fields
- Columns empty only in early years (`xb_*`, `ir_*`, `solar_hr_*`, `trans_godda_*`)
  are **schema onset** — those report sections/sheets did not exist before ~2023/2024. Correctly NaN before; not gaps.
- `max_demand_met_*` (2019-20) and `diversity_*` (2019) were genuine parse gaps — now fixed (+458 and +335 rows recovered respectively).

---

## 3. Spot-check log (Phase 0 verification, 2026-06-24)

8 dates checked across all eras, 44 field comparisons, **0 mismatches**.

| Date | Raw file | Era | Fields checked | Result |
|------|----------|-----|----------------|--------|
| 2019-03-15 | 16.03.19_NLDC_PSP.pdf | PDF | 5 | ✓ |
| 2020-06-07 | 07.06.20_NLDC_PSP.pdf | PDF | 5 | ✓ |
| 2021-03-22 | 22.03.21_NLDC_PSP.pdf | PDF | 5 | ✓ |
| 2022-08-11 | 11.08.22_NLDC_PSP.pdf | PDF | 5 | ✓ |
| 2023-02-18 | 18.02.23_NLDC_PSP.xls | XLS | 6 | ✓ |
| 2023-10-06 | 06.10.23_NLDC_PSP.xls | XLS | 6 | ✓ |
| 2024-01-02 | 02.01.24_NLDC_PSP.xls | XLS | 6 | ✓ |
| 2025-01-21 | 21.01.25_NLDC_PSP.xls | XLS | 6 | ✓ |

Fields verified per row: `peak_demand_met_total_mw`, `energy_met_total_mu`,
`gen_total_mu`, `freq_fvi`, `diversity_regional`, `outage_total_total_mw`,
`ir_wr_nr_net_mu` (where present).

---

## 4. Still unparsed in the raw files

| Source | Required by a study? | Decision |
|--------|----------------------|----------|
| MOP_E §C — per-state Power Supply Position (~40 entities) | Not in the current Study 1/2 feature set | Optional. If added later → flag ISTS rows and exclude from state→region totals |
| IR-Line `Max Import/Export (MW)` columns | No (we take MU + NET) | Optional, low value |
| `Time Of Maximum Demand Met` (daily) | No | file3 captures it; file1/file2 don't — add if peak-timing becomes a feature |
| Transnational "Day peak (MW)", Solar/Non-solar "Time" | No | Low value, skip |

---

## 5. Roadmap

### Phase 0 — Correct datasets ✅ COMPLETE
- [x] Parser fixes #1-#3, #5; IR-Line backport; dedup; date handling
- [x] Regenerate all three datasets
- [x] Re-run downloader — confirmed 70 gaps are all irreducible source absences
- [x] Spot-check 10 dates vs raw files — 44 checks, 0 mismatches
- [x] study1_hourly rebuilt with 21 IR cols (was 0)
- [x] study2_scada: 2 stub rows dropped, dates standardised to ISO

---

### Phase 1 — Feature tables ready for modelling

**Goal:** one command rebuilds everything; automated validation catches regressions.

#### 1a. `build_all.py` — single-command pipeline
- Calls each parser in order (File1 → f1_daily, File2 → study1_daily, File3 → study2_scada)
- Joins f1_daily + hourlyLoadDataIndia → study1_hourly
- Writes all outputs to `Dataset/`
- Prints row counts and null summary on completion

#### 1b. Validation gate
Run after every rebuild. Checks:

| Check | Threshold | Files |
|-------|-----------|-------|
| Row count vs expected | ±5 rows | all |
| Date continuity (no new gaps) | 0 new gaps vs baseline | study1_daily, study2_scada |
| Null % per column vs baseline | <2% increase | all |
| `xb_export_*` ≥ 0 | 0 violations | study1_daily |
| `xb_net_* = import - export` per country | abs diff < 0.01 | study1_daily |
| `ir_*_net = import - export` per corridor | abs diff < 0.01 | study1_daily |
| study2 slots/day = 96 | allow ≤10 days with 95/98 | study2_scada |
| study2_scada no 63-slot day | 0 | study2_scada |

#### 1c. Data dictionary
Spreadsheet: `Dataset/data_dictionary.xlsx`
Columns: `column_name`, `dataset`, `unit`, `source_section`, `schema_start_date`, `notes`
~144 columns for study1, ~165 for study2.

#### 1d. (Optional) Publish to Kaggle
Three CSVs + data dictionary + dataset card describing methodology.

---

### Phase 2 — Coverage expansion

- **Text-regex fallback** for generation/outage on ~27 merged-blob PDFs (last ~1% of rows missing those fields)
- **Optional:** §C state-level table → `study3_states.csv` (~40 state entities, daily)
- **Backfill:** 2025-05-22/23 if NLDC re-publishes; monitor for new gaps

---

### Phase 3 — Study 1: daily load forecasting

**Dataset:** `Dataset/study1_daily.csv` (2,660 rows × 144 cols) + optionally join hourly → aggregate to daily.

**Target variable:** `peak_demand_met_total_mw` or `energy_met_total_mu` (next-day forecast).

**Feature groups available:**
| Group | Columns | Notes |
|-------|---------|-------|
| Generation mix | `gen_coal_mu`, `gen_hydro_mu`, `gen_nuclear_mu`, `gen_res_mu`, `gen_gas_mu`, `gen_lignite_mu` | Daily totals |
| Outages | `outage_central_*_mw`, `outage_state_*_mw` per region | Planned + forced |
| IR-Line corridor flows | 21 `ir_*` cols (export/import/net per corridor) | Available from ~2023; NaN before |
| Cross-border exchange | 12 `xb_*` cols (Bhutan/Nepal/Bangladesh/Myanmar) | Available from ~2023 |
| Frequency | `freq_fvi`, `freq_pct_*` bands | Daily aggregates |
| Diversity | `diversity_regional`, `diversity_state` | Demand diversity factor |
| RES share | `share_res_pct`, `share_nonfossil_pct` | Daily % |
| Regional demand | `peak_demand_met_*_mw`, `energy_met_*_mu` per region (NR/WR/SR/ER/NER) | |

**What we can produce:**
- Next-day peak demand forecast (MW) — national + per region
- Next-day energy met forecast (MU)
- Feature importance ranking over generation mix / outages / IR-line / cross-border

**Modelling plan:**
1. Time-aware train/val/test split (e.g. 2019-2022 train, 2023 val, 2024-2026 test) — no leakage
2. Baseline: gradient boosting (XGBoost / LightGBM) with lag features (t-1, t-7, t-365)
3. Sequence model: LSTM or Temporal Fusion Transformer
4. Metrics: MAPE, RMSE, MAE on held-out test set

---

### Phase 4 — Study 2: 15-min frequency-violation classifier

**Dataset:** `Dataset/study2_scada.csv` (55,068 rows × 165 cols, 96 slots/day).

**Target variable:** binary — did a frequency violation occur in a given 15-min block?
- Violation definition to decide: `freq_hz` outside [49.7, 50.2] Hz band, OR
  use the pre-computed `freq_pct_below_497` / `freq_pct_above_5005` cols directly.

**Feature groups available:**
| Group | Columns | Notes |
|-------|---------|-------|
| Real-time generation mix | `nuclear_mw`, `wind_mw`, `solar_mw`, `hydro_mw`, `gas_mw`, `thermal_mw` | Per 15-min slot |
| Demand | `demand_met_mw`, `net_demand_met_mw`, `total_gen_mw` | Per slot |
| Net transmission | `net_trans_exchange_mw` | Per slot |
| Evening peak demand | Per region (NR/WR/SR/ER/NER) | Broadcast from daily |
| IR-Line corridor flows | 21 `ir_*` cols | Broadcast from daily MOP_E |
| Cross-border exchange | `xb_*` cols | Broadcast from daily |
| Frequency stats | `freq_hz`, `freq_fvi`, `freq_pct_*` bands | Per slot — **use carefully** (some are the target) |
| Time features | `hhmm`, time-of-day, day-of-week | Derived |

**What we can produce:**
- 15-min ahead frequency violation probability
- Feature importance: which generation source / corridor imbalance most predictive
- Risk heatmap: time-of-day × day-of-week violation frequency
- Threshold analysis: precision-recall at fixed recall (e.g. catch 90% of violations)

**Modelling plan:**
1. Define violation label per slot (threshold TBD — consult NLDC grid code: 49.7–50.2 Hz)
2. EDA: violation rate by hour, season, generation mix
3. Handle class imbalance: SMOTE or class-weighted loss
4. Time-aware split: 2024-11 to 2025-06 train, 2025-07 to 2025-12 val, 2026 test
5. Baseline: LightGBM with slot-level + lag-1 slot features
6. Sequence model: temporal CNN or LSTM over 96-slot daily window
7. Metrics: PR-AUC, recall at 95% precision, F1

---

## 6. Verification log

| Check | Raw | Output |
|-------|-----|--------|
| 2019-01-01 file (01.01.19) data date | subject says 31.12.2018 | 2018-12-31 ✓ |
| 2024-01-01 IR-Line ER-NR net | -94.85 | -94.85 ✓ |
| 2023-06-01 IR-Line cols | 21 | 21 ✓ |
| 2024 xb export/import/net Bhutan | 11.4 / 0.54 / -10.86 | matches ✓ |
| dedup keeps richest row | — | verified ✓ |
| concatenated + page-variance PDFs | non-empty | recovered ✓ |
| Spot-check 8 dates × 44 fields (2019-2025) | — | 0 mismatches ✓ |
| 70 missing dates investigated | all irreducible source gaps | confirmed ✓ |
| study1_hourly IR cols | 0 (old) | 21 (new) ✓ |
| study2_scada stub rows | 2 present | dropped ✓ |
| study2_scada date format | DD/MM/YYYY | ISO YYYY-MM-DD ✓ |
