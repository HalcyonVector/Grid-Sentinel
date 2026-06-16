"""
Parser for Grid-India / POSOCO Daily PSP Report PDFs (2019–2022 era).

Fixed for the 2019 format where:
  - Date lives on page 2 in "Date of Reporting 1-Jan-19"
  - Page 2 has 9 tables; their fixed indices are:
      Table 0  – giant blob (skip for structured parsing)
      Table 1  – regional demand summary  (NR/WR/SR/ER/NER/Total)
      Table 2  – frequency profile
      Table 3  – transnational exchanges
      Table 4  – regional import/export
      Table 5  – generation outage
      Table 6  – sourcewise generation
      Table 7  – RES / non-fossil shares
      Table 8  – diversity factor

Usage:
    python parse_pdf_psp.py /path/to/pdf_folder/ output_daily.csv
    python parse_pdf_psp.py single_file.pdf
"""

import re
import sys
import glob
from pathlib import Path
from datetime import datetime

import pdfplumber
import pandas as pd


REGIONS = ["NR", "WR", "SR", "ER", "NER"]


def _to_float(val):
    if val is None:
        return None
    s = str(val).strip().replace(",", "").replace("----------", "")
    try:
        return float(s)
    except ValueError:
        return None


# ── Date extraction ──────────────────────────────────────────────────────────

def _extract_date(pdf):
    """
    Extract report date from page 2 header line:
      "Report for previous day   Date of Reporting  1-Jan-19"
    Falls back to page 1 if needed.
    """
    # Primary: page 2 header — most reliable
    text2 = (pdf.pages[1].extract_text() or "") if len(pdf.pages) > 1 else ""
    m = re.search(r"Date of Reporting\s+(\d{1,2}[-\s]\w{3}[-\s]\d{2,4})", text2)
    if m:
        raw = m.group(1).strip()
        for fmt in ["%d-%b-%y", "%d-%b-%Y", "%d %b %y", "%d %b %Y"]:
            try:
                return datetime.strptime(raw, fmt).date()
            except ValueError:
                continue

    # Fallback: bare date pattern on page 2 e.g. "1-Jan-19"
    m = re.search(r"\b(\d{1,2}-\w{3}-\d{2,4})\b", text2)
    if m:
        raw = m.group(1)
        for fmt in ["%d-%b-%y", "%d-%b-%Y"]:
            try:
                return datetime.strptime(raw, fmt).date()
            except ValueError:
                continue

    # Last resort: page 1
    text1 = pdf.pages[0].extract_text() or ""
    m = re.search(r"\b(\d{1,2}-\w{3}-\d{2,4})\b", text1)
    if m:
        raw = m.group(1)
        for fmt in ["%d-%b-%y", "%d-%b-%Y"]:
            try:
                return datetime.strptime(raw, fmt).date()
            except ValueError:
                continue

    return None


# ── Section parsers ──────────────────────────────────────────────────────────

def _parse_regional_summary(tables):
    """
    Table 1: regional demand summary.
    Header row: ['', 'NR', 'WR', 'SR', 'ER', 'NER', 'Total']
    """
    result = {}
    target = None
    for t in tables:
        if not t or len(t) < 2:
            continue
        headers = [str(c or "").strip() for c in t[0]]
        if "NR" in headers and "WR" in headers:
            target = t
            break
    if target is None:
        return result

    headers = [str(c or "").strip() for c in target[0]]
    col_idx = {}
    for r in REGIONS + ["Total", "TOTAL"]:
        if r in headers:
            col_idx[r] = headers.index(r)

    for row in target[1:]:
        if not row or row[0] is None:
            continue
        label = str(row[0]).strip().lower()
        # skip time-of-peak rows (values like "09:44")
        if not label:
            continue

        def get(r):
            i = col_idx.get(r)
            return _to_float(row[i]) if i is not None and i < len(row) else None

        if "evening peak" in label or "(at 1900" in label:
            for r in list(col_idx):
                result[f"evening_peak_demand_{r.lower()}_mw"] = get(r)
        elif "peak shortage" in label:
            for r in list(col_idx):
                result[f"peak_shortage_{r.lower()}_mw"] = get(r)
        elif "energy met" in label and "shortage" not in label:
            for r in list(col_idx):
                result[f"energy_met_{r.lower()}_mu"] = get(r)
        elif "hydro gen" in label:
            for r in list(col_idx):
                result[f"hydro_gen_{r.lower()}_mu"] = get(r)
        elif "wind gen" in label:
            for r in list(col_idx):
                result[f"wind_gen_{r.lower()}_mu"] = get(r)
        elif "solar gen" in label:
            for r in list(col_idx):
                result[f"solar_gen_{r.lower()}_mu"] = get(r)
        elif "energy shortage" in label:
            for r in list(col_idx):
                result[f"energy_shortage_{r.lower()}_mu"] = get(r)
        elif "maximum demand met" in label or "demand met during" in label:
            if "time" in label or "hour" in label:
                continue
            for r in list(col_idx):
                result[f"max_demand_met_{r.lower()}_mw"] = get(r)

    return result


def _parse_frequency(tables):
    """
    Table 2: frequency profile.
    Header: ['Region','FVI','<49.7','49.7-49.8','49.8-49.9','<49.9','49.9-50.05','> 50.05']
    Data:   ['All India', 0.040, ...]
    """
    result = {}
    for t in tables:
        if not t:
            continue
        # Find the row that has 'FVI'
        header_idx = None
        for i, row in enumerate(t):
            if any(str(c or "").strip() == "FVI" for c in row):
                header_idx = i
                break
        if header_idx is None:
            continue
        for row in t[header_idx + 1:]:
            label = str(row[0] or "").strip().lower()
            if "all india" in label:
                result["freq_fvi"]           = _to_float(row[1]) if len(row) > 1 else None
                result["freq_pct_below_497"] = _to_float(row[2]) if len(row) > 2 else None
                result["freq_pct_497_498"]   = _to_float(row[3]) if len(row) > 3 else None
                result["freq_pct_498_499"]   = _to_float(row[4]) if len(row) > 4 else None
                result["freq_pct_below_499"] = _to_float(row[5]) if len(row) > 5 else None
                result["freq_pct_499_5005"]  = _to_float(row[6]) if len(row) > 6 else None
                result["freq_pct_above_5005"]= _to_float(row[7]) if len(row) > 7 else None
                break
        if result:
            break
    return result


def _parse_generation_sourcewise(tables):
    """
    Tables 6 + 7: sourcewise generation (All India MU) and share %.
    Table 6 header: ['', 'NR', 'WR', 'SR', 'ER', 'NER', 'All India']
    Table 7: share rows (no header, just two data rows).
    """
    result = {}
    source_map = {
        "coal":    "gen_coal_mu",
        "lignite": "gen_lignite_mu",
        "hydro":   "gen_hydro_mu",
        "nuclear": "gen_nuclear_mu",
        "gas":     "gen_gas_mu",
        "res":     "gen_res_mu",
        "total":   "gen_total_mu",
    }

    for t in tables:
        if not t:
            continue
        headers = [str(c or "").strip().lower() for c in t[0]]
        # Detect generation table by "all india" column header
        ai_col = next((i for i, h in enumerate(headers)
                       if "all india" in h or "all\nindia" in h), None)
        if ai_col is None:
            continue
        # must also have generation rows
        row_labels = [str(r[0] or "").lower() for r in t[1:]]
        if not any("coal" in l for l in row_labels):
            continue

        for row in t[1:]:
            label = str(row[0] or "").strip().lower()
            val = _to_float(row[ai_col]) if ai_col < len(row) else None
            for key, col_name in source_map.items():
                if label.startswith(key):
                    result[col_name] = val
                    break

        if "gen_coal_mu" in result:
            break

    # Table 7: share rows — no "all india" in header but last column is all-india
    for t in tables:
        if not t:
            continue
        for row in t:
            label = str(row[0] or "").strip().lower()
            val   = _to_float(row[-1]) if row else None
            if "share of res" in label:
                result["share_res_pct"] = val
            elif "share of non" in label:
                result["share_nonfossil_pct"] = val

    return result


def _parse_outage(tables):
    """
    Table 5: generation outage MW.
    Header: ['', 'NR', 'WR', 'SR', 'ER', 'NER', 'Total']
    Rows:   Central Sector / State Sector / Total
    """
    result = {}
    for t in tables:
        if not t:
            continue
        row_labels = [str(r[0] or "").strip().lower() for r in t]
        has_central = any(l.startswith("central sector") for l in row_labels)
        has_state   = any(l.startswith("state sector")   for l in row_labels)
        if not (has_central and has_state):
            continue
        headers   = [str(c or "").strip().lower() for c in t[0]]
        total_col = next((i for i, h in enumerate(headers) if h == "total"), len(t[0]) - 1)
        for row in t:
            label = str(row[0] or "").strip().lower()
            val   = _to_float(row[total_col]) if total_col < len(row) else None
            if label.startswith("central sector"):
                result["outage_central_mw"] = val
            elif label.startswith("state sector"):
                result["outage_state_mw"] = val
            elif label == "total":
                result["outage_total_mw"] = val
        if result:
            break
    return result


def _parse_regional_import_export(tables):
    """
    Table 4: regional import/export actual MU.
    Header: ['', 'NR', 'WR', 'SR', 'ER', 'NER', 'TOTAL']
    """
    result = {}
    for t in tables:
        if not t:
            continue
        headers = [str(c or "").strip() for c in t[0]]
        if "NR" not in headers or "WR" not in headers:
            continue
        col_idx = {r: headers.index(r) for r in REGIONS + ["TOTAL", "Total"] if r in headers}
        for row in t[1:]:
            label = str(row[0] or "").strip().lower()
            if "actual" in label:
                for r, i in col_idx.items():
                    if r in REGIONS and i < len(row):
                        result[f"ie_actual_{r.lower()}_mu"] = _to_float(row[i])
                break
        if result:
            break
    return result


def _parse_transnational(tables):
    """
    Table 3: transnational exchanges actual MU.
    Header: ['', 'Bhutan', 'Nepal', 'Bangladesh']
    """
    result = {}
    for t in tables:
        if not t:
            continue
        headers_lower = [str(c or "").strip().lower() for c in t[0]]
        if "bhutan" not in headers_lower:
            continue
        for row in t[1:]:
            label = str(row[0] or "").strip().lower()
            if "actual" in label:
                for country in ["bhutan", "nepal", "bangladesh"]:
                    try:
                        i = headers_lower.index(country)
                        result[f"trans_{country}_mu"] = _to_float(row[i])
                    except (ValueError, IndexError):
                        pass
                break
        if result:
            break
    return result


# ── Main parse function ──────────────────────────────────────────────────────

def parse_pdf(filepath):
    """Parse a single PSP PDF and return a dict of daily features."""
    with pdfplumber.open(filepath) as pdf:
        date = _extract_date(pdf)
        if date is None:
            print(f"  WARNING: could not extract date from {Path(filepath).name}")
            return None

        # All data tables are on page 2 (index 1)
        tables = pdf.pages[1].extract_tables() if len(pdf.pages) > 1 else []

        row = {"date": date}
        row.update(_parse_regional_summary(tables))
        row.update(_parse_frequency(tables))
        row.update(_parse_generation_sourcewise(tables))
        row.update(_parse_outage(tables))
        row.update(_parse_regional_import_export(tables))
        row.update(_parse_transnational(tables))

    return row


def build_pdf_dataset(input_dir, output_csv):
    p = Path(input_dir)

    if p.is_file():
        files = [p]

    elif p.is_dir():
        files = sorted(p.rglob("*.pdf"))

    else:
        import glob
        files = [Path(f) for f in glob.glob(input_dir)]

    if not files:
        print(f"ERROR: No PDF files found in '{input_dir}'")
        return pd.DataFrame()

    print(f"Found {len(files)} PDF file(s).")
    rows, errors = [], []

    for f in files:
        try:
            row = parse_pdf(str(f))
            if row:
                rows.append(row)
            else:
                errors.append((f.name, "could not extract date"))
        except Exception as e:
            errors.append((f.name, str(e)))

    print(f"\nProcessed {len(files)} files: {len(rows)} succeeded, {len(errors)} failed.")
    if errors:
        print(f"\nErrors ({len(errors)}):")
        for name, e in errors:
            print(f"  {name}: {e}")

    if not rows:
        print("No rows extracted — check errors above.")
        pd.DataFrame().to_csv(output_csv, index=False)
        return pd.DataFrame()

    df = pd.DataFrame(rows).sort_values("date").reset_index(drop=True)
    df.to_csv(output_csv, index=False)
    print(f"\nParsed {len(df)} PDFs → {output_csv}")
    print(f"Columns ({len(df.columns)}): {df.columns.tolist()}")
    print(df.head(2).to_string())
    return df


if __name__ == "__main__":
    if len(sys.argv) == 3:
        build_pdf_dataset(sys.argv[1], sys.argv[2])
    elif len(sys.argv) == 2:
        row = parse_pdf(sys.argv[1])
        if row:
            for k, v in row.items():
                print(f"{k}: {v}")
        else:
            print("Failed to parse — see warnings above.")
    else:
        print("Usage: python parse_pdf_psp.py INPUT_DIR OUTPUT_CSV")
        print("   or: python parse_pdf_psp.py single_file.pdf")
