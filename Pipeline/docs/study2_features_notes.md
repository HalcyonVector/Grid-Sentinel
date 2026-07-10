# Notes: ML/Study2/features.py

**Script:** `ML/Study2/features.py`
**Purpose:** Shared feature-engineering module for Study 2 (corridor-aware frequency-violation + ramp-shock lead-time classifiers) — imported by all five notebooks in `ML/Study2/notebooks/` and `predict.py`, same pattern as Study 1's `features.py`.

> Documented here in `Pipeline/docs/` rather than an `ML/docs/` folder, same reasoning as `study1_features_notes.md` — one place for "how does a piece of this pipeline work."

---

## In plain English

Study 2 tries to answer, for every 15-minute slot of the day: "in the next 15-60 minutes, is the grid about to have a problem?" — either a frequency violation (the grid's electrical frequency drifting outside its safe band) or a ramp-shock (demand suddenly jumping or dropping sharply). This file turns the raw slot-by-slot SCADA data into the inputs a model needs to answer that: what just happened in the last few slots, what time of day/year it is, how much power is flowing between regions and across borders, and — as a bonus signal — how far off Study 1's demand forecast was that day (a forecast being unusually wrong is itself a warning sign).

---

## The two targets

- **`violation_lead`** — 1 if `freq_hz` falls outside [49.7, 50.2] Hz in any of the next 1-4 slots (15-60 min ahead), 0 if it stays in-band for all 4, NaN if that window can't be determined yet (too close to the end of the available data).
- **`ramp_lead`** — same lead-time framing, but for whether `|demand_met_mw` slot-to-slot delta`| exceeds `RAMP_THRESHOLD_MW` (3,500 MW, ≈ the empirical 95th percentile of that delta across the whole archive) in any of the next 1-4 slots.

Both are "OR over the lookahead window" labels, not "will it happen in exactly slot N" — this matches how an early-warning system would actually be used (any warning in the next hour is actionable), and it's why their positive rate (violation_lead ≈2.4%, ramp_lead ≈15%) is higher than the raw per-slot event rate (0.89% / 6.1%) reported in `01_eda.ipynb`.

---

## The contiguity guard — why this file doesn't just use `.shift()`

A plain `df[col].shift(-k)` silently bridges gaps: if a day was dropped (see `drop_bad_days()` below) or the archive is missing a date, `shift(-k)` pulls in whatever row happens to be `k` rows away in the table — which might be hours or days away in real time, not `k * 15` minutes away. That would make the "no event in the next 4 slots" label wrong (actually unknown) without ever raising an error.

Every lookahead/lookbehind computation in this file — the lead labels (`_add_lead_label`), the ramp delta (`add_ramp_label`), and the lag/rolling features (`add_slot_lag_features`) — checks the actual `datetime` gap to the row being referenced and only uses it if the gap is exactly what it should be (`k * 15` minutes). Otherwise the value is `NaN`, meaning "unknown," not "no event." Crossing a calendar-day boundary is fine and expected (the grid doesn't reset at midnight); crossing a real data gap is not.

---

## `drop_bad_days()` — which days get excluded and why

Days with fewer than 90 of the expected 96 slots are dropped entirely before any feature is computed. Verified 2026-07-11 against the live dataset: `2024-11-20` and `2025-04-01` have exactly 1 slot each, `2025-10-02` has 63 (already documented in the roadmap as a known bad day). These are corrupted source files, not real grid behavior — training on them (or worse, letting a lag/rolling feature silently reach across them) would teach the model on garbage. Slot counts of 95/97/98 are kept — those are real DST/rounding edge cases with enough data to be usable.

---

## `build_study1_residual_signal()` — reusing Study 1's model, not a stale CSV

Study 2's roadmap design treats "how wrong was yesterday's demand forecast" as a leading indicator of grid stress (Phase 3 → Phase 4 hand-off). The obvious source would be the live forecast log at `Dataset/predictions/study1_forecast.csv` — except that log only has real history going back to when `ML/Study1/predict.py` started running (2026-07-10), nowhere near enough to cover Study 2's Nov 2024-present training window.

Instead, this function re-runs Study 1's exact baseline procedure (train on ≤2022, validate on 2023, predict 2024+) from `ML/Study1/features.py`, loaded via `importlib` under the name `study1_features` rather than a plain `import features` — both Study 1 and Study 2 have a file literally named `features.py`, and a naive `sys.path.insert` + `import features` would silently return whichever one Python happened to import first instead of Study 1's. The resulting residual (`actual - forecast`) is available for every date in Study 1's 2024+ test window, which fully covers `study2_scada`'s date range.

This is a **single-cutoff backtest approximation**, not a reproduction of what `predict.py` would have output live on each historical day (that would mean walk-forward retraining once per day, which this function doesn't do) — but it's the same model and feature pipeline, computed fresh every time rather than depending on a hand-generated, potentially stale CSV.

---

## `scale_pos_weight()` — why not SMOTE

Both targets are rare-event (0.5-18% positive rate depending on split/target). LightGBM's `scale_pos_weight` handles this natively by reweighting the loss function — chosen over SMOTE (synthetic oversampling) because it doesn't require inventing synthetic frequency/demand values that don't correspond to real grid states, and tree boosting handles class weighting well without it.

---

## Verified 2026-07-11

- `build_feature_table()` run against the full live `study2_scada.csv`: 56,923 rows (after dropping the 3 bad days), 184 columns, `violation_lead` rate 2.42%, `ramp_lead` rate 15.11%, only 23 rows of each with an unresolvable (NaN) label — all at the very end of the available data, as expected.
- Spot-checked the lead-label logic directly: for three known violation events, the four slots immediately preceding each one are correctly flagged `violation_lead = 1`.
- `build_study1_residual_signal()` reproduces the exact same LightGBM MAPE 0.0175 / naive MAPE 0.0242 result already verified for `03_baseline.ipynb` (same underlying procedure), confirming it isn't a divergent re-implementation.

---

## Usage

Not run standalone — imported by every notebook in `ML/Study2/notebooks/` and by `predict.py`. Depends on `pandas`, `numpy`, `lightgbm` (already in CI's pip install list).
