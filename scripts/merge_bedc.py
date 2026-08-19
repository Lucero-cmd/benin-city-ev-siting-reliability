"""
Merge 13 months of BEDC Band A feeder daily supply-hours data (April 2025 - April 2026)
into one long panel: Feeder x Month x Day x Supply Hours.
Filters to confirmed Benin City feeders only.
Produces a data-quality/missingness summary alongside the merged panel.
"""
import pandas as pd
import numpy as np
import re
import calendar
import os

pd.set_option('display.max_columns', None)

# ---------------------------------------------------------------------------
# 1. Confirmed Benin City feeder name list (validated earlier against
#    Feeder Location / Major Streets fields in the Jan-Apr 2026 files)
# ---------------------------------------------------------------------------
BENIN_FEEDERS = {
    "AIRPORT (COMMERCIAL)", "AKPAKPAVA COMMERCIAL", "EGOR", "EKEHUAN CAMPUS",
    "ETETE", "FEDERAL SECRETARIAT COMMERCIAL", "GRA", "GRA 11", "GRA COMMERCIAL",
    "IDSL COMMERCIAL", "IHAMA", "IHOVBOR", "IKPOBA-HILL-COMMERCIAL",
    "LIMIT ROAD COMMERCIAL", "MBH COMMERCIAL", "NEKPENEKPEN", "OLUKU",
    "SWITCHING STATION", "UGBOR", "UJEMEN-COMMERCIAL", "UNIBEN",
    "UNIBEN COMMERCIAL", "UPPER LAWANI",
}

def norm_name(x):
    if pd.isna(x):
        return ""
    return re.sub(r'\s+', ' ', str(x)).strip().upper()

NORM_BENIN = {norm_name(x) for x in BENIN_FEEDERS}

MONTHS = [
    ("bedc_april_2025.csv", "2025-04", "compliance"),
    ("BEDC_may_2025.csv", "2025-05", "compliance"),
    ("bedc_june_2025.csv", "2025-06", "compliance"),
    ("bedc_july_2025.csv", "2025-07", "compliance"),
    ("BEDC_August__2025.csv", "2025-08", "plain"),
    ("bedc_september_2025.csv", "2025-09", "plain"),
    ("BEDC__1__October__2025.csv", "2025-10", "plain"),
    ("BEDC_2NOVEMBER.csv", "2025-11", "plain"),
    ("BEDC_3December.csv", "2025-12", "plain"),
    ("BEDC_4January.csv", "2026-01", "plain"),
    ("BEDC_5February.csv", "2026-02", "plain"),
    ("BEDC_6March.csv", "2026-03", "plain"),
    ("BEDC_7April.csv", "2026-04", "plain"),
]

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
RAW_DIR = os.path.join(SCRIPT_DIR, "..", "data", "raw") + os.sep
OUTPUT_DIR = os.path.join(SCRIPT_DIR, "..", "data", "processed") + os.sep
os.makedirs(OUTPUT_DIR, exist_ok=True)

def resolve_path(fname):
    path = RAW_DIR + fname
    if not os.path.exists(path):
        raise FileNotFoundError(
            f"Could not find '{fname}' in {RAW_DIR}. "
            f"Make sure all 13 raw BEDC files are placed in data/raw/."
        )
    return path

DAY_RE = re.compile(r'^\s*(\d{1,2})(st|nd|rd|th)\s*$', re.IGNORECASE)

def parse_plain(path, month_str):
    df = pd.read_csv(path)
    df.columns = [str(c).strip() for c in df.columns]
    # drop fully-unnamed columns
    df = df.loc[:, ~df.columns.str.startswith('Unnamed')]
    day_cols = {}
    for c in df.columns:
        m = DAY_RE.match(c)
        if m:
            day_cols[c] = int(m.group(1))
    keep = ['Feeder']
    if 'Band' in df.columns:
        keep.append('Band')
    sub = df[keep + list(day_cols.keys())].copy()
    sub['Feeder_norm'] = sub['Feeder'].apply(norm_name)
    sub = sub[sub['Feeder_norm'].isin(NORM_BENIN)]
    long = sub.melt(id_vars=['Feeder', 'Feeder_norm'] + (['Band'] if 'Band' in sub.columns else []),
                     value_vars=list(day_cols.keys()), var_name='day_col', value_name='hours')
    long['day'] = long['day_col'].map(day_cols)
    long['month'] = month_str
    long['hours'] = pd.to_numeric(long['hours'], errors='coerce')
    return long[['Feeder', 'Feeder_norm', 'month', 'day', 'hours']]

def parse_compliance(path, month_str):
    raw = pd.read_csv(path, header=None)
    # header row 3 (0-indexed 2) holds the date columns; feeder name in col index 1
    header_row = raw.iloc[2]
    data = raw.iloc[3:].reset_index(drop=True)
    day_cols = {}
    for idx, val in header_row.items():
        if pd.isna(val):
            continue
        s = str(val)
        m = re.match(r'^(\d{1,2})/', s)
        if m:
            day_cols[idx] = int(m.group(1))
    rows = []
    for _, r in data.iterrows():
        feeder = r[1]
        if pd.isna(feeder):
            continue
        fn = norm_name(feeder)
        if fn not in NORM_BENIN:
            continue
        for col_idx, day in day_cols.items():
            val = r[col_idx]
            rows.append({'Feeder': feeder, 'Feeder_norm': fn, 'month': month_str,
                         'day': day, 'hours': pd.to_numeric(val, errors='coerce')})
    return pd.DataFrame(rows)

all_long = []
quality_rows = []

for fname, month_str, kind in MONTHS:
    path = resolve_path(fname)
    if kind == 'plain':
        long = parse_plain(path, month_str)
    else:
        long = parse_compliance(path, month_str)
    n_feeders_found = long['Feeder_norm'].nunique()
    missing_feeders = NORM_BENIN - set(long['Feeder_norm'].unique())
    n_missing_vals = long['hours'].isna().sum()
    n_total_vals = len(long)
    quality_rows.append({
        'month': month_str, 'source_file': fname, 'schema': kind,
        'benin_feeders_found': n_feeders_found,
        'benin_feeders_expected': len(NORM_BENIN),
        'missing_feeder_names': ", ".join(sorted(missing_feeders)) if missing_feeders else "",
        'day_values_total': n_total_vals,
        'day_values_missing_or_nonnumeric': int(n_missing_vals),
        'pct_missing': round(100 * n_missing_vals / n_total_vals, 1) if n_total_vals else np.nan,
    })
    all_long.append(long)

panel = pd.concat(all_long, ignore_index=True)
quality = pd.DataFrame(quality_rows)

# Drop impossible day numbers (e.g. day 30/31 in Feb) and out-of-range hours
def days_in_month(m):
    y, mo = map(int, m.split('-'))
    return calendar.monthrange(y, mo)[1]

panel['valid_day'] = panel.apply(lambda r: r['day'] <= days_in_month(r['month']), axis=1)
panel_clean = panel[panel['valid_day']].drop(columns='valid_day').copy()

# flag out-of-range hours (should be 0-24)
panel_clean['flag_out_of_range'] = ~panel_clean['hours'].between(0, 24) & panel_clean['hours'].notna()

panel_clean.to_csv(OUTPUT_DIR + 'benin_feeder_panel_FULL_apr2025_apr2026.csv', index=False)
quality.to_csv(OUTPUT_DIR + 'data_quality_summary.csv', index=False)

# ---------------------------------------------------------------------------
# Dataset B: consistent-coverage subset (all 23 feeders present every month)
# ---------------------------------------------------------------------------
coverage = panel_clean.groupby(['Feeder_norm', 'month']).size().unstack(fill_value=0)
months_all = sorted(panel_clean['month'].unique())
n_months = len(months_all)
fully_covered_feeders = coverage[(coverage > 0).sum(axis=1) == n_months].index.tolist()

# Determine which month-set gives full 23-feeder coverage (report both options)
month_options = {
    'oct2025_apr2026': ['2025-10','2025-11','2025-12','2026-01','2026-02','2026-03','2026-04'],
    'nov2025_apr2026': ['2025-11','2025-12','2026-01','2026-02','2026-03','2026-04'],
}

for label, months_subset in month_options.items():
    sub = panel_clean[panel_clean['month'].isin(months_subset)]
    cov_sub = sub.groupby('Feeder_norm')['month'].nunique()
    complete = cov_sub[cov_sub == len(months_subset)].index
    print(f"{label}: {len(complete)} of 23 feeders fully covered across {len(months_subset)} months")
    consistent_panel = sub[sub['Feeder_norm'].isin(complete)]
    consistent_panel.to_csv(OUTPUT_DIR + f'benin_feeder_panel_CONSISTENT_{label}.csv', index=False)

print("PANEL SHAPE:", panel_clean.shape)
print()
print("FEEDERS FOUND ACROSS ALL MONTHS:")
print(sorted(panel_clean['Feeder_norm'].unique()))
print()
print("MISSING FROM EXPECTED LIST:")
print(NORM_BENIN - set(panel_clean['Feeder_norm'].unique()))
print()
print("QUALITY SUMMARY:")
print(quality.to_string(index=False))
print()
print("OUT OF RANGE VALUES:", panel_clean['flag_out_of_range'].sum())
