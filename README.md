# Benin City EV Charging Site Reliability Screening

Reproducible data pipeline supporting the study *"A Reliability-Based Screening Framework for Fast Electric Vehicle Charging Site Selection in the Benin City Distribution Network, Nigeria."*

This repository contains the raw source data, processing scripts, and all intermediate/final output files needed to independently reproduce every numerical result in the paper, from the 13 raw monthly BEDC files through to the final Reliability Index and MCDA/TOPSIS candidate site rankings.

## What this pipeline does

1. **Harmonizes** 13 months of BEDC Band A feeder daily supply-hours records (April 2025 to April 2026), which arrive in three different, inconsistent column schemas, into a single clean panel.
2. **Filters** to 23 confirmed Benin City feeders (BEDC's coverage extends into Delta, Ondo, and Ekiti States, so this filtering step matters).
3. **Computes** a composite, entropy-weighted Reliability Index per feeder, tied to NERC's Service-Based Tariff Band A regulatory thresholds (20-hour and 18-hour daily supply minimums), with a robustness check against equal weighting.
4. **Screens** candidate feeders for fast EV charging site suitability using a TOPSIS multi-criteria ranking, combining the Reliability Index with a commercial land-use proxy and a reliability trend measure, with a weight-sensitivity analysis.

## Repository structure

```
data/
  raw/         13 original monthly BEDC CSV files, unmodified
  processed/   All intermediate and final output CSVs produced by the scripts
scripts/
  merge_bedc.py          Step 1: raw file harmonization and Benin City filtering
  reliability_index.py   Step 2: Reliability Index construction and robustness check
  mcda_topsis.py          Step 3: MCDA/TOPSIS candidate site screening and sensitivity analysis
```

## How to reproduce the results

Requirements: Python 3, `pandas`, `numpy`.

```bash
pip install pandas numpy
cd scripts
python3 merge_bedc.py        # reads data/raw/, writes panel + quality summary to data/processed/
python3 reliability_index.py # reads the panel, writes Reliability Index results to data/processed/
python3 mcda_topsis.py       # reads the Reliability Index, writes MCDA/TOPSIS results to data/processed/
```

Each script resolves its input and output paths relative to its own location, so the pipeline runs correctly regardless of where the repository is cloned.

## Key output files (in `data/processed/`)

| File | Description |
|---|---|
| `benin_feeder_panel_CONSISTENT_nov2025_apr2026.csv` | Primary panel used in the paper: 23 feeders, 6 months (Nov 2025-Apr 2026), no coverage gaps |
| `benin_feeder_panel_CONSISTENT_oct2025_apr2026.csv` | Alternative 7-month panel (22 of 23 feeders complete) |
| `benin_feeder_panel_FULL_apr2025_apr2026.csv` | Full 13-month extended panel with uneven feeder coverage |
| `data_quality_summary.csv` | Per-month schema type, feeder coverage, and missingness |
| `reliability_index_results.csv` | Full 23-feeder Reliability Index ranking |
| `reliability_index_weights.csv` | Entropy-derived criterion weights |
| `reliability_index_sensitivity_check.csv` | Entropy vs. equal-weighting robustness comparison |
| `reliability_monthly_means.csv` | Monthly mean supply hours per feeder (basis for the trend criterion) |
| `mcda_topsis_results.csv` | Full 23-feeder MCDA/TOPSIS candidate site ranking |
| `mcda_weight_sensitivity.csv` | Comparison across five alternative MCDA weighting schemes |

## Data source

Raw data is BEDC's (Benin Electricity Distribution Company) daily feeder supply-hours compliance records, reported under the Nigerian Electricity Regulatory Commission's (NERC) Service-Based Tariff framework for Band A feeders.

## Notes on data limitations

- Seven of the 23 confirmed Benin City feeders are absent from the April-September 2025 source files; one further feeder is absent from October 2025. Full 23-feeder coverage begins November 2025. See `data_quality_summary.csv` and the paper's Section 3 for full detail.
- Source files use three distinct column schemas across the study period; `merge_bedc.py` handles each explicitly rather than assuming a single format.
- This pipeline produces a reliability and site-screening analysis only. It does not include load-flow, voltage, or network-loss analysis, which would require distribution network topology data not available for this study.
