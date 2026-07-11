# Notes: ML/Study2/features.py

**Script:** `ML/Study2/features.py`
**Purpose:** Shared feature-engineering module for Study 2 (corridor-aware frequency-violation + ramp-shock lead-time classifiers) — imported by all five notebooks in `ML/Study2/notebooks/` and `predict.py`, same pattern as Study 1's `features.py`.

> Documented here in `Pipeline/docs/` rather than an `ML/docs/` folder, same reasoning as `study1_features_notes.md` — one place for "how does a piece of this pipeline work."

---

## In plain English

Study 2 tries to answer, for every 15-minute slot of the day: "in the next 15-60 minutes, is the grid about to have a problem?" — either a frequency violation (the grid's electrical frequency drifting outside its safe band) or a ramp-shock (demand suddenly jumping or dropping sharply). This file turns the raw slot-by-slot SCADA data into the inputs a model needs to answer that: what just happened in the last few slots, how volatile recent solar generation has been, what time of day/year it is, and — as a bonus signal — how far off Study 1's demand forecast was that day (a forecast being unusually wrong is itself a warning sign). Corridor/cross-border flow and same-day RES share are computed here too, but as of 2026-07-11 are deliberately excluded from what the classifiers actually train on — see `DAILY_BROADCAST_COLS` below.

---

## The two targets

- **`violation_lead`** — 1 if `freq_hz` falls outside [49.7, 50.2] Hz in any of the next 1-4 slots (15-60 min ahead), 0 if it stays in-band for all 4, NaN if that window can't be determined yet (too close to the end of the available data).
- **`ramp_lead`** — same lead-time framing, but for whether `|demand_met_mw` slot-to-slot delta`| exceeds `RAMP_THRESHOLD_MW` (3,500 MW, ≈ the empirical 95th percentile of that delta across the whole archive) in any of the next 1-4 slots.

Both are "OR over the lookahead window" labels, not "will it happen in exactly slot N" — this matches how an early-warning system would actually be used (any warning in the next hour is actionable), and it's why their positive rate (violation_lead ≈2.4%, ramp_lead ≈15%) is higher than the raw per-slot event rate (0.89% / 6.1%) reported in `01_eda.ipynb`.

`add_violation_label()` and `build_feature_table()` both take a `lead_slots` / `violation_lead_slots` override (default 4, matching `LEAD_SLOTS`) — added 2026-07-11 so `03_violation_baseline.ipynb` could test shorter lead windows without disturbing the shipped default or the ramp-shock target. Re-run three times now, on three different feature sets, and the "best" window has moved every time (see that notebook's appendix for the full detail) — the instability itself is the finding; 4 remains the shipped default because no window has been shown *robustly* best, not because it's been confirmed as such.

---

## Solar-volatility features — added 2026-07-11

`solar_delta_mw` (slot-to-slot change in `solar_mw`) and `solar_roll8_std` (rolling std over the last 8 slots) were added to `add_slot_lag_features()` after the originally-planned two-stage ramp→violation idea was tested and falsified: `P(ramp_lead=1 | violation_lead=1)` = 14.2%, actually *below* the 15.1% unconditional rate, so a demand-side ramp does not meaningfully precede a violation in this data. Scanning every generation source's slot-to-slot delta for correlation with `violation_lead` instead found solar clearly ahead of the rest (corr 0.0785 vs. wind's 0.036, demand's ~0) — consistent with violations clustering at 08:00-09:00 and 13:00 (`01_eda.ipynb`), prime solar-ramp hours. Both features use the same contiguity guard as everything else in this file.

---

## `DAILY_BROADCAST_COLS` — corridor/RES-share removed from the classifiers, 2026-07-11

`share_res_pct` and all 11 `ir_*`/`xb_*` corridor columns turned out to be whole-DAY aggregates, broadcast identically to every one of a day's 96 slots (verified directly: every row of a given date has the exact same value for these columns, unlike `freq_hz`/`demand_met_mw` which genuinely vary per slot). That raised a real methodological question: does a whole-day RES-share/corridor figure leak information from *later* in the same day into a prediction for an *earlier* slot?

Tested rather than assumed. Retraining both classifiers with these 12 columns excluded **improved** both — `violation_lead` PR-AUC 0.0937 → 0.1186, `ramp_lead` PR-AUC 0.7248 → 0.7446. So there was no leakage-driven inflation to worry about; these columns were adding noise, not signal, once genuine per-slot features (frequency/demand lags, solar volatility, hour) are available. `FEATURE_COLS` no longer includes them. `CORRIDOR_COLS` and the new `DAILY_BROADCAST_COLS` (= `["share_res_pct"] + CORRIDOR_COLS`) are still defined and still used directly by `01_eda.ipynb`'s corridor-flow-quintile analysis and `00_era2_daily_correlation.ipynb` — that daily-resolution correlation work is a separate, valid analysis unaffected by this classifier-level result.

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

## `scale_pos_weight()` — kept, but no longer used

Both targets are rare-event (0.5-18% positive rate depending on split/target), and `scale_pos_weight` was the original plan for handling that — chosen over SMOTE (synthetic oversampling) because it doesn't require inventing synthetic frequency/demand values that don't correspond to real grid states, and tree boosting should handle class weighting natively.

**Found broken, 2026-07-11:** it caused LightGBM's early stopping to fire after a single boosting round (`best_iteration_=1`) for the `violation_lead` target specifically, in every configuration tested (extra regularization, `is_unbalance=True`, different learning rates) — effectively capping the model at close to one shallow tree instead of the intended up-to-500-round ensemble. Removing it entirely, and switching the early-stopping eval metric from the default `binary_logloss` to `average_precision`, raised `violation_lead`'s PR-AUC from 0.0614 to 0.0937 and gave a smaller but consistent gain on `ramp_lead` too (0.7140 → 0.7248). Neither `03_violation_baseline.ipynb`, `04_ramp_shock_baseline.ipynb`, nor `predict.py` call this function anymore. The function itself is kept, not deleted, as a documented cautionary reference — see its docstring for how to recognize this failure mode if a future rare-event target tempts someone to reach for it again (suspiciously tiny single-digit feature-importance split counts is the tell, not an obvious crash).

---

## Verified 2026-07-11

- `build_feature_table()` run against the full live `study2_scada.csv`: 56,923 rows (after dropping the 3 bad days), 184 columns, `violation_lead` rate 2.42%, `ramp_lead` rate 15.11%, only 23 rows of each with an unresolvable (NaN) label — all at the very end of the available data, as expected.
- Spot-checked the lead-label logic directly: for three known violation events, the four slots immediately preceding each one are correctly flagged `violation_lead = 1`.
- `build_study1_residual_signal()` reproduces the exact same LightGBM MAPE 0.0175 / naive MAPE 0.0242 result already verified for `03_baseline.ipynb` (same underlying procedure), confirming it isn't a divergent re-implementation.

---

## Usage

Not run standalone — imported by every notebook in `ML/Study2/notebooks/` and by `predict.py`. Depends on `pandas`, `numpy`, `lightgbm` (already in CI's pip install list).
