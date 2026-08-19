"""
Section 4: Reliability Assessment
Computes per-feeder reliability metrics from the CONSISTENT Nov 2025 - Apr 2026 panel,
then builds a composite Reliability Index (RI) using entropy weighting.
"""
import pandas as pd
import numpy as np
import os

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(SCRIPT_DIR, "..", "data", "processed") + os.sep
os.makedirs(DATA_DIR, exist_ok=True)

panel = pd.read_csv(DATA_DIR + 'benin_feeder_panel_CONSISTENT_nov2025_apr2026.csv')

# Use the original (non-normalized) Feeder name for display, Feeder_norm as key
panel['hours'] = pd.to_numeric(panel['hours'], errors='coerce')

THRESHOLD_PRIMARY = 20.0  # NERC Service-Based Tariff Order (effective 3 April 2024): Band A minimum guaranteed supply, 20 hours/day
THRESHOLD_SECONDARY = 18.0  # NERC special compensation tier (Feb-Mar 2026 directive): feeders below 18 hrs/day flagged as severely underperforming while retaining Band A status

# ---------------------------------------------------------------------------
# 4.1 Per-feeder, per-month metrics, then aggregate to full-period metrics
# ---------------------------------------------------------------------------
def summarize(g):
    hours = g['hours'].dropna()
    n_days = len(g)
    n_valid = len(hours)
    return pd.Series({
        'n_days_recorded': n_days,
        'n_days_valid': n_valid,
        'mean_hours': hours.mean(),
        'std_hours': hours.std(),
        'min_hours': hours.min(),
        'p05_hours': hours.quantile(0.05),
        'max_hours': hours.max(),
        'pct_days_below_20h': 100 * (hours < THRESHOLD_PRIMARY).sum() / n_valid if n_valid else np.nan,
        'pct_days_below_18h': 100 * (hours < THRESHOLD_SECONDARY).sum() / n_valid if n_valid else np.nan,
    })

feeder_stats = panel.groupby(['Feeder_norm']).apply(summarize, include_groups=False).reset_index()
feeder_stats['cv'] = feeder_stats['std_hours'] / feeder_stats['mean_hours']

# Monthly means per feeder, for trend/seasonality view
monthly_means = panel.groupby(['Feeder_norm', 'month'])['hours'].mean().unstack()
monthly_means.to_csv(DATA_DIR + 'reliability_monthly_means.csv')

# ---------------------------------------------------------------------------
# 4.2 Composite Reliability Index (RI) via entropy weighting
# Criteria used (all derived from data in hand):
#   - mean_hours       (higher is better)
#   - cv               (lower is better -> invert)
#   - min_hours        (higher is better)
#   - pct_days_below_threshold (lower is better -> invert)
# ---------------------------------------------------------------------------
idx = feeder_stats.set_index('Feeder_norm')
criteria = pd.DataFrame({
    'mean_hours': idx['mean_hours'],
    'consistency': 1 / (1 + idx['cv']),          # transform CV so higher = more consistent
    'p05_hours': idx['p05_hours'],               # 5th percentile, worst-case exposure without one-day outlier dominance
    'reliability_days': 100 - idx['pct_days_below_20h'],  # NERC 20h/day standard, inverted so higher = better
})

# Min-max normalize each criterion to [0,1]
norm = (criteria - criteria.min()) / (criteria.max() - criteria.min())

# Entropy weighting
def entropy_weights(norm_df):
    # proportion matrix (avoid zero with tiny epsilon)
    eps = 1e-9
    P = (norm_df + eps) / (norm_df + eps).sum(axis=0)
    k = 1 / np.log(len(norm_df))
    E = -k * (P * np.log(P)).sum(axis=0)
    d = 1 - E  # degree of diversification
    w = d / d.sum()
    return w

weights = entropy_weights(norm)
print("Entropy-derived weights:")
print(weights)

RI = (norm * weights).sum(axis=1)
RI_normalized = 100 * (RI - RI.min()) / (RI.max() - RI.min())

result = criteria.copy()
result['pct_days_below_18h'] = idx['pct_days_below_18h']  # secondary NERC severe-underperformance tier, reported not weighted
result['RI_raw'] = RI
result['RI_0_100'] = RI_normalized
result = result.sort_values('RI_0_100', ascending=False)
result['rank'] = range(1, len(result) + 1)

result.to_csv(DATA_DIR + 'reliability_index_results.csv')
weights.to_csv(DATA_DIR + 'reliability_index_weights.csv', header=['weight'])

print()
print("RELIABILITY INDEX RANKING (entropy weights):")
print(result.round(2).to_string())

# ---------------------------------------------------------------------------
# 4.3 Sensitivity check: equal weighting vs entropy weighting
# ---------------------------------------------------------------------------
equal_w = pd.Series(1 / len(criteria.columns), index=criteria.columns)
RI_equal = (norm * equal_w).sum(axis=1)
RI_equal_0_100 = 100 * (RI_equal - RI_equal.min()) / (RI_equal.max() - RI_equal.min())

compare = pd.DataFrame({
    'RI_entropy_0_100': RI_normalized,
    'RI_equal_0_100': RI_equal_0_100,
})
compare['rank_entropy'] = compare['RI_entropy_0_100'].rank(ascending=False).astype(int)
compare['rank_equal'] = compare['RI_equal_0_100'].rank(ascending=False).astype(int)
compare['rank_change'] = compare['rank_equal'] - compare['rank_entropy']
compare = compare.sort_values('rank_entropy')

spearman = compare['RI_entropy_0_100'].corr(compare['RI_equal_0_100'], method='spearman')

compare.to_csv(DATA_DIR + 'reliability_index_sensitivity_check.csv')

print()
print("EQUAL WEIGHTS USED:")
print(equal_w)
print()
print("SENSITIVITY CHECK (entropy vs equal weighting):")
print(compare.round(2).to_string())
print()
print(f"Spearman rank correlation between the two weighting schemes: {spearman:.3f}")
print(f"Feeders with a rank change of 3 or more positions: {(compare['rank_change'].abs() >= 3).sum()} of {len(compare)}")
