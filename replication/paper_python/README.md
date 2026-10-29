# Python Figures and Tables Pipeline

This folder replaces the MATLAB workflow with a reproducible Python pipeline.

## What it does now

- Parses model outputs from:
  - `Revision/Model_2.1_Local/output.txt`
  - `Revision/Model_2.1_Local/Tax_Reform/output_exp.txt`
  - `Revision/Model_2.1_Local/Tax_Reform/*.txt`
- Generates core tables (CSV + XLSX if `openpyxl` is installed):
  - `table_iii_moments_model.csv`
  - `table_iv_return_distribution.csv`
  - `table_v_macro_changes_tax_reform.csv`
  - `table_vi_welfare_tax_reform.csv`
  - `table_vii_welfare_by_group.csv`
  - `table_x_decomposition.csv`
  - `table_b3_welfare_distribution.csv`
- Attempts figure generation where inputs exist.
- Writes a machine-readable status file:
  - `paper_python/outputs/missing_inputs_report.csv`
  - `paper_python/outputs/paper_items_status.csv`

## Install

Install Python 3.10+ and packages:

```powershell
pip install -r paper_python/requirements.txt
```

## Run

From repo root:

```powershell
python paper_python/run_pipeline.py
```

Optional:

```powershell
python paper_python/run_pipeline.py --model-dir Revision/Model_2.1_Local --out-dir paper_python/outputs
```

## Notes

- Some paper figures/tables need additional runs/folders (e.g. optimal tax grids, Pareto simulation files).
- The pipeline reports missing dependencies explicitly instead of failing silently.
