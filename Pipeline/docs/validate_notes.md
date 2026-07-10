# Notes: validate.py

**Script:** `Pipeline/validate.py`
**Purpose:** Post-build integrity check for all four Grid-Sentinel output datasets. Run this after every full or partial rebuild to confirm no regressions were introduced.

---

## In plain English

After the datasets get rebuilt or updated, how do we know nothing broke? This script is the checkup. It looks for obvious red flags — a missing day, the same date appearing twice, numbers that should add up but don't, a value that's physically impossible — and gives a clear pass/warning/fail report. If it fails, the data shouldn't be trusted or published until the problem is fixed.

---

## When to run

Run after any call to `build_all.py` or `Scrapings/update_live.py`. Can also be run on demand to inspect the current state of the datasets without rebuilding them.

```
python Pipeline/validate.py              # check all four datasets
python Pipeline/validate.py --only study1
python Pipeline/validate.py --only study2
python Pipeline/validate.py --only study3
python Pipeline/validate.py --only hourly
```

Exit code 0 means no FAILs. Exit code 1 means at least one check failed.

---

## Check severity levels

| Level | Meaning |
|-------|---------|
| PASS | Check passed within expected bounds. |
| WARN | Something is unusual but not necessarily broken. Investigate if unexpected. |
| FAIL | A structural problem that indicates a parser regression or corrupted output. Datasets should not be used until resolved. |

---

## Checks run per dataset

### study1_daily

| Check | Level if triggered | Threshold |
|-------|--------------------|-----------|
| Column count | FAIL | Must equal 144 |
| Row count | FAIL | Must be >= 2,660 |
| Duplicate dates | FAIL | Zero allowed |
| Data freshness | WARN | Latest date must be within 5 days of today |
| `xb_export_*` non-negative | WARN | All four country export columns must be >= 0 |
| `xb_net = import - export` | WARN | Absolute difference <= 0.01 MU for all rows |
| `ir_*_net = import - export` | WARN | Absolute difference <= 0.01 MU for all rows, all 7 corridors |

The 7 IR corridors checked are: ER-NR, ER-WR, ER-SR, ER-NER, NER-NR, WR-NR, WR-SR.

### study2_scada

| Check | Level if triggered | Threshold |
|-------|--------------------|-----------|
| Column count | FAIL | Must equal 164 |
| Row count | FAIL | Must be >= 55,068 |
| Duplicate (date, hhmm) pairs | FAIL | Zero allowed |
| Data freshness | WARN | Latest date must be within 5 days of today |
| 63-slot days | FAIL | Zero allowed (these indicate a legacy parse error) |
| Days outside 95-98 slots | FAIL if > 10 days, WARN if <= 10 | Each day should have 96 fifteen-minute slots |
| Days not exactly 96 slots | WARN | Informational count only |
| `freq_hz` range | WARN | Values must be within [47, 52] Hz |

### study3_states

| Check | Level if triggered | Threshold |
|-------|--------------------|-----------|
| Column count | FAIL | Must equal 10 |
| Row count | FAIL | Must be >= 99,000 |
| Duplicate (date, state) pairs | FAIL | Zero allowed |
| Data freshness | WARN | Latest date must be within 5 days of today |
| Every row has a valid region | FAIL | `region` must be non-null and one of NR/WR/SR/ER/NER — a null here means `parse_psp_states.py`'s `STATE_TO_REGION` map is missing an entity, see its notes file |
| Consistent state count per day | WARN | Flags any day with more than 3 fewer states than the typical (mode) count — usually means that date's section C table wasn't fully parsed |

### study1_hourly

| Check | Level if triggered | Threshold |
|-------|--------------------|-----------|
| Column count | FAIL | Must equal 151 |
| Row count | FAIL | Must be >= 46,728 |
| Latest datetime | Informational | Printed but not a FAIL condition |

---

## Baseline values

The baselines (minimum row counts, exact column counts) are hardcoded in the script. They reflect the dataset state as of 2026-07-01 for the original three datasets, and 2026-07-10 for `study3_states` (added that day). As daily data accumulates, row counts will grow above these baselines. Column counts should remain fixed unless a parser is modified to add or remove fields.

If a parser change intentionally adds or removes columns, update `BASELINE_COLS` in `validate.py` to match.

---

## Checks not included

- Null percentage per column compared to a stored baseline. This would require a snapshot file and was deferred as the datasets are still growing.
- Date continuity check against the known 70-gap list. The gap list exists in the roadmap as prose but is not machine-readable. If that list is ever exported to a file, a continuity check can be added here.
- Cross-dataset consistency (e.g., confirming that study2_scada covers the same date range as study1_daily post-2024).

---

## Col count discrepancy — resolved 2026-07-10

Earlier roadmap prose (Phase 0, 2026-06-24) stated study2_scada has 165 columns while the actual file has 164; this note used to flag it as untraced. Resolved by direct column diff: `study2_scada` = all 144 `study1_daily` columns (verified present, none missing) + exactly 20 real-time-only columns (`time`, `hhmm`, `freq_hz`, `demand_met_mw`, per-source real-time generation, `net_demand_met_mw`, `total_gen_mw`, `net_trans_exchange_mw`, 6 `time_max_demand_met_*` columns) = 164 exactly. The "165" was a stale pre-build estimate, not a missing column — no action needed.

---

## Adversarial audit, 2026-07-10

Beyond running this script, the full pipeline was independently re-verified by re-deriving evidence rather than trusting prior documentation: 74 field-by-field checks against raw PDF/XLS source across 2 dates not covered by the original spot-check log (0 mismatches), 2 new confirmed-irreducible gap dates found while doing so, a real duplicate-date case traced and confirmed harmless, and all three `update_live.py` append functions independently tested by removing a date and re-appending. See `ROADMAP.md`'s "Audit: Phase 0-1 re-verification" section for the full account, including the one real bug this pass found (`build_data_dict.py` silently missing `study3_states`, since fixed).
