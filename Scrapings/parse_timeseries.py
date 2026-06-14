"""
Parser for the 'TimeSeries' sheet of Grid-India Daily PSP Report XLS files.

Handles two known column-layout variants:
  - 13-column "pre-storage" format (seen from ~Nov 2024)
  - 16-column "with BESS/storage" format (seen by mid-2026)

Standardizes both into one schema:
  timestamp, frequency_hz, demand_met_mw, net_demand_met_mw,
  nuclear_mw, wind_mw, solar_mw, hydro_mw, gas_mw, thermal_mw, others_mw,
  storage_demand_mw, storage_gen_mw, total_generation_mw,
  net_transnational_exchange_mw, vre_mw, vre_ratio
"""

import re
import pandas as pd
from datetime import datetime, timedelta, time as dtime


# Keyword -> standard column name. Order matters: more specific first.
KEYWORD_MAP = [
    (r"^TIME$", "time_str"),
    (r"FREQUENCY", "frequency_hz"),
    (r"STORAGE\s*DEMAND", "storage_demand_mw"),
    (r"^DEMAND\s*MET", "demand_met_mw"),          # avoid matching NET DEMAND MET
    (r"NET\s*DEMAND\s*MET", "net_demand_met_mw"),
    (r"NUCLEAR", "nuclear_mw"),
    (r"WIND", "wind_mw"),
    (r"SOLAR", "solar_mw"),
    (r"HYDRO", "hydro_mw"),
    (r"GAS", "gas_mw"),
    (r"THERMAL", "thermal_mw"),
    (r"^STORAGE", "storage_gen_mw"),               # generic STORAGE (gen) col
    (r"OTHERS", "others_mw"),
    (r"TOTAL\s*GENERATION", "total_generation_mw"),
    (r"NET\s*TRANSNATIONAL", "net_transnational_exchange_mw"),
]


def _clean_header(raw):
    if raw is None or (isinstance(raw, float) and pd.isna(raw)):
        return ""
    s = str(raw)
    s = s.replace("\n", " ")
    s = re.sub(r"[¹²³*]", "", s)          # strip footnote markers
    s = re.sub(r"\s+", " ", s).strip()
    return s.upper()


def _map_header(header_cells):
    """Map a list of raw header strings to standardized column names."""
    cleaned = [_clean_header(c) for c in header_cells]
    mapped = [None] * len(cleaned)

    # First pass: NET DEMAND MET and DEMAND MET need careful ordering
    for i, h in enumerate(cleaned):
        if "NET DEMAND MET" in h:
            mapped[i] = "net_demand_met_mw"
        elif "TOTAL GENERATION" in h:
            mapped[i] = "total_generation_mw"
        elif "EXCHANGE" in h and "TRANS" in h:
            mapped[i] = "net_transnational_exchange_mw"
        elif "STORAGE DEMAND" in h:
            mapped[i] = "storage_demand_mw"
        elif h == "DEMAND MET (MW)" or h.startswith("DEMAND MET"):
            mapped[i] = "demand_met_mw"
        elif "FREQUENCY" in h:
            mapped[i] = "frequency_hz"
        elif "NUCLEAR" in h:
            mapped[i] = "nuclear_mw"
        elif "WIND" in h:
            mapped[i] = "wind_mw"
        elif "SOLAR" in h:
            mapped[i] = "solar_mw"
        elif "HYDRO" in h:
            mapped[i] = "hydro_mw"
        elif "GAS" in h:
            mapped[i] = "gas_mw"
        elif "THERMAL" in h:
            mapped[i] = "thermal_mw"
        elif h.startswith("STORAGE"):
            mapped[i] = "storage_gen_mw"
        elif "OTHERS" in h:
            mapped[i] = "others_mw"
        elif h == "TIME":
            mapped[i] = "time_str"

    return mapped


def _find_report_date(df):
    """Search the first few rows for a date like '22-Mar-2025'."""
    date_pattern = re.compile(r"\d{1,2}-[A-Za-z]{3}-\d{4}")
    for i in range(min(3, len(df))):
        for val in df.iloc[i].tolist():
            if isinstance(val, str) and date_pattern.match(val.strip()):
                return datetime.strptime(val.strip(), "%d-%b-%Y").date()
            # sometimes pandas reads it as a Timestamp already
            if isinstance(val, pd.Timestamp):
                return val.date()
    return None


def parse_timeseries(filepath, sheet_name="TimeSeries"):
    """Parse the TimeSeries sheet of a Grid-India PSP xls file into a tidy dataframe."""
    raw = pd.read_excel(filepath, sheet_name=sheet_name, header=None)

    report_date = _find_report_date(raw)
    if report_date is None:
        raise ValueError(f"Could not find report date in {filepath}")

    # Locate header row (the one whose first cell is exactly 'TIME')
    header_row_idx = None
    for i in range(len(raw)):
        first_cell = _clean_header(raw.iloc[i, 0])
        if first_cell == "TIME":
            header_row_idx = i
            break
    if header_row_idx is None:
        raise ValueError(f"Could not find TIME header row in {filepath}")

    header_cells = raw.iloc[header_row_idx].tolist()
    col_map = _map_header(header_cells)

    # Data rows: start right after the (A)(B)(C)... annotation row
    data_start = header_row_idx + 2
    data = raw.iloc[data_start:].copy()
    data.columns = range(data.shape[1])

    # Keep only rows where time_str column looks like a time value:
    # accepted: "H:MM", "H:MM:SS" strings, or datetime.time objects
    time_col_idx = col_map.index("time_str")
    time_pattern = re.compile(r"^\d{1,2}:\d{2}(:\d{2})?$")

    def is_time_row(val):
        if isinstance(val, dtime):
            return True
        if isinstance(val, str):
            return bool(time_pattern.match(val.strip()))
        return False

    data = data[data[time_col_idx].apply(is_time_row)].reset_index(drop=True)

    # Build standardized output dataframe
    out = pd.DataFrame()
    for i, colname in enumerate(col_map):
        if colname is None:
            continue
        if colname in out.columns:
            # duplicate mapping (shouldn't normally happen) - skip
            continue
        out[colname] = data[i].values

    # Fill missing optional columns with 0 (storage cols absent in 13-col format)
    for opt_col in ["storage_demand_mw", "storage_gen_mw"]:
        if opt_col not in out.columns:
            out[opt_col] = 0

    # Build proper timestamp
    def to_timestamp(t):
        if isinstance(t, dtime):
            h, m = t.hour, t.minute
        else:
            parts = t.strip().split(":")
            h, m = int(parts[0]), int(parts[1])
        return datetime.combine(report_date, datetime.min.time()) + timedelta(hours=h, minutes=m)

    out["timestamp"] = out["time_str"].apply(to_timestamp)
    out = out.drop(columns=["time_str"])

    # Derived features
    out["vre_mw"] = out["wind_mw"] + out["solar_mw"]
    out["vre_ratio"] = out["vre_mw"] / out["total_generation_mw"].replace(0, pd.NA)

    # Order columns nicely
    ordered = [
        "timestamp", "frequency_hz", "demand_met_mw", "net_demand_met_mw",
        "nuclear_mw", "wind_mw", "solar_mw", "hydro_mw", "gas_mw", "thermal_mw",
        "others_mw", "storage_demand_mw", "storage_gen_mw",
        "total_generation_mw", "net_transnational_exchange_mw",
        "vre_mw", "vre_ratio",
    ]
    out = out[[c for c in ordered if c in out.columns]]

    # numeric coercion
    for c in out.columns:
        if c != "timestamp":
            out[c] = pd.to_numeric(out[c], errors="coerce")

    return out


if __name__ == "__main__":
    import sys
    fp = sys.argv[1]
    df = parse_timeseries(fp)
    print(df.head())
    print(df.tail())
    print(df.shape)
    print(df.dtypes)
