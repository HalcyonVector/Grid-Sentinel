# Notes: build_data_dict.py

**Script:** `build_data_dict.py` (repo root)
**Purpose:** Generate `Dataset/data_dictionary.xlsx`, a human-readable reference for all columns across the three Grid-Sentinel datasets.

---

## Output

`Dataset/data_dictionary.xlsx` with four sheets:

| Sheet | Contents |
|-------|----------|
| `study1_daily` | All 144 columns from `study1_daily.csv` |
| `study2_scada` | All 164 columns from `study2_scada.csv` |
| `study1_hourly` | All 151 columns from `study1_hourly.csv` |
| `master` | Union of all unique column names across the three datasets |

Each sheet has the following fields:

| Field | Description |
|-------|-------------|
| `column_name` | Exact column name as it appears in the CSV |
| `datasets` | Which CSV files contain this column |
| `unit` | Physical unit (MW, MU, %, Hz, ratio, or date) |
| `source_section` | Section of the PSP report or external source this column is parsed from |
| `schema_start_date` | Approximate date from which this column has non-null values in the dataset |
| `notes` | Additional context, derivation formula, or caveats |

---

## Unit conventions

| Abbreviation | Full form | Notes |
|---|---|---|
| MW | Megawatt | Instantaneous demand or capacity |
| MU | Million Units | 1 MU = 1 GWh = 1,000 MWh. Used for energy (generation, consumption, exchange). |
| % | Percentage | Frequency band percentages, RES share, diversity factors expressed as ratios are noted separately. |
| Hz | Hertz | Instantaneous system frequency (study2_scada only) |
| ratio | Dimensionless | Demand diversity factors |

---

## Source sections

Columns are parsed from the following sections of the NLDC PSP report:

| Section label | Location in PSP report |
|---|---|
| Section A (National Overview) | Page 1: daily demand, shortage, peak, regional generation by source |
| Section B (Inter-Regional) | Page 2: national generation mix, frequency stats, outages, IE schedule/actual/ODUD |
| IR-Line table (Section B appendix) | Appears as a separate table or XLS sheet. Inter-regional corridor flows. |
| Cross-border table (Section B appendix) | Cross-border exchange with Bhutan, Nepal, Bangladesh, Myanmar. |
| TimeSeries sheet (SCADA) | XLS sheet present from FY2025 onward. Contains 15-minute slot data for study2_scada. |
| Kaggle India Hourly Load dataset | External source joined in step 4 of `build_all.py`. Provides hourly load figures 2019 to 2024. |

---

## Schema start dates

Many columns are structurally present from the beginning of the dataset (2018-12-31) but contain null values in older files where that section was not yet part of the PSP format. The `schema_start_date` field records the approximate date from which values should be non-null in normal circumstances.

Key thresholds:

| Date | What changed |
|------|-------------|
| 2018-12-31 | First PSP file in the dataset. All Section A and B core columns are available from this date, though some may be null due to format variations. |
| 2023-04-01 | IR-Line corridor flows and restructured cross-border (xb_*) columns begin appearing. Earlier files have these columns but with null values. |
| 2023-04-01 | Solar and non-solar peak-hour statistics (solar_hr_peak_mw etc.) and the Godda Bangladesh export column begin. |
| 2024-11-04 | First date in study2_scada. All slot-level SCADA columns begin here. |

---

## How domain knowledge is populated

The script hardcodes a `KNOWN` dictionary mapping each column name to its unit, source section, schema start date, and notes. For columns not in `KNOWN`, the script infers the unit from the column name suffix (`_mw`, `_mu`, `_pct`, `_hz`) and leaves other fields blank.

As of 2026-07-01, all 144 study1_daily columns and all 164 study2_scada columns have been populated with at least unit and source section. The remaining blank `notes` fields in the master sheet are for columns that are shared across datasets and carry the same annotation in their per-dataset sheet.

---

## Extending the dictionary

To add or correct an annotation, edit the `_add(...)` calls in `build_data_dict.py` and re-run the script. The xlsx is regenerated from scratch on each run; do not edit the xlsx directly.

If a new column is added to a parser, add a corresponding `_add(...)` call. If no `_add` entry exists, the column will appear in the xlsx with unit inferred from the name suffix and all other fields blank.

---

## Usage

```
python build_data_dict.py
python build_data_dict.py --output path/to/custom.xlsx
```

Requires `pandas` and `openpyxl`. Both are installed as part of the standard project dependencies (`pip install pandas openpyxl`).
