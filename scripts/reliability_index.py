"""
Step 2: Reliability assessment (paper Sections 2.3 and 3.1 to 3.2)

Computes per-feeder reliability metrics from the November 2025 to April 2026
panel, builds the composite Reliability Index (RI) using entropy weighting, and
runs the two robustness checks described in Section 2.3.3:
  1. absolute daily minimum versus fifth percentile as the worst-case criterion;
  2. entropy weighting versus equal weighting (Spearman rank correlation).
"""
import pandas as pd
import numpy as np
import os

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(SCRIPT_DIR, "..", "data", "processed") + os.sep
os.makedirs(DATA_DIR, exist_ok=True)

panel = pd.read_csv(DATA_DIR + 'benin_feeder_panel_nov2025_apr2026.csv')

# Use the original (non-normalized) Feeder name for display, Feeder_norm as key
panel['hours'] = pd.to_numeric(panel['hours'], errors='coerce')

THRESHOLD_PRIMARY = 20.0  # NERC Order NERC/2025/046: Band A minimum supply, 20 hours/day
THRESHOLD_SECONDARY = 18.0  # NERC Order NERC/2025/046: lower threshold used in determining compensation for Band A feeders

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
# Criteria (all higher-is-better after transformation):
#   - mean_hours         mean daily supply hours
#   - consistency        1 / (1 + coefficient of variation)
#   - p05_hours          fifth percentile of daily supply hours (worst-case exposure)
#   - reliability_days   percentage of days meeting the 20-hour Band A standard
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

# ---------------------------------------------------------------------------
# Robustness check 1 (Section 2.3.3): worst-case criterion.
# Repeat the entropy weighting with the absolute daily minimum in place of the
# fifth percentile. Isolated single-day total outages inflate the spread of the
# minimum, so it takes a disproportionate share of the entropy weight.
# ---------------------------------------------------------------------------
criteria_min = criteria.drop(columns='p05_hours').assign(min_hours=idx['min_hours'])
criteria_min = criteria_min[['mean_hours', 'consistency', 'min_hours', 'reliability_days']]
norm_min = (criteria_min - criteria_min.min()) / (criteria_min.max() - criteria_min.min())
weights_min = entropy_weights(norm_min)
pd.DataFrame({'weight_with_p05': weights.rename({'p05_hours': 'worst_case'}),
              'weight_with_min': weights_min.rename({'min_hours': 'worst_case'})}
             ).to_csv(DATA_DIR + 'reliability_index_worstcase_check.csv')
print()
print("ROBUSTNESS CHECK 1: worst-case criterion")
print(f"  Weight of absolute minimum when used: {weights_min['min_hours']:.3f}")
print(f"  Weight of fifth percentile when used: {weights['p05_hours']:.3f}")

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
