# Grid-Sentinel

A machine learning project for predicting and detecting stress on the Indian power grid, built entirely on NLDC (National Load Despatch Centre) daily Power System Position (PSP) reports scraped from the NLDC/Grid-India CDN.

> **Live dashboard:** [grid-sentinel-vm.vercel.app](https://grid-sentinel-vm.vercel.app/)

---

## What this project does

Seven years of daily grid reports (PDF up to ~2023, XLS from 2023 onward) are scraped, parsed, and cleaned into four public datasets covering three complementary resolutions: daily, hourly, and 15-minute SCADA. Two LightGBM models are trained on top of that data and retrained daily: a next-day demand forecast and a 15-minute frequency-violation/ramp-shock risk classifier. Both feed a live dashboard alongside a historical explorer built around the project's three-era research design.

**Central research question:** as India's grid monitoring granularity and renewable penetration have both increased 2019 to 2026, how has the observability and predictability of grid stress (demand ramps, frequency deviations) evolved, and once corridor/cross-border visibility exists in the data, do inter-regional congestion and cross-border exchange meaningfully predict short-term grid stress?

Answered across three eras, each using the dataset that actually covers it:

| Era | Window | Dataset(s) | What it answers |
|---|---|---|---|
| **1 — Pre-corridor** | 2019-2022 | `study1_daily` + `study1_hourly` | Intra-day ramp characteristics and RES-share growth trend |
| **2 — Corridor-visible** | 2023-Oct 2024 | `study1_daily` | Does corridor congestion / cross-border exchange correlate with daily frequency-band stress? |
| **3 — Live SCADA** | Nov 2024-present | `study2_scada` | 15-minute-resolution violation and ramp-shock risk, with corridor-aware lead-time classification |

---

## Findings

- **Season-controlled evidence that rising RES share correlates with increased grid stress at 15-minute resolution** once SCADA-resolution visibility exists (Nov 2024 onward) — the first granular result of its kind for the Indian grid, complementing macro-level policy findings rather than just restating them.
- **Inter-regional corridor flow acts as a stress-relief signal, not a stress-causing one** — a moderate negative correlation with next-day frequency instability.
- **Grid stress has a genuine day-of-week decoupling**: Sunday has the week's highest frequency-violation rate but its lowest ramp-shock rate, consistent with thinner online reserve margins on a low-demand day.
- **Ramp-shock classifier is strong** (PR-AUC 0.746 vs. 0.177 base rate, ~4.2x lift); **frequency-violation classifier is real but modest** (PR-AUC 0.154 vs. 0.031 base rate, ~5.0x lift). The gap between the two is itself evidence they are mechanistically different phenomena, not two flavors of the same thing.
- **A demand-side hypothesis was tested and falsified rather than assumed**: ramp-shocks do not precede frequency violations more than chance, reported as a documented dead end, not hidden.

All headline numbers are reported honestly, including a threshold-selection methodology bug (found and fixed) that had inflated several operating-point metrics. See [ROADMAP.md](ROADMAP.md) for the full history and corrected figures.

---

## Datasets

Four CSVs, auto-updated daily via GitHub Actions and published on Kaggle:

| File | Rows | Cols | Date range | Granularity |
|------|------|------|------------|-------------|
| `study1_daily.csv` | 2,680+ | 144 | Dec 2018 → present | 1 row per day |
| `study1_hourly.csv` | 46,728 | 151 | Jan 2019 → Apr 2024 | 1 row per hour |
| `study2_scada.csv` | 57,000+ | 164 | Nov 2024 → present | 1 row per 15-min block |
| `study3_states.csv` | 99,000+ | 10 | Dec 2018 → present | 1 row per state/UT/entity per day |

Row counts grow daily and should be treated as a snapshot, not a live figure. Full column-level documentation, known gaps, and licensing live in [Dataset/README.md](Dataset/README.md).

**Public Kaggle mirror:** [halcyonvector/india-power-grid-nldc-daily-psp-reports](https://www.kaggle.com/datasets/halcyonvector/india-power-grid-nldc-daily-psp-reports)

---

## Models

| Study | Target | Model | Result |
|-------|--------|-------|--------|
| **Study 1 — Daily load forecasting** | Next-day peak demand (MW) / energy met (MU) | LightGBM, retrained daily | See `ML/Study1/notebooks/03_baseline.ipynb` |
| **Study 2 — Frequency-violation classifier** | Binary: frequency violation in a 15-min slot? | LightGBM, retrained daily | PR-AUC 0.154 vs. 0.031 base rate |
| **Study 2 — Ramp-shock classifier** | Binary: sudden demand/generation swing in a 15-min slot? | LightGBM, retrained daily | PR-AUC 0.746 vs. 0.177 base rate |

Both classifiers retrain from scratch on every CI run (training takes seconds at this dataset size), output daily 96-slot risk timelines, and are wired into the same GitHub Actions pipeline that scrapes and publishes the data.

---

## Repository structure

```
Grid-Sentinel/
├── Dataset/            Output CSVs + Kaggle metadata (auto-updated daily by CI)
├── ML/                  Modelling work: Study1/ (daily forecast), Study2/ (violation + ramp-shock)
├── Pipeline/            Build, validate, and data-dictionary scripts, plus docs/ notes per script
├── Reference/           External source data (hourly load dataset from Kaggle)
├── Scrapings/           Parsers and download scripts for the NLDC/Grid-India CDN
├── dashboard/           React + Vite + Tailwind + Recharts dashboard, deployed on Vercel
├── .github/workflows/   daily_scrape.yml — CI pipeline (scrape, build, train, publish)
└── ROADMAP.md           Full project history, phase-by-phase, kept current as work lands
```

---

## Tech stack

| Layer | Technology |
|-------|-----------|
| Scraping & parsing | Python (`pdfplumber`, `pandas`, `requests`) |
| Modelling | LightGBM, scikit-learn, notebooks developed on Google Colab |
| Data pipeline & CI | GitHub Actions, daily scrape → build → validate → train → publish |
| Dashboard | React 19 + Vite + Tailwind CSS + Recharts, deployed on Vercel |
| Dataset distribution | Kaggle (auto-pushed daily via `kaggle datasets version`) |

---

## Quick start

```bash
# Full dataset rebuild (all four datasets)
python Pipeline/build_all.py

# Validate after any rebuild
python Pipeline/validate.py

# Run the dashboard locally
cd dashboard
npm install
npm run dev
```

See [ROADMAP.md](ROADMAP.md) for the full build/validate command reference and [dashboard/README.md](dashboard/README.md) for dashboard-specific setup and deployment steps.

---

## Known limitations

- `study1_daily` / `study1_hourly` have 69 individually-root-caused missing dates (mostly duplicate NLDC republishes during the 2020 COVID era, plus a handful of genuine archive gaps) — source-level absences, not parser failures.
- `study2_scada` has 17 dates with no rows (PDF-only source days, which cannot contain 15-minute SCADA data) and 3 severely corrupted days dropped before training.
- IR-Line and cross-border columns are only available from ~2023 onward, when NLDC began publishing that section.
- The frequency-violation classifier is a real but modest baseline (PR-AUC 0.154), reported honestly rather than oversold.

Full detail, including per-date root causes, lives in [Dataset/README.md](Dataset/README.md) and [ROADMAP.md](ROADMAP.md).

---

## Authors

**Sagnik** [@HalcyonVector](https://github.com/HalcyonVector)

**Abhirami** [@menaegerie](https://github.com/menaegerie)

---

## License

Code is MIT licensed — see [LICENSE](./LICENSE). The published dataset is CC BY-SA 4.0 — see [Dataset/README.md](Dataset/README.md#license) for the dataset-specific terms.
