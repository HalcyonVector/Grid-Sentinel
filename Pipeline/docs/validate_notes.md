# Notes: validate.py

**Script:** `validate.py` (repo root)
**Purpose:** Post-build integrity check for all three Grid-Sentinel output datasets. Run this after every full or partial rebuild to confirm no regressions were introduced.

---

## When to run

Run after any call to `build_all.py` or `Scrapings/update_live.py`. Can also be run on demand to inspect the current state of the datasets without rebuilding them.

```
python validate.py              # check all three datasets
python validate.py --only study1
python validate.py --only study2
python validate.py --only hourly
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

### study1_hourly

| Check | Level if triggered | Threshold |
|-------|--------------------|-----------|
| Column count | FAIL | Must equal 151 |
| Row count | FAIL | Must be >= 46,728 |
| Latest datetime | Informational | Printed but not a FAIL condition |

---

## Baseline values

The baselines (minimum row counts, exact column counts) are hardcoded in the script. They reflect the dataset state as of 2026-07-01. As daily data accumulates, row counts will grow above these baselines. Column counts should remain fixed unless a parser is modified to add or remove fields.

If a parser change intentionally adds or removes columns, update `BASELINE_COLS` in `validate.py` to match.

---

## Checks not included

- Null percentage per column compared to a stored baseline. This would require a snapshot file and was deferred as the datasets are still growing.
- Date continuity check against the known 70-gap list. The gap list exists in the roadmap as prose but is not machine-readable. If that list is ever exported to a file, a continuity check can be added here.
- Cross-dataset consistency (e.g., confirming that study2_scada covers the same date range as study1_daily post-2024).

---

## Known col count discrepancy

The roadmap (Phase 0, written 2026-06-24) states study2_scada has 165 columns. The actual file has 164. The baseline in `validate.py` uses 164 (the observed count). If the discrepancy is traced to a missing column that should be restored, update both the parser and `BASELINE_COLS["study2_scada"]`.
