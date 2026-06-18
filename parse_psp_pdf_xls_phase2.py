import re
import sys
import glob
from pathlib import Path
from datetime import datetime

import pandas as pd


REGIONS = ["NR", "WR", "SR", "ER", "NER"]
COUNTRIES = ["bhutan", "nepal", "bangladesh"]

def _to_float(val):
    if val is None:
        return None
    try:
        import pandas as pd
        if pd.isna(val):
            return None
    except (TypeError, ValueError):
        pass
    s = str(val).strip().replace(",", "").replace("----------", "")
    if s.lower() == "nan" or s == "":
        return None
    try:
        return float(s)
    except ValueError:
        return None


def _parse_date_str(raw):
    """Try several date formats; return datetime.date or None."""
    raw = str(raw).strip()
    for fmt in ["%d-%b-%y", "%d-%b-%Y", "%d %b %y", "%d %b %Y",
                "%d/%m/%Y", "%Y-%m-%d"]:
        try:
            return datetime.strptime(raw, fmt).date()
        except ValueError:
            continue
    return None


def _pdf_extract_date(pdf):
    text2 = (pdf.pages[1].extract_text() or "") if len(pdf.pages) > 1 else ""
    m = re.search(r"Date of Reporting\s+(\d{1,2}[-\s]\w{3}[-\s]\d{2,4})", text2)
    if m:
        d = _parse_date_str(m.group(1))
        if d:
            return d
    m = re.search(r"\b(\d{1,2}-\w{3}-\d{2,4})\b", text2)
    if m:
        d = _parse_date_str(m.group(1))
        if d:
            return d
    text1 = pdf.pages[0].extract_text() or ""
    m = re.search(r"\b(\d{1,2}-\w{3}-\d{2,4})\b", text1)
    if m:
        return _parse_date_str(m.group(1))
    return None


def _pdf_regional_summary(tables):
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
    col_idx = {r: headers.index(r) for r in REGIONS + ["Total", "TOTAL"] if r in headers}

    for row in target[1:]:
        if not row or row[0] is None:
            continue
        label = str(row[0]).strip().lower()
        if not label:
            continue

        def get(r):
            i = col_idx.get(r)
            return _to_float(row[i]) if i is not None and i < len(row) else None

        if "evening peak" in label or "(at 1900" in label or "(at 19:00" in label:
            for r in col_idx:
                result[f"evening_peak_demand_{r.lower()}_mw"] = get(r)
        elif "peak shortage" in label:
            for r in col_idx:
                result[f"peak_shortage_{r.lower()}_mw"] = get(r)
        elif "energy met" in label and "shortage" not in label:
            for r in col_idx:
                result[f"energy_met_{r.lower()}_mu"] = get(r)
        elif "hydro gen" in label:
            for r in col_idx:
                result[f"hydro_gen_{r.lower()}_mu"] = get(r)
        elif "wind gen" in label:
            for r in col_idx:
                result[f"wind_gen_{r.lower()}_mu"] = get(r)
        elif "solar gen" in label:
            for r in col_idx:
                result[f"solar_gen_{r.lower()}_mu"] = get(r)
        elif "energy shortage" in label:
            for r in col_idx:
                result[f"energy_shortage_{r.lower()}_mu"] = get(r)
        elif ("maximum demand met" in label or "demand met during" in label) and \
                "time" not in label and "hour" not in label:
            for r in col_idx:
                result[f"max_demand_met_{r.lower()}_mw"] = get(r)

    return result


def _pdf_frequency(tables):
    result = {}
    for t in tables:
        if not t:
            continue
        header_idx = None
        for i, row in enumerate(t):
            if any(str(c or "").strip() == "FVI" for c in row):
                header_idx = i
                break
        if header_idx is None:
            continue
        for row in t[header_idx + 1:]:
            if "all india" in str(row[0] or "").strip().lower():
                result["freq_fvi"]            = _to_float(row[1]) if len(row) > 1 else None
                result["freq_pct_below_497"]  = _to_float(row[2]) if len(row) > 2 else None
                result["freq_pct_497_498"]    = _to_float(row[3]) if len(row) > 3 else None
                result["freq_pct_498_499"]    = _to_float(row[4]) if len(row) > 4 else None
                result["freq_pct_below_499"]  = _to_float(row[5]) if len(row) > 5 else None
                result["freq_pct_499_5005"]   = _to_float(row[6]) if len(row) > 6 else None
                result["freq_pct_above_5005"] = _to_float(row[7]) if len(row) > 7 else None
                break
        if result:
            break
    return result


def _pdf_generation(tables):
    result = {}
    source_map = {
        "coal": "gen_coal_mu", "lignite": "gen_lignite_mu", "hydro": "gen_hydro_mu",
        "nuclear": "gen_nuclear_mu", "gas": "gen_gas_mu", "res": "gen_res_mu",
        "total": "gen_total_mu",
    }
    for t in tables:
        if not t:
            continue
        headers = [str(c or "").strip().lower() for c in t[0]]
        ai_col = next((i for i, h in enumerate(headers)
                       if "all india" in h or "all\nindia" in h), None)
        if ai_col is None:
            continue
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

    for t in tables:
        if not t:
            continue
        for row in t:
            label = str(row[0] or "").strip().lower()
            val = _to_float(row[-1]) if row else None
            if "share of res" in label:
                result["share_res_pct"] = val
            elif "share of non" in label:
                result["share_nonfossil_pct"] = val
    return result


def _pdf_outage(tables):
    """
    Extract regional outage breakdown (Central + State rows × NR/WR/SR/ER/NER/Total).
    Also retains legacy total-only keys for backward compat.
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

        headers = [str(c or "").strip() for c in t[0]]
        # Build region column map
        reg_cols = {}
        for r in REGIONS + ["Total", "TOTAL"]:
            if r in headers:
                reg_cols[r] = headers.index(r)

        for row in t:
            label = str(row[0] or "").strip().lower()
            if label.startswith("central sector"):
                prefix = "outage_central"
            elif label.startswith("state sector"):
                prefix = "outage_state"
            elif label == "total":
                prefix = "outage_total"
            else:
                continue
            for r, i in reg_cols.items():
                col_key = r.lower() if r not in ("Total", "TOTAL") else "total"
                result[f"{prefix}_{col_key}_mw"] = _to_float(row[i]) if i < len(row) else None

        if result:
            break
    return result


def _pdf_regional_ie(tables):
    """
    Extract Schedule, Actual, OD/UD rows from the regional IE section.
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
            if "schedule" in label:
                prefix = "ie_schedule"
            elif "actual" in label:
                prefix = "ie_actual"
            elif "o/d" in label or "od" in label:
                prefix = "ie_odud"
            else:
                continue
            for r, i in col_idx.items():
                col_key = r.lower() if r not in ("TOTAL", "Total") else "total"
                result[f"{prefix}_{col_key}_mu"] = _to_float(row[i]) if i < len(row) else None

        if any(k.startswith("ie_") for k in result):
            break
    return result


def _pdf_transnational(tables):
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
                for country in COUNTRIES:
                    try:
                        i = headers_lower.index(country)
                        result[f"trans_{country}_mu"] = _to_float(row[i])
                    except (ValueError, IndexError):
                        pass
                break
        if result:
            break
    return result


def _pdf_diversity(tables):
    """Extract the two diversity factor rows (Regional + State)."""
    result = {}
    for t in tables:
        if not t:
            continue
        for row in t:
            label = str(row[0] or "").strip().lower()
            # Diversity factors are often in a single-column-ish table
            # Look for the numeric value in col 1 or the last non-None cell
            vals = [_to_float(c) for c in row if _to_float(c) is not None]
            if not vals:
                continue
            val = vals[0]
            if "regional" in label and "diversity" not in label and val is None:
                continue
            if "based on regional" in label:
                result["diversity_regional"] = val
            elif "based on state" in label:
                result["diversity_state"] = val
        if result:
            break
    return result


def parse_pdf(filepath):
    """Parse a single PSP PDF → dict of daily features."""
    import pdfplumber
    with pdfplumber.open(filepath) as pdf:
        date = _pdf_extract_date(pdf)
        if date is None:
            print(f"  WARNING: could not extract date from {Path(filepath).name}")
            return None

        tables = pdf.pages[1].extract_tables() if len(pdf.pages) > 1 else []

        row = {"date": date}
        row.update(_pdf_regional_summary(tables))
        row.update(_pdf_frequency(tables))
        row.update(_pdf_generation(tables))
        row.update(_pdf_outage(tables))
        row.update(_pdf_regional_ie(tables))
        row.update(_pdf_transnational(tables))
        row.update(_pdf_diversity(tables))

    return row

def _xls_read_sheet(filepath, sheet):
    return pd.read_excel(filepath, sheet_name=sheet, engine="xlrd", header=None)


def _xls_find_date(df):
    """Scan all cells for 'Date of Reporting' and parse the value to its right."""
    for _, row in df.iterrows():
        for j, cell in enumerate(row):
            if isinstance(cell, str) and "date of reporting" in cell.lower():
                # Look rightward for a date-like value
                for k in range(j + 1, len(row)):
                    val = row.iloc[k]
                    if pd.isna(val):
                        continue
                    d = _parse_date_str(str(val))
                    if d:
                        return d
    return None


def _xls_col_map(df, row_idx):
    """
    Given a header row index, return {label_str: col_idx} for REGIONS + TOTAL/All India.
    """
    col_map = {}
    for j, cell in enumerate(df.iloc[row_idx]):
        s = str(cell).strip() if not pd.isna(cell) else ""
        if s in REGIONS or s in ("TOTAL", "Total", "All India", "All\nIndia"):
            col_map[s] = j
    return col_map


def _xls_parse_mop_e(df):
    """
    Parse the MOP_E sheet of an XLS file.
    Mirrors all the PDF section parsers but works on the flat DataFrame.
    Returns a dict of features.
    """
    result = {}
    nrows = len(df)

    # ── helper ──────────────────────────────────────────────────────────────
    def cell(r, c):
        return df.iloc[r, c] if r < nrows and c < df.shape[1] else None

    def fval(r, c):
        return _to_float(cell(r, c))

    # ── locate key structural rows ──────────────────────────────────────────
    # We scan col 0 for known labels (case-insensitive)
    label_rows = {}   # label_key -> row_index
    for i, row in df.iterrows():
        lbl = str(row.iloc[0]).strip().lower() if not pd.isna(row.iloc[0]) else ""
        if lbl:
            label_rows[lbl] = i

    def find_row(substring):
        for lbl, idx in label_rows.items():
            if substring in lbl:
                return idx
        return None

    # ── Section A: regional summary ─────────────────────────────────────────
    # Header row has NR/WR/SR/ER/NER/TOTAL in it; find it
    header_row = None
    for i, row in df.iterrows():
        vals = [str(v).strip() for v in row if not pd.isna(v)]
        if "NR" in vals and "WR" in vals and "SR" in vals:
            header_row = i
            break

    if header_row is not None:
        col_map = _xls_col_map(df, header_row)

        def get_region(row_idx, r):
            j = col_map.get(r) or col_map.get("TOTAL") if r in ("TOTAL", "Total") else col_map.get(r)
            return fval(row_idx, j) if j is not None else None

        for i in range(header_row + 1, min(header_row + 20, nrows)):
            lbl = str(df.iloc[i, 0]).strip().lower() if not pd.isna(df.iloc[i, 0]) else ""
            if not lbl:
                continue

            def gr(r):
                j = col_map.get(r)
                return fval(i, j) if j is not None else None

            if "evening peak" in lbl or "(at 19:00" in lbl or "(at 1900" in lbl:
                for r in list(col_map):
                    result[f"evening_peak_demand_{r.lower()}_mw"] = gr(r)
            elif "peak shortage" in lbl:
                for r in list(col_map):
                    result[f"peak_shortage_{r.lower()}_mw"] = gr(r)
            elif "energy met" in lbl and "shortage" not in lbl:
                for r in list(col_map):
                    result[f"energy_met_{r.lower()}_mu"] = gr(r)
            elif "hydro gen" in lbl:
                for r in list(col_map):
                    result[f"hydro_gen_{r.lower()}_mu"] = gr(r)
            elif "wind gen" in lbl:
                for r in list(col_map):
                    result[f"wind_gen_{r.lower()}_mu"] = gr(r)
            elif "solar gen" in lbl:
                for r in list(col_map):
                    result[f"solar_gen_{r.lower()}_mu"] = gr(r)
            elif "energy shortage" in lbl:
                for r in list(col_map):
                    result[f"energy_shortage_{r.lower()}_mu"] = gr(r)
            elif ("maximum demand met" in lbl or "demand met during" in lbl) and \
                    "time" not in lbl and "hour" not in lbl:
                for r in list(col_map):
                    result[f"max_demand_met_{r.lower()}_mw"] = gr(r)

    # ── Section B: frequency ─────────────────────────────────────────────────
    freq_header = None
    for i, row in df.iterrows():
        vals = [str(v).strip() for v in row if not pd.isna(v)]
        if "FVI" in vals:
            freq_header = i
            break
    if freq_header is not None:
        for i in range(freq_header + 1, min(freq_header + 5, nrows)):
            lbl = str(df.iloc[i, 0]).strip().lower() if not pd.isna(df.iloc[i, 0]) else ""
            if "all india" in lbl:
                row = df.iloc[i]
                result["freq_fvi"]            = _to_float(row.iloc[1]) if len(row) > 1 else None
                result["freq_pct_below_497"]  = _to_float(row.iloc[2]) if len(row) > 2 else None
                result["freq_pct_497_498"]    = _to_float(row.iloc[3]) if len(row) > 3 else None
                result["freq_pct_498_499"]    = _to_float(row.iloc[4]) if len(row) > 4 else None
                result["freq_pct_below_499"]  = _to_float(row.iloc[5]) if len(row) > 5 else None
                result["freq_pct_499_5005"]   = _to_float(row.iloc[6]) if len(row) > 6 else None
                result["freq_pct_above_5005"] = _to_float(row.iloc[7]) if len(row) > 7 else None
                break

    # ── Section D: transnational ─────────────────────────────────────────────
    for i, row in df.iterrows():
        vals_lower = [str(v).strip().lower() for v in row if not pd.isna(v)]
        if "bhutan" in vals_lower:
            # This is the header row; actual row is below
            bhutan_col  = next((j for j, v in enumerate(row) if str(v).strip().lower() == "bhutan"), None)
            nepal_col   = next((j for j, v in enumerate(row) if str(v).strip().lower() == "nepal"), None)
            bd_col      = next((j for j, v in enumerate(row) if "bangladesh" in str(v).strip().lower()), None)
            godda_col   = next((j for j, v in enumerate(row) if "godda" in str(v).strip().lower()), None)
            # scan next rows for "actual"
            for k in range(i + 1, min(i + 5, nrows)):
                lbl = str(df.iloc[k, 0]).strip().lower() if not pd.isna(df.iloc[k, 0]) else ""
                if "actual" in lbl:
                    result["trans_bhutan_mu"]     = fval(k, bhutan_col) if bhutan_col else None
                    result["trans_nepal_mu"]       = fval(k, nepal_col) if nepal_col else None
                    result["trans_bangladesh_mu"]  = fval(k, bd_col) if bd_col else None
                    # Godda → Bangladesh (new in 2024)
                    if godda_col:
                        result["trans_godda_bangladesh_mu"] = fval(k, godda_col)
                    break
            break

    # ── Section E: regional import/export ───────────────────────────────────
    ie_header = None
    for i, row in df.iterrows():
        lbl = str(row.iloc[0]).strip().lower() if not pd.isna(row.iloc[0]) else ""
        if "import/export by regions" in lbl or "e. import/export" in lbl:
            ie_header = i
            break

    if ie_header is not None:
        # Find the NR/WR/… header row right below
        for i in range(ie_header + 1, min(ie_header + 4, nrows)):
            vals = [str(v).strip() for v in df.iloc[i] if not pd.isna(v)]
            if "NR" in vals and "WR" in vals:
                ie_col_map = _xls_col_map(df, i)
                # Scan the next ~6 rows for Schedule/Actual/OD
                for k in range(i + 1, min(i + 7, nrows)):
                    lbl = str(df.iloc[k, 0]).strip().lower() if not pd.isna(df.iloc[k, 0]) else ""
                    if "schedule" in lbl:
                        prefix = "ie_schedule"
                    elif "actual" in lbl:
                        prefix = "ie_actual"
                    elif "o/d" in lbl or "od" in lbl:
                        prefix = "ie_odud"
                    else:
                        continue
                    for r, j in ie_col_map.items():
                        col_key = r.lower() if r not in ("TOTAL", "Total") else "total"
                        result[f"{prefix}_{col_key}_mu"] = fval(k, j)
                break

    # ── Section F: generation outage ─────────────────────────────────────────
    out_header = None
    for i, row in df.iterrows():
        lbl = str(row.iloc[0]).strip().lower() if not pd.isna(row.iloc[0]) else ""
        if "generation outage" in lbl:
            out_header = i
            break

    if out_header is not None:
        for i in range(out_header + 1, min(out_header + 4, nrows)):
            vals = [str(v).strip() for v in df.iloc[i] if not pd.isna(v)]
            if "NR" in vals and "WR" in vals:
                out_col_map = _xls_col_map(df, i)
                for k in range(i + 1, min(i + 6, nrows)):
                    lbl = str(df.iloc[k, 0]).strip().lower() if not pd.isna(df.iloc[k, 0]) else ""
                    if "central sector" in lbl:
                        prefix = "outage_central"
                    elif "state sector" in lbl:
                        prefix = "outage_state"
                    elif lbl == "total":
                        prefix = "outage_total"
                    else:
                        continue
                    for r, j in out_col_map.items():
                        col_key = r.lower() if r not in ("TOTAL", "Total") else "total"
                        result[f"{prefix}_{col_key}_mw"] = fval(k, j)
                break

    # ── Section G: sourcewise generation ─────────────────────────────────────
    gen_header = None
    for i, row in df.iterrows():
        lbl = str(row.iloc[0]).strip().lower() if not pd.isna(row.iloc[0]) else ""
        if "sourcewise generation" in lbl:
            gen_header = i
            break

    if gen_header is not None:
        for i in range(gen_header + 1, min(gen_header + 4, nrows)):
            vals = [str(v).strip() for v in df.iloc[i] if not pd.isna(v)]
            if "NR" in vals and "All India" in vals:
                gen_col_map = _xls_col_map(df, i)
                ai_col = gen_col_map.get("All India")
                if ai_col is None:
                    break
                source_map = {
                    "coal": "gen_coal_mu", "lignite": "gen_lignite_mu",
                    "hydro": "gen_hydro_mu", "nuclear": "gen_nuclear_mu",
                    "gas": "gen_gas_mu", "res": "gen_res_mu", "total": "gen_total_mu",
                }
                for k in range(i + 1, min(i + 10, nrows)):
                    lbl = str(df.iloc[k, 0]).strip().lower() if not pd.isna(df.iloc[k, 0]) else ""
                    val = fval(k, ai_col)
                    for key, col_name in source_map.items():
                        if lbl.startswith(key):
                            result[col_name] = val
                            break
                break

    # Share rows — All India value is the last non-NaN numeric in the row
    for i, row in df.iterrows():
        lbl = str(row.iloc[0]).strip().lower() if not pd.isna(row.iloc[0]) else ""
        if "share of res" in lbl:
            vals = [_to_float(v) for v in row.iloc[1:] if _to_float(v) is not None]
            result["share_res_pct"] = vals[-1] if vals else None
        elif "share of non" in lbl:
            vals = [_to_float(v) for v in row.iloc[1:] if _to_float(v) is not None]
            result["share_nonfossil_pct"] = vals[-1] if vals else None

    # ── Section H: diversity factors ─────────────────────────────────────────
    for i, row in df.iterrows():
        lbl = str(row.iloc[0]).strip().lower() if not pd.isna(row.iloc[0]) else ""
        if "based on regional" in lbl:
            # value sits in col 2 in XLS (col 1 is NaN)
            val = next((_to_float(v) for v in row.iloc[1:] if _to_float(v) is not None), None)
            result["diversity_regional"] = val
        elif "based on state" in lbl:
            val = next((_to_float(v) for v in row.iloc[1:] if _to_float(v) is not None), None)
            result["diversity_state"] = val

    # ── Section I (2024+): solar / non-solar peak ────────────────────────────
    # Structure: row with "Solar hr" in col 4, max-demand in col 5, shortage in col 8
    for i, row in df.iterrows():
        for j, cell in enumerate(row):
            lbl = str(cell).strip().lower() if not pd.isna(cell) else ""
            if lbl == "solar hr":
                result["solar_hr_peak_mw"]     = _to_float(row.iloc[j + 1]) if j + 1 < len(row) else None
                result["solar_hr_shortage_mw"] = _to_float(row.iloc[j + 4]) if j + 4 < len(row) else None
            elif lbl == "non-solar hr":
                result["nonsolar_hr_peak_mw"]     = _to_float(row.iloc[j + 1]) if j + 1 < len(row) else None
                result["nonsolar_hr_shortage_mw"] = _to_float(row.iloc[j + 4]) if j + 4 < len(row) else None

    return result


def _xls_parse_crossborder(df):
    """
    Parse the CrossBorder sheet (present from FY2024 onwards).
    Extracts total export/import/net per country from the TOTAL column (col 12).
    Returns dict with keys: xb_export_*, xb_import_*, xb_net_*
    """
    result = {}
    country_map = {
        "bhutan": "bhutan", "nepal": "nepal",
        "bangladesh": "bangladesh", "myanmar": "myanmar",
    }

    # TOTAL is the last column in the CrossBorder sheet (col 12)
    total_col = df.shape[1] - 1

    # Identify section blocks
    sections = {}
    for i, row in df.iterrows():
        lbl = " ".join(str(v).lower() for v in row if not pd.isna(v))
        if "export from india" in lbl:
            sections["export"] = i
        elif "import by india" in lbl:
            sections["import"] = i
        elif "net from india" in lbl:
            sections["net"] = i

    for section_name, section_start in sections.items():
        for i in range(section_start, min(section_start + 20, len(df))):
            row_label = str(df.iloc[i, 0]).strip().lower() if not pd.isna(df.iloc[i, 0]) else ""
            for country_key, country_name in country_map.items():
                if row_label == country_key:
                    result[f"xb_{section_name}_{country_name}_mu"] = _to_float(df.iloc[i, total_col])
    return result


def _parse_timeseries_time_cell(val):
    """
    Decode a single TIME-column cell from the TimeSeries sheet into (hh, mm).

    Three formats appear across the corpus:
      1. String  "H:MM:SS"  or  "H:MM"   — seen in most Nov-2024 files
         (xlrd reads the cell as a plain string because the cell is formatted
         as Text in the workbook).
      2. float fraction-of-day  0.0 … <1.0  — seen when xlrd reads a true
         XLS time cell (xlrd type=3) that pandas surfaces as a float.
         e.g. 0:15 → 0.010416666…  (= 15 / (24*60))
      3. datetime.time object  — seen in some Nov-2024 files where pandas
         converts an XLS time cell to a Python datetime.time.

    Returns (hh, mm) as ints, or None if the cell is not a recognisable time.
    """
    if val is None:
        return None

    # Case 3: pandas already decoded it to datetime.time
    if hasattr(val, 'hour') and hasattr(val, 'minute'):
        return val.hour, val.minute

    # Case 2: float fraction of a day (xlrd type=3 surfaced as float by pandas)
    try:
        f = float(val)
        if 0.0 <= f < 1.0:
            total_minutes = round(f * 24 * 60)
            hh, mm = divmod(total_minutes, 60)
            return hh % 24, mm
    except (TypeError, ValueError):
        pass

    # Case 1: string "H:MM:SS" or "H:MM"
    s = str(val).strip()
    m = re.match(r"^(\d{1,2}):(\d{2})(?::\d{2})?$", s)
    if m:
        return int(m.group(1)) % 24, int(m.group(2))

    return None  # disclaimer row / unexpected content → stop parsing


def _xls_parse_timeseries_records(df):
    """
    Parse the TimeSeries sheet into a list of per-15-min-block records —
    the shared core used by both the wide (one-row-per-day) and long
    (one-row-per-15-min-block) builders.

    Sheet layout: a header row with TIME / FREQUENCY(Hz) / DEMAND MET(MW) /
    NUCLEAR(MW) / WIND(MW) / SOLAR(MW) / HYDRO**(MW) / GAS(MW) / THERMAL(MW) /
    OTHERS*(MW) / NET DEMAND MET(MW) / TOTAL GENERATION(MW) /
    NET TRANSNATIONAL EXCHANGE(MW), followed by ~96 data rows (one per
    15-min slot: 0:00, 0:15, … 23:45).

    Handles all known TIME-column encodings via _parse_timeseries_time_cell():
      • "H:MM:SS" / "H:MM" strings  (most Nov-2024 files)
      • xlrd float fraction-of-day  (some Nov-2024 files)
      • datetime.time objects       (pandas coercion of XLS time cells)

    Returns: list of dicts, each like
        {"hhmm": "0000", "time": "00:00", "freq_hz": 49.99,
         "demand_met_mw": 147488.0, "nuclear_mw": ..., ...}
    Does NOT attach a date — callers do that.
    """
    records = []

    # Locate header row (col 0 == "TIME")
    header_idx = None
    for i, row in df.iterrows():
        if str(row.iloc[0]).strip().upper() == "TIME":
            header_idx = i
            break
    if header_idx is None:
        return records

    def _norm(s):
        s = str(s).replace("\n", " ").replace("*", "")
        s = re.sub(r"\s+", " ", s).strip().upper()
        return s

    headers = [_norm(c) for c in df.iloc[header_idx]]

    # Most-specific labels first to avoid substring collisions
    # (e.g. "NET DEMAND MET" must be checked before plain "DEMAND MET").
    label_order = [
        ("NET TRANSNATIONAL EXCHANGE", "net_trans_exchange_mw"),
        ("NET DEMAND MET",             "net_demand_met_mw"),
        ("TOTAL GENERATION",           "total_gen_mw"),
        ("DEMAND MET",                 "demand_met_mw"),
        ("FREQUENCY",                  "freq_hz"),
        ("NUCLEAR",                    "nuclear_mw"),
        ("WIND",                       "wind_mw"),
        ("SOLAR",                      "solar_mw"),
        ("HYDRO",                      "hydro_mw"),
        ("GAS",                        "gas_mw"),
        ("THERMAL",                    "thermal_mw"),
        ("OTHERS",                     "others_mw"),
    ]

    col_metric = {}  # col_idx -> metric_key
    for j, h in enumerate(headers):
        if j == 0:
            continue
        for label, key in label_order:
            if label in h:
                col_metric[j] = key
                break

    if not col_metric:
        return records

    for i in range(header_idx + 1, len(df)):
        cell_val = df.iloc[i, 0]
        if pd.isna(cell_val):
            continue  # blank separator row — skip, don't stop
        parsed = _parse_timeseries_time_cell(cell_val)
        if parsed is None:
            break  # disclaimer / footer text — stop
        hh, mm = parsed
        rec = {"hhmm": f"{hh:02d}{mm:02d}", "time": f"{hh:02d}:{mm:02d}"}
        for j, metric_key in col_metric.items():
            rec[metric_key] = _to_float(df.iloc[i, j]) if j < df.shape[1] else None
        records.append(rec)

    return records


def _xls_parse_timeseries(df):
    """
    WIDE view of the TimeSeries sheet: one row per day, each metric exploded
    into 96 columns named ts_<metric>_HHMM (e.g. ts_freq_hz_0000,
    ts_demand_met_mw_1915, ...). Good for daily-level analysis.

    For the long/tidy view (one row per 15-min block — what Study 2's
    frequency-violation classifier needs), use _xls_parse_timeseries_records()
    directly, or run this script in "long" mode (see build_timeseries_long).
    """
    result = {}
    for rec in _xls_parse_timeseries_records(df):
        hhmm = rec["hhmm"]
        for metric_key, val in rec.items():
            if metric_key in ("hhmm", "time"):
                continue
            result[f"ts_{metric_key}_{hhmm}"] = val
    return result


def parse_xls(filepath):
    """Parse a single PSP XLS file → dict of daily features."""
    xl = pd.ExcelFile(filepath, engine="xlrd")
    sheets = xl.sheet_names

    row = {}

    # MOP_E sheet (always present)
    if "MOP_E" in sheets:
        df_mop = _xls_read_sheet(filepath, "MOP_E")
        date = _xls_find_date(df_mop)
        if date is None:
            print(f"  WARNING: could not extract date from {Path(filepath).name}")
            return None
        row["date"] = date
        row.update(_xls_parse_mop_e(df_mop))
    else:
        print(f"  WARNING: no MOP_E sheet in {Path(filepath).name}")
        return None

    # CrossBorder sheet (FY2024+, optional)
    if "CrossBorder" in sheets:
        df_cb = _xls_read_sheet(filepath, "CrossBorder")
        row.update(_xls_parse_crossborder(df_cb))

    # TimeSeries sheet (present from Nov-2024 onwards) — 15-min SCADA data, wide format
    if "TimeSeries" in sheets:
        df_ts = _xls_read_sheet(filepath, "TimeSeries")
        row.update(_xls_parse_timeseries(df_ts))

    return row


# ═══════════════════════════════════════════════════════════════════════════════
# ── DISPATCHER ────────────────────────────────────────────────────────────────
# ═══════════════════════════════════════════════════════════════════════════════

def parse_file(filepath):
    """Dispatch to PDF or XLS parser based on extension."""
    ext = Path(filepath).suffix.lower()
    if ext == ".pdf":
        return parse_pdf(str(filepath))
    elif ext in (".xls", ".xlsx"):
        return parse_xls(str(filepath))
    else:
        print(f"  WARNING: unsupported extension '{ext}' — {Path(filepath).name}")
        return None


def build_dataset(input_path, output_csv):
    p = Path(input_path)
    if p.is_file():
        files = [p]
    elif p.is_dir():
        files = sorted(p.rglob("*.pdf")) + sorted(p.rglob("*.xls")) + sorted(p.rglob("*.xlsx"))
        files = sorted(files, key=lambda f: f.name)
    else:
        files = [Path(f) for f in glob.glob(input_path)]

    if not files:
        print(f"ERROR: no files found at '{input_path}'")
        return pd.DataFrame()

    print(f"Found {len(files)} file(s).")
    rows, errors = [], []

    for f in files:
        try:
            r = parse_file(f)
            if r:
                rows.append(r)
            else:
                errors.append((f.name, "could not extract"))
        except Exception as e:
            errors.append((f.name, str(e)))

    print(f"\nProcessed {len(files)}: {len(rows)} OK, {len(errors)} failed.")
    if errors:
        print(f"\nErrors ({len(errors)}):")
        for name, e in errors:
            print(f"  {name}: {e}")

    if not rows:
        pd.DataFrame().to_csv(output_csv, index=False)
        return pd.DataFrame()

    df = pd.DataFrame(rows).sort_values("date").reset_index(drop=True)
    df.to_csv(output_csv, index=False)
    print(f"\nSaved {len(df)} rows → {output_csv}")
    print(f"Columns ({len(df.columns)}): {df.columns.tolist()}")
    return df


def build_timeseries_long(input_path, output_csv):
    """
    Long/tidy builder for Study 2 (frequency-violation classifier): one row
    per 15-min block per day, instead of the wide one-row-per-day format
    that build_dataset() produces.

    Columns: date, time, hhmm, freq_hz, demand_met_mw, nuclear_mw, wind_mw,
    solar_mw, hydro_mw, gas_mw, thermal_mw, others_mw, net_demand_met_mw,
    total_gen_mw, net_trans_exchange_mw.

    Only XLS files with a TimeSeries sheet (present from Nov-2024 onwards)
    contribute rows; older files are silently skipped since they have no
    15-min data to give.
    """
    p = Path(input_path)
    if p.is_file():
        files = [p]
    elif p.is_dir():
        files = sorted(p.rglob("*.xls")) + sorted(p.rglob("*.xlsx"))
        files = sorted(files, key=lambda f: f.name)
    else:
        files = [Path(f) for f in glob.glob(input_path)]

    if not files:
        print(f"ERROR: no files found at '{input_path}'")
        return pd.DataFrame()

    print(f"Found {len(files)} file(s).")
    all_rows, skipped, errors = [], [], []

    for f in files:
        try:
            xl = pd.ExcelFile(str(f), engine="xlrd")
            sheets = xl.sheet_names
            if "TimeSeries" not in sheets:
                skipped.append(f.name)
                continue
            if "MOP_E" not in sheets:
                errors.append((f.name, "no MOP_E sheet to read date from"))
                continue

            df_mop = _xls_read_sheet(str(f), "MOP_E")
            date = _xls_find_date(df_mop)
            if date is None:
                errors.append((f.name, "could not extract date"))
                continue

            df_ts = _xls_read_sheet(str(f), "TimeSeries")
            records = _xls_parse_timeseries_records(df_ts)
            if not records:
                errors.append((f.name, "TimeSeries sheet present but unparseable"))
                continue

            for rec in records:
                rec["date"] = date
                all_rows.append(rec)
        except Exception as e:
            errors.append((f.name, str(e)))

    print(f"\nProcessed {len(files)}: {len(all_rows)} rows from "
          f"{len(files) - len(skipped) - len(errors)} file(s), "
          f"{len(skipped)} skipped (no TimeSeries sheet), {len(errors)} failed.")
    if errors:
        print(f"\nErrors ({len(errors)}):")
        for name, e in errors:
            print(f"  {name}: {e}")

    if not all_rows:
        pd.DataFrame().to_csv(output_csv, index=False)
        return pd.DataFrame()

    df = pd.DataFrame(all_rows)
    front = ["date", "time", "hhmm"]
    df = df[front + [c for c in df.columns if c not in front]]
    df = df.sort_values(["date", "hhmm"]).reset_index(drop=True)
    df.to_csv(output_csv, index=False)
    print(f"\nSaved {len(df)} rows (long format) → {output_csv}")
    print(f"Columns ({len(df.columns)}): {df.columns.tolist()}")
    return df


if __name__ == "__main__":
    if len(sys.argv) == 4 and sys.argv[1] == "long":
        build_timeseries_long(sys.argv[2], sys.argv[3])
    elif len(sys.argv) == 3:
        build_dataset(sys.argv[1], sys.argv[2])
    elif len(sys.argv) == 2:
        r = parse_file(sys.argv[1])
        if r:
            for k, v in r.items():
                print(f"{k}: {v}")
        else:
            print("Failed to parse — see warnings above.")
    else:
        print("Usage: python parse_psp.py INPUT_DIR OUTPUT_CSV              (wide, one row per day)")
        print("   or: python parse_psp.py long INPUT_DIR OUTPUT_CSV        (long, one row per 15-min block; FY2025+ only)")
        print("   or: python parse_psp.py single_file.pdf")
        print("   or: python parse_psp.py single_file.xls")
