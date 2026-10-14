"""
Step 3: Multi-criteria candidate site screening (paper Sections 2.4 and 3.3 to 3.4)

Combines the Reliability Index with two further criteria derived from the same
data and ranks the feeders with TOPSIS, then repeats the ranking under four
alternative weighting schemes (weight sensitivity analysis).

Criteria (all benefit criteria, higher is better):
  C1. Reliability Index (RI_0_100), from Step 2
  C2. Commercial land-use indicator: 1 if the BEDC feeder name designates it
      commercial, 0 otherwise
  C3. Reliability trend: slope of a least-squares line fitted to the six monthly
      mean supply hours (hours per day per month); positive = improving

The criteria weights (0.60, 0.25, 0.15) are assigned by the authors, not derived
from expert judgement; their basis is given in Section 2.4.2 of the paper and
their influence is tested by the weight sensitivity analysis.
"""
import pandas as pd
import numpy as np
import os

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(SCRIPT_DIR, "..", "data", "processed") + os.sep
os.makedirs(DATA_DIR, exist_ok=True)

ri = pd.read_csv(DATA_DIR + 'reliability_index_results.csv', index_col=0)
monthly = pd.read_csv(DATA_DIR + 'reliability_monthly_means.csv', index_col=0)

# ---------------------------------------------------------------------------
# C2: Commercial land-use indicator (from the BEDC feeder name)
# ---------------------------------------------------------------------------
ri['commercial_indicator'] = ri.index.to_series().apply(
    lambda x: 1 if 'COMMERCIAL' in x else 0
)

# ---------------------------------------------------------------------------
# C3: Reliability trend - slope of monthly mean hours, Nov 2025 to Apr 2026
# ---------------------------------------------------------------------------
month_order = ['2025-11', '2025-12', '2026-01', '2026-02', '2026-03', '2026-04']
monthly = monthly[month_order]
x = np.arange(len(month_order))

def slope(row):
    y = row.values.astype(float)
    if np.isnan(y).any():
        return np.nan
    return np.polyfit(x, y, 1)[0]

ri['trend_slope'] = monthly.apply(slope, axis=1)

# ---------------------------------------------------------------------------
# Assemble MCDA decision matrix
# ---------------------------------------------------------------------------
decision = pd.DataFrame({
    'RI': ri['RI_0_100'],
    'commercial_indicator': ri['commercial_indicator'],
    'trend_slope': ri['trend_slope'],
})

# Normalize (vector normalization, standard for TOPSIS)
norm_matrix = decision / np.sqrt((decision ** 2).sum())

# Assumed weights (Section 2.4.2). Basis:
#   RI weighted highest (0.6) since it is the paper's primary, data-grounded criterion
#   commercial_indicator given moderate weight (0.25) as a plausible but unvalidated indicator of demand
#   trend_slope given lowest weight (0.15) since 6 months is a short window for trend inference
WEIGHTS_ASSUMED = {'RI': 0.60, 'commercial_indicator': 0.25, 'trend_slope': 0.15}
w = pd.Series(WEIGHTS_ASSUMED)

weighted = norm_matrix * w

# Ideal best / worst (all criteria treated as benefit criteria, higher = better)
ideal_best = weighted.max()
ideal_worst = weighted.min()

dist_best = np.sqrt(((weighted - ideal_best) ** 2).sum(axis=1))
dist_worst = np.sqrt(((weighted - ideal_worst) ** 2).sum(axis=1))

closeness = dist_worst / (dist_best + dist_worst)

result = decision.copy()
result['topsis_closeness'] = closeness
result = result.sort_values('topsis_closeness', ascending=False)
result['final_rank'] = range(1, len(result) + 1)

result.to_csv(DATA_DIR + 'mcda_topsis_results.csv')

print("ASSUMED CRITERIA WEIGHTS (Section 2.4.2):")
print(w)
print()
print("MCDA / TOPSIS RANKING:")
print(result.round(3).to_string())

# ---------------------------------------------------------------------------
# Weight sensitivity analysis (Section 2.4.4): test alternative weighting schemes
# ---------------------------------------------------------------------------
def run_topsis(weights_dict):
    w_ = pd.Series(weights_dict)
    weighted_ = norm_matrix * w_
    ib = weighted_.max()
    iw = weighted_.min()
    db = np.sqrt(((weighted_ - ib) ** 2).sum(axis=1))
    dw = np.sqrt(((weighted_ - iw) ** 2).sum(axis=1))
    return dw / (db + dw)

schemes = {
    'base_RI60_comm25_trend15': {'RI': 0.60, 'commercial_indicator': 0.25, 'trend_slope': 0.15},
    'equal_thirds': {'RI': 1/3, 'commercial_indicator': 1/3, 'trend_slope': 1/3},
    'RI_dominant_80': {'RI': 0.80, 'commercial_indicator': 0.10, 'trend_slope': 0.10},
    'commercial_dominant': {'RI': 0.30, 'commercial_indicator': 0.55, 'trend_slope': 0.15},
    'trend_dominant': {'RI': 0.30, 'commercial_indicator': 0.15, 'trend_slope': 0.55},
}

closeness_table = pd.DataFrame({name: run_topsis(sw) for name, sw in schemes.items()})
rank_table = closeness_table.rank(ascending=False).astype(int)
rank_table.columns = [c + '_rank' for c in rank_table.columns]

sensitivity = pd.concat([closeness_table.round(3), rank_table], axis=1)
sensitivity = sensitivity.sort_values('base_RI60_comm25_trend15_rank')
sensitivity.to_csv(DATA_DIR + 'mcda_weight_sensitivity.csv')

# top-5 stability check
top5_sets = {name: set(rank_table[rank_table[name + '_rank'] <= 5].index) for name in schemes}
base_top5 = top5_sets['base_RI60_comm25_trend15']

print()
print("TOP-5 SHORTLIST UNDER EACH WEIGHTING SCHEME:")
for name, s in top5_sets.items():
    overlap = len(s & base_top5)
    print(f"  {name}: {sorted(s)}  (overlap with base scheme: {overlap}/5)")

# Spearman correlations vs base scheme
print()
print("SPEARMAN RANK CORRELATION vs base scheme:")
for name in schemes:
    if name == 'base_RI60_comm25_trend15':
        continue
    corr = rank_table['base_RI60_comm25_trend15_rank'].corr(rank_table[name + '_rank'], method='spearman')
    print(f"  {name}: {corr:.3f}")
