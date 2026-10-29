# Thesis figure scripts

These scripts read saved results only; none runs the economic model.

| Script | Produces |
|---|---|
| `make_thesis_figures.py` | Welfare surface through a 95% subsidy, three-panel flat regions, estate-tax sweep and age-by-ability heat maps |
| `estate_incidence.py` | Estate-tax incidence table (`estate_incidence_table.tex`), alternative welfare measures and the estate-incidence heat maps |
| `estate_comparison.py` | Two-panel estate-tax comparison of newborn welfare and wealth concentration (`fig_estate_comparison.pdf/.png`), corresponding to the thesis's inline PGFPlots figure |

From the repository root:

```bash
python3 scripts/thesis_figures/make_thesis_figures.py --check-data   # load and check the saved results
python3 scripts/thesis_figures/make_thesis_figures.py                # write the figures
python3 scripts/thesis_figures/estate_incidence.py --model-root replication --check-data
python3 scripts/thesis_figures/estate_incidence.py --model-root replication
python3 scripts/thesis_figures/estate_comparison.py --check-data
python3 scripts/thesis_figures/estate_comparison.py
```

Outputs are written to `output/figures/`. Install the dependencies in `replication/requirements.txt` before generating figures. Each script checks its inputs against the values reported in the thesis before writing anything.

The welfare surface and flat-region comparisons include the Part D
results in `replication/experiments/robustness_gkkoc_2022/runs/partD_all.json`.
The flat-regions figure has three panels: the capital-income-tax plateau, the
wealth-tax hump at a 50% subsidy, and the corresponding comparisons at 80% and
95% subsidies. The highest tested newborn CE2 is 31.01% at a 9% wealth tax and
95% subsidy without estate taxation; the 10% wealth-tax point is treated as tied.
The `--check-data` commands inspect saved inputs without writing figures or
running the model. The generated figures remain local and are ignored by Git.
