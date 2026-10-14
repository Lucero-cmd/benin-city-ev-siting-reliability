# Benin City EV Charging Site Reliability Screening

Reproducible data pipeline supporting the study *"A Reliability-Based Screening Framework for Fast Electric Vehicle Charging Site Selection in the Benin City Distribution Network, Nigeria."*

This repository contains the source data, processing scripts and output files needed to reproduce every numerical result in the paper, from the six monthly BEDC files for November 2025 to April 2026 through to the Reliability Index and the TOPSIS candidate site ranking.

## What this pipeline does

1. **Prepares the data** (paper Section 2.2). Combines the six monthly BEDC Band A feeder daily supply-hours files for November 2025 to April 2026 into a single dataset, keeps the 22 Benin City feeders in the study, and produces the data coverage summary in Table 1. BEDC's Band A records also cover Delta, Ondo and Ekiti States and other parts of Edo State, so this filtering step matters.
2. **Assesses reliability** (Sections 2.3 and 3.1 to 3.2). Computes per-feeder reliability metrics and an entropy-weighted composite Reliability Index, tied to the NERC Band A twenty-hour standard, with two robustness checks: the absolute daily minimum against the fifth percentile as the worst-case criterion, and entropy weighting against equal weighting.
3. **Screens candidate sites** (Sections 2.4 and 3.3 to 3.4). Ranks the feeders with TOPSIS, combining the Reliability Index with a commercial land-use indicator based on the BEDC feeder name and a reliability trend measure, followed by a weight sensitivity analysis.

## Feeders in the study

The study covers 22 Band A feeders in Benin City: Airport (Commercial), Akpakpava Commercial, Egor, Ekehuan Campus, Etete, Federal Secretariat Commercial, GRA, GRA 11, GRA Commercial, IDSL Commercial, Ihama, Ihovbor, Ikpoba-Hill-Commercial, Limit Road Commercial, MBH Commercial, Nekpenekpen, Oluku, Switching Station, Ugbor, Uniben, Uniben Commercial and Upper Lawani.

Each feeder was confirmed against the feeder location and major streets recorded by BEDC in the January to April 2026 files. Ujemen-Commercial is excluded because its recorded location is Ujemen and the streets it serves are in Ekpoma, outside Benin City.

## Repository structure

```
data/
  raw/           the six monthly BEDC CSV files used in the study (November 2025 to April 2026), unmodified
  raw/archive/   earlier monthly BEDC files (April to October 2025), kept for reference and not used in the analysis
  processed/     all output CSVs produced by the scripts
scripts/
  merge_bedc.py          Step 1: data preparation and data coverage summary
  reliability_index.py   Step 2: Reliability Index and robustness checks
  mcda_topsis.py         Step 3: TOPSIS candidate site screening and weight sensitivity analysis
```

## How to reproduce the results

Requirements: Python 3, `pandas`, `numpy`.

```bash
pip install pandas numpy
cd scripts
python3 merge_bedc.py        # reads data/raw/, writes the dataset and coverage summary to data/processed/
python3 reliability_index.py # writes the Reliability Index results and robustness checks
python3 mcda_topsis.py       # writes the TOPSIS ranking and weight sensitivity results
```

Each script resolves its input and output paths relative to its own location, so the pipeline runs correctly wherever the repository is cloned.

## Output files (in `data/processed/`)

| File | Description | Paper |
|---|---|---|
| `benin_feeder_panel_nov2025_apr2026.csv` | Daily supply hours for the 22 feeders, November 2025 to April 2026 (3,982 daily values) | Section 2.2 |
| `data_quality_summary.csv` | Feeders found and daily values recorded or missing, per month | Table 1 |
| `reliability_index_results.csv` | Reliability metrics and Reliability Index for each feeder | Table 2 |
| `reliability_index_weights.csv` | Entropy weights of the four criteria | Sections 2.3.2 and 3.2 |
| `reliability_index_worstcase_check.csv` | Entropy weights with the fifth percentile and with the absolute minimum as the worst-case criterion | Section 3.2 |
| `reliability_index_sensitivity_check.csv` | Entropy-weighted against equally weighted ranking | Section 3.2 |
| `reliability_monthly_means.csv` | Monthly mean supply hours per feeder (basis of the trend criterion) | Section 2.4.1 |
| `mcda_topsis_results.csv` | TOPSIS candidate site ranking under the base weights | Table 3 |
| `mcda_weight_sensitivity.csv` | Rankings under the five weighting schemes | Section 3.4 |

## Data source

BEDC Band A feeder daily supply-hours records, reported under the Nigerian Electricity Regulatory Commission (NERC) Service-Based Tariff framework and published by BEDC: https://beninelectric.com/band-a-feeders/

## Notes on data limitations

- The records contain only daily hours of supply. They contain no load, voltage or network topology data, so the pipeline produces a reliability and site-screening analysis only and does not include load-flow, voltage or network-loss analysis.
- A daily value is recorded for every feeder on every day of the study period. The monthly files carry a column for the 31st day, which is empty in 30-day months; these columns are dropped and are not counted as missing.
- The study period is six months, which does not cover a full wet and dry season cycle.
