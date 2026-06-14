import sys
import glob
import pandas as pd
from pathlib import Path
from parse_timeseries import parse_timeseries


def build_dataset(input_dir):
    files = sorted(glob.glob(str(Path(input_dir) / "*.xls")))
    frames = []
    skipped = []

    for f in files:
        try:
            xls = pd.ExcelFile(f)
            if "TimeSeries" not in xls.sheet_names:
                skipped.append((f, "no TimeSeries sheet"))
                continue
            df = parse_timeseries(f)
            df["source_file"] = Path(f).name
            frames.append(df)
        except Exception as e:
            skipped.append((f, str(e)))

    if not frames:
        raise RuntimeError("No usable files found.")

    data = pd.concat(frames, ignore_index=True)
    data = data.sort_values("timestamp").drop_duplicates(subset="timestamp").reset_index(drop=True)

    print(f"Loaded {len(frames)} days, skipped {len(skipped)} files.")
    if skipped:
        for f, reason in skipped[:10]:
            print("  skipped:", Path(f).name, "-", reason)

    return data


def add_features_and_labels(data):
    data = data.copy()

    # --- Time-based features ---
    data["hour"] = data["timestamp"].dt.hour
    data["block_of_day"] = data["timestamp"].dt.hour * 4 + data["timestamp"].dt.minute // 15
    data["day_of_week"] = data["timestamp"].dt.dayofweek
    data["month"] = data["timestamp"].dt.month

    # --- Lag / momentum features (15-min, 1hr, 24hr) ---
    for lag, label in [(1, "15min"), (4, "1hr"), (96, "24hr")]:
        data[f"demand_lag_{label}"] = data["net_demand_met_mw"].shift(lag)
        data[f"freq_lag_{label}"] = data["frequency_hz"].shift(lag)
        data[f"vre_ratio_lag_{label}"] = data["vre_ratio"].shift(lag)

    # --- Rolling stats (1hr = 4 blocks, 3hr = 12 blocks) ---
    for window, label in [(4, "1hr"), (12, "3hr")]:
        data[f"demand_roll_mean_{label}"] = data["net_demand_met_mw"].rolling(window).mean()
        data[f"demand_roll_std_{label}"] = data["net_demand_met_mw"].rolling(window).std()
        data[f"vre_roll_mean_{label}"] = data["vre_ratio"].rolling(window).mean()

    # --- Ramp rate over 1hr (Condition B input) ---
    data["net_load_ramp_1hr"] = data["net_demand_met_mw"].diff(4)

    # --- Label Condition A: frequency violation ---
    data["label_freq_violation"] = (data["frequency_hz"] < 49.90).astype(int)

    # --- Label Condition B: ramp shock (95th percentile of |ramp|, computed on this data) ---
    ramp_abs = data["net_load_ramp_1hr"].abs()
    p95 = ramp_abs.quantile(0.95)
    data["label_ramp_shock"] = (ramp_abs > p95).astype(int)
    print(f"95th percentile of |1hr ramp|: {p95:.1f} MW")

    # --- Combined label ---
    data["label_stressed"] = (
        (data["label_freq_violation"] == 1) | (data["label_ramp_shock"] == 1)
    ).astype(int)

    return data


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python build_dataset.py INPUT_DIR OUTPUT_CSV")
        sys.exit(1)

    input_dir, output_csv = sys.argv[1], sys.argv[2]

    raw = build_dataset(input_dir)
    full = add_features_and_labels(raw)

    full.to_csv(output_csv, index=False)
    print(f"\nSaved {len(full)} rows to {output_csv}")
    print("\nLabel distribution:")
    print(full[["label_freq_violation", "label_ramp_shock", "label_stressed"]].mean())
