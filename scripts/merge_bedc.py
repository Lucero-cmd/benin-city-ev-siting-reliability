"""
Step 1: Data preparation (paper Section 2.2)

Merges the six monthly BEDC Band A feeder daily supply-hours files for the study
period, November 2025 to April 2026, into one long panel:
Feeder x Month x Day x Supply Hours, filtered to the 22 Benin City feeders.

Also writes the data coverage and quality summary reported in Table 1 of the paper.
"""
import pandas as pd
import numpy as np
import re
import calendar
import os

# ---------------------------------------------------------------------------
# 1. Benin City feeders included in the study (22 feeders).
#    Each feeder was confirmed against the "Feeder Location" and
#    "Major Streets on Feeder" fields recorded by BEDC in the January to
#    April 2026 files.
# ---------------------------------------------------------------------------
BENIN_FEEDERS = {
    "AIRPORT (COMMERCIAL)", "AKPAKPAVA COMMERCIAL", "EGOR", "EKEHUAN CAMPUS",
    "ETETE", "FEDERAL SECRETARIAT COMMERCIAL", "GRA", "GRA 11", "GRA COMMERCIAL",
    "IDSL COMMERCIAL", "IHAMA", "IHOVBOR", "IKPOBA-HILL-COMMERCIAL",
    "LIMIT ROAD COMMERCIAL", "MBH COMMERCIAL", "NEKPENEKPEN", "OLUKU",
    "SWITCHING STATION", "UGBOR", "UNIBEN", "UNIBEN COMMERCIAL", "UPPER LAWANI",
}

# Ujemen-Commercial appears in the BEDC Benin Band A list, but its recorded
# location is Ujemen and the streets it serves are in Ekpoma, outside Benin
# City, so it is excluded.

def norm_name(x):
    if pd.isna(x):
        return ""
    return re.sub(r'\s+', ' ', str(x)).strip().upper()

NORM_BENIN = {norm_name(x) for x in BENIN_FEEDERS}

# Study period: the six months in which every study feeder is present.
# Earlier monthly files (April to October 2025) are kept in data/raw/archive/
# for reference and are not used in the analysis.
MONTHS = [
    ("BEDC_2NOVEMBER.csv", "2025-11"),
    ("BEDC_3December.csv", "2025-12"),
    ("BEDC_4January.csv", "2026-01"),
    ("BEDC_5February.csv", "2026-02"),
    ("BEDC_6March.csv", "2026-03"),
    ("BEDC_7April.csv", "2026-04"),
]

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
RAW_DIR = os.path.join(SCRIPT_DIR, "..", "data", "raw") + os.sep
OUTPUT_DIR = os.path.join(SCRIPT_DIR, "..", "data", "processed") + os.sep
os.makedirs(OUTPUT_DIR, exist_ok=True)

DAY_RE = re.compile(r'^\s*(\d{1,2})(st|nd|rd|th)\s*$', re.IGNORECASE)


def days_in_month(month_str):
    y, mo = map(int, month_str.split('-'))
    return calendar.monthrange(y, mo)[1]


def parse_month(path, month_str):
    """Read one monthly file and return the Benin City feeders in long format.

    The files carry a column for every day up to the 31st. For months with
    fewer days, the surplus day columns are empty and are dropped here, so they
    are not counted as missing values.
    """
    df = pd.read_csv(path, encoding='latin-1')
    df.columns = [str(c).strip() for c in df.columns]
    df = df.loc[:, ~df.columns.str.startswith('Unnamed')]
    n_days = days_in_month(month_str)
    day_cols = {}
    for c in df.columns:
        m = DAY_RE.match(c)
        if m and int(m.group(1)) <= n_days:
            day_cols[c] = int(m.group(1))
    sub = df[['Feeder'] + list(day_cols)].copy()
    sub['Feeder_norm'] = sub['Feeder'].apply(norm_name)
    sub = sub[sub['Feeder_norm'].isin(NORM_BENIN)]
    long = sub.melt(id_vars=['Feeder', 'Feeder_norm'], value_vars=list(day_cols),
                    var_name='day_col', value_name='hours')
    long['day'] = long['day_col'].map(day_cols)
    long['month'] = month_str
    long['hours'] = pd.to_numeric(long['hours'], errors='coerce')
    return long[['Feeder', 'Feeder_norm', 'month', 'day', 'hours']]


all_long, quality_rows = [], []
for fname, month_str in MONTHS:
    path = RAW_DIR + fname
    if not os.path.exists(path):
        raise FileNotFoundError(f"Could not find '{fname}' in {RAW_DIR}.")
    long = parse_month(path, month_str)
    found = set(long['Feeder_norm'].unique())
    n_missing = int(long['hours'].isna().sum())
    quality_rows.append({
        'month': month_str,
        'source_file': fname,
        'feeders_found': len(found),
        'feeders_expected': len(NORM_BENIN),
        'missing_feeder_names': ", ".join(sorted(NORM_BENIN - found)),
        'daily_values_recorded': len(long),
        'missing_or_nonnumeric': n_missing,
        'pct_missing': round(100 * n_missing / len(long), 1) if len(long) else np.nan,
    })
    all_long.append(long)

panel = pd.concat(all_long, ignore_index=True)
quality = pd.DataFrame(quality_rows)

# Every study feeder must be present in every month of the study period.
coverage = panel.groupby('Feeder_norm')['month'].nunique()
incomplete = coverage[coverage < len(MONTHS)]
assert incomplete.empty and len(coverage) == len(NORM_BENIN), \
    f"Feeders without full coverage: {sorted(set(NORM_BENIN) - set(coverage[coverage == len(MONTHS)].index))}"

panel['flag_out_of_range'] = ~panel['hours'].between(0, 24) & panel['hours'].notna()

panel.to_csv(OUTPUT_DIR + 'benin_feeder_panel_nov2025_apr2026.csv', index=False)
quality.to_csv(OUTPUT_DIR + 'data_quality_summary.csv', index=False)

print(f"PANEL: {panel['Feeder_norm'].nunique()} feeders, {len(MONTHS)} months, {len(panel)} daily values")
print()
print("DATA COVERAGE AND QUALITY (Table 1):")
print(quality.drop(columns=['source_file', 'missing_feeder_names']).to_string(index=False))
print()
print("TOTAL MISSING OR NON-NUMERIC:", int(panel['hours'].isna().sum()))
print("OUT-OF-RANGE VALUES (outside 0-24 h):", int(panel['flag_out_of_range'].sum()))
