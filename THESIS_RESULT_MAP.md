# Thesis result map

This file links each of the 20 tables and five figures in the thesis, and a few results stated in the text, to the saved results, code and commands that reproduce them. Results are listed by their LaTeX label. `THESIS_RESULT_MAP.json` contains the same information in machine-readable form.

To recompute the reported table and figure values from the saved results, without solving the model, run from the repository root:

```bash
python3 scripts/check_thesis_results.py
```

Add `--json-output /path/to/report.json` to save the output. To rebuild the SCF definitions table from the bundled public archives, run `python3 scripts/rebuild_scf_audit.py --check`.

## Results

Paths are relative to the repository root, and each command states its working directory. Commands that build or solve the model need the benchmarks and inputs described in `REPLICATION_GUIDE.md`, and many take hours; run them in a separate copy of the repository. Values taken from the published paper and the original calibration targets are inputs, not results recomputed here.


### `tab:ext_params` — External parameters

- Inputs: `replication/parameters.f90`, `replication/GKK_Main.f90`.
- Code: `scripts/check_thesis_results.py`.
- How to reproduce: These are constants in the model source; nothing needs to be solved.
- Notes: The values are set in parameters.f90 and GKK_Main.f90; their empirical sources are cited in the thesis.

Repository root — recompute from saved results:

```bash
python3 scripts/check_thesis_results.py
```


### `tab:int_params` — Starting and staged parameter values

- Inputs: `replication/calibration/runs/scf_2022/best.json`, `replication/calibration/runs/business_financing_2022/best.json`, `replication/calibration/business_financing_2022.csv`.
- Code: `scripts/check_thesis_results.py`, `replication/tools/recalibrate_scf.py`, `replication/tools/recalibrate_financing_2022.py`.
- How to reproduce: The first command recomputes the table from the saved parameter files. The other two run the SCF and financing calibration stages after the model is built and the inputs are prepared (see REPLICATION_GUIDE.md).
- Notes: A new calibration run starts from the saved targets and need not follow exactly the same optimisation path.

Repository root — recompute from saved results:

```bash
python3 scripts/check_thesis_results.py
```

`replication/` — solve the model (slow):

```bash
python3 tools/recalibrate_scf.py
```

`replication/` — solve the model (slow):

```bash
python3 tools/recalibrate_financing_2022.py
```


### `tab:defn` — Audited SCF definitions and wealth per head

- Inputs: `replication/calibration/scf_2022_definition_moments_audited.csv`, `data/scf2022/MANIFEST.json`, `data/scf2022/scfp2022excel.zip`, `data/scf2022/scf2022s.zip`, `data/scf2022/scf2022rw1s.zip`, `data/scf2022/audit_reproduction_check.json`.
- Code: `scripts/check_thesis_results.py`, `scripts/rebuild_scf_audit.py`.
- How to reproduce: The first command rebuilds the SCF definitions from the bundled public archives. The second recomputes the four rows shown in the thesis and their wealth-per-head ratios.
- Notes: The rebuild covers all seven SCF definitions (28 numbers); four of them appear in the thesis table. The calibration targets and their standard errors are produced by separate scripts; see data/scf2022/README.md.

Repository root — rebuild from the SCF archives:

```bash
python3 scripts/rebuild_scf_audit.py --check
```

Repository root — recompute from saved results:

```bash
python3 scripts/check_thesis_results.py
```


### `tab:financing` — Benchmark and audited targets

- Inputs: `replication/calibration/runs/business_financing_2022/rn_reform/output.txt`, `replication/calibration/runs/repaired_statistics_2022/summary.json`, `replication/calibration/scf_2022_definition_moments_audited.csv`.
- Code: `scripts/check_thesis_results.py`, `replication/tools/recalibrate_financing_2022.py`.
- How to reproduce: The command recomputes the table from the saved benchmark report and percentile statistics. Solving it again requires the reported-calibration benchmark sequence in REPLICATION_GUIDE.md.
- Notes: The table combines aggregates from the saved benchmark with the percentile statistics in calibration/runs/repaired_statistics_2022/. Compare with the saved benchmark, not a newly solved one.

Repository root — recompute from saved results:

```bash
python3 scripts/check_thesis_results.py
```


### `tab:rn` — Revenue-neutral macro reform

- Inputs: `replication/calibration/runs/business_financing_2022/rn_reform/output.txt`, `replication/calibration/runs/business_financing_2022/rn_reform/Tax_Reform/output_exp.txt`.
- Code: `scripts/check_thesis_results.py`, `replication/tools/rn_reform_tables.py`, `replication/tools/reproduce_rn_reform.sh`.
- How to reproduce: Exports the table as CSV from the saved benchmark and reform reports. --model-dir is relative to replication/ and --out to the current directory. Solving it again uses the revenue-neutral reform commands in REPLICATION_GUIDE.md.
- Notes: The Guvenen et al. comparison column is taken from the published paper, not recomputed here.

Repository root — export the table from saved results:

```bash
python3 replication/tools/rn_reform_tables.py --model-dir calibration/runs/business_financing_2022/rn_reform --out output/tables/rn
```


### `tab:opt` — Separate tax policies

- Inputs: `replication/calibration/runs/headline_revalidation_2022/validated_headline.json`.
- Code: `scripts/check_thesis_results.py`, `replication/tools/revalidate_headline_points_2022.py`, `replication/tools/theta_max_robustness_2022.py`.
- How to reproduce: The first command recomputes the separate-policy rows from the saved results. The second solves the separate policies again after the benchmark and evaluator are rebuilt; the headline-policy driver reuses these results.
- Notes: The commands solve the selected policies; the search that selected them is not rerun.

Repository root — recompute from saved results:

```bash
python3 scripts/check_thesis_results.py
```

`replication/` — solve the model (slow):

```bash
python3 tools/theta_max_robustness_2022.py --arm financing --anchors owt,okit
```


### `tab:marginal_returns` — Marginal returns and borrowing constraints (Table VII)

- Inputs: `replication/experiments/marginal_returns_2022/results.json`, `replication/experiments/marginal_returns_2022/run_map.example.json`.
- Code: `scripts/check_thesis_results.py`, `replication/experiments/marginal_returns_2022/extract_marginal_returns.py`, `scripts/test_marginal_run_map.py`.
- How to reproduce: Re-extracts the table from the bundled detailed reports into output/marginal_returns without solving the model. The extractor reads seven policy runs and their benchmark reports, including the six policy rows shown in Table VII. For newly solved runs, copy run_map.example.json, replace its seven run folders (relative to replication/) and pass --run-map /path/to/my_runs.json.
- Notes: Marginal-return percentiles are wealth-weighted; constraint shares are population-weighted within each ability and productivity state. After-tax returns are computed from the Before_Tax reports, because the model's After_Tax report field leaves out the capital-income subsidy under joint policies. The 42 detailed reports are bundled at the paths the extractor expects.

Repository root — recompute from saved results:

```bash
python3 scripts/check_thesis_results.py
```

Repository root — export the table from saved results:

```bash
python3 replication/experiments/marginal_returns_2022/extract_marginal_returns.py --out output/marginal_returns
```


### `tab:joint_mechanism` — Five joint-policy columns and output accounting

- Inputs: `replication/validation/policy_table_inputs/index.json`, `replication/validation/saved_comparison.json`.
- Code: `scripts/check_saved_policy_tables.py`.
- How to reproduce: Rebuilds the five columns, sixteen rows and the output log-accounting identities from the saved reports. Solving the policies again uses the headline-policy, common-grid and Part D commands in REPLICATION_GUIDE.md.
- Notes: Add --show-table to print the rows.

Repository root — recompute from saved results:

```bash
python3 scripts/check_saved_policy_tables.py --show-table
```


### `tab:estate` — Separate-wealth-tax estate sweep

- Inputs: `replication/calibration/runs/estate_tax_grid_2022/grid_results.json`.
- Code: `scripts/check_thesis_results.py`, `replication/tools/policy_grid_2022.py`.
- How to reproduce: The first command recomputes the table from the saved results; the second solves the separate-wealth-tax estate sweep again after the benchmark and evaluator are prepared.
- Notes: Lifetime tax rates are held fixed across the sweep.

Repository root — recompute from saved results:

```bash
python3 scripts/check_thesis_results.py
```

`replication/` — solve the model (slow):

```bash
python3 tools/policy_grid_2022.py --grid estate
```


### `tab:estate_joint` — Joint-policy estate sweep

- Inputs: `replication/experiments/three_tax_2022/results.json`.
- Code: `scripts/check_thesis_results.py`, `replication/experiments/three_tax_2022/run_three_tax.py`.
- How to reproduce: The first command recomputes the table from the saved results; the second runs the estate phase of the three-tax driver after the benchmark and evaluator are prepared.
- Notes: All rows use the same lifetime tax rates and benchmark.

Repository root — recompute from saved results:

```bash
python3 scripts/check_thesis_results.py
```

`replication/` — solve the model (slow):

```bash
python3 experiments/three_tax_2022/run_three_tax.py --phase estate
```


### `tab:estate_decomposition` — Estate welfare decomposition

- Inputs: `replication/experiments/three_tax_2022/results.json`.
- Code: `scripts/check_thesis_results.py`, `replication/experiments/three_tax_2022/run_three_tax.py`.
- How to reproduce: The first command recomputes the table from the saved results; the second runs the decomposition phase of the three-tax driver after the benchmark and evaluator are prepared.
- Notes: The decomposition is multiplicative accounting of the welfare change, not a causal decomposition by channel.

Repository root — recompute from saved results:

```bash
python3 scripts/check_thesis_results.py
```

`replication/` — solve the model (slow):

```bash
python3 experiments/three_tax_2022/run_three_tax.py --phase decomp
```


### `tab:estate_measures` — Alternative welfare measures

- Inputs: `replication/calibration/runs/estate_tax_grid_2022/grid_results.json`, `replication/calibration/runs/headline_revalidation_2022/validated_headline.json`, `replication/experiments/policy_reoptimization_2022/runs/grid_points.json`.
- Code: `scripts/thesis_figures/estate_incidence.py`.
- How to reproduce: Create the output folder, then rebuild the table and figure from the saved results. The model is not solved.
- Notes: Group averages use the saved age-by-ability welfare changes and benchmark weights; transition welfare is not computed.

Repository root — create the output folder:

```bash
mkdir -p output/figures
```

Repository root — draw from saved results:

```bash
python3 scripts/thesis_figures/estate_incidence.py --model-root replication
```


### `tab:ch7_recal_parameters` — Recalibrated entrepreneurial parameters

- Inputs: `replication/experiments/model_spec_sensitivity_2022/recal_results.json`.
- Code: `scripts/check_thesis_results.py`, `replication/experiments/model_spec_sensitivity_2022/recalibrate.py`.
- How to reproduce: The first command recomputes the table from the saved parameters; the second runs the recalibration after its model variants and benchmark are prepared.
- Notes: A new recalibration run may follow a slightly different optimiser path on another platform.

Repository root — recompute from saved results:

```bash
python3 scripts/check_thesis_results.py
```

`replication/` — solve the model (slow):

```bash
python3 experiments/model_spec_sensitivity_2022/recalibrate.py
```


### `tab:parameter_direction` — Policy comparisons along the calibration parameter direction (Table XIV)

- Inputs: `replication/experiments/model_spec_sensitivity_2022/flat/results.json`, `replication/experiments/model_spec_sensitivity_2022/flat/minus/financing.json`, `replication/experiments/model_spec_sensitivity_2022/flat/plus/financing.json`, `replication/experiments/model_spec_sensitivity_2022/results.json`, `replication/calibration/runs/scf_2022/best.json`, `replication/calibration/runs/business_financing_2022/best.json`.
- Code: `scripts/check_thesis_results.py`, `replication/experiments/model_spec_sensitivity_2022/flat_direction.py`, `replication/experiments/model_spec_sensitivity_2022/recalibrate.py`.
- How to reproduce: --plan reconstructs the parameter direction from the saved Jacobian records (recal/control/solves) without running the model. --summary-only rewrites the summary from the saved financing and policy results. A full rerun needs the control build, the Jacobian records and a newly solved benchmark (see REPLICATION_GUIDE.md); it re-fits the financing parameter on each side and holds the capital-tax rates fixed.
- Notes: The largest proportional change in any parameter is 10%. The centre uses a newly solved benchmark, about 0.10 welfare points below the headline values. The weakest (third) direction is not evaluated. The saved results include some joint policies that support the ranking but are not shown in the table. This is a local comparison, not a test of global identification.

Repository root — recompute from saved results:

```bash
python3 scripts/check_thesis_results.py
```

`replication/` — show the plan:

```bash
python3 experiments/model_spec_sensitivity_2022/flat_direction.py --plan
```

`replication/` — rewrite the summary from saved results:

```bash
python3 experiments/model_spec_sensitivity_2022/flat_direction.py --summary-only
```

`replication/` — solve the model (slow):

```bash
python3 experiments/model_spec_sensitivity_2022/flat_direction.py --max-parallel 2
```


### `tab:ch7_robustness_summary` — Separate-policy and estate robustness

- Inputs: `replication/experiments/table15_estate_2022/results.json`, `replication/experiments/model_spec_sensitivity_2022/recal_results.json`, `replication/experiments/policy_reoptimization_2022/runs/grid_points.json`, `replication/experiments/robustness_gkkoc_2022/runs/looser_policies.json`, `replication/experiments/robustness_gkkoc_2022/runs/partB_all.json`, `replication/experiments/robustness_gkkoc_2022/runs/c6_policies.json`, `replication/experiments/robustness_gkkoc_2022/runs/c7_policies.json`, `replication/experiments/grid_accuracy_2022/results_na401.json`.
- Code: `scripts/check_thesis_results.py`, `replication/experiments/table15_estate_2022/run_table15_estate.py`, `replication/experiments/robustness_gkkoc_2022/tier1.py`, `replication/experiments/robustness_gkkoc_2022/partB.py`, `replication/experiments/robustness_gkkoc_2022/partC6.py`, `replication/experiments/robustness_gkkoc_2022/partC7.py`, `replication/experiments/grid_accuracy_2022/run_grid_check.py`.
- How to reproduce: Follow the experiment sequence in REPLICATION_GUIDE.md. Each matched pair uses its own benchmark.
- Notes: The table has eight comparisons: seven economic variants and a finer asset grid.

Repository root — recompute from saved results:

```bash
python3 scripts/check_thesis_results.py
```


### `tab:asset_grid_check` — Seven policies on three asset grids (Table XVI)

- Inputs: `replication/experiments/grid_accuracy_2022/results_na301.json`, `replication/experiments/grid_accuracy_2022/results_na401.json`, `replication/experiments/grid_accuracy_2022/runs/na301/points.json`, `replication/experiments/grid_accuracy_2022/runs/na401/points.json`, `replication/experiments/grid_accuracy_2022/variants/na301/provenance.json`, `replication/experiments/grid_accuracy_2022/variants/na401/provenance.json`, `replication/experiments/grid_accuracy_2022/results_extended.json`, `replication/experiments/grid_accuracy_2022/runs/na201/points_extended.json`, `replication/experiments/grid_accuracy_2022/variants/na201_guard/provenance.json`, `replication/experiments/grid_accuracy_2022/runs/na301/points_extended.json`, `replication/experiments/grid_accuracy_2022/variants/na301_guard/provenance.json`, `replication/experiments/grid_accuracy_2022/runs/na401/points_extended.json`, `replication/experiments/grid_accuracy_2022/variants/na401_guard/provenance.json`.
- Code: `scripts/check_thesis_results.py`, `replication/experiments/grid_accuracy_2022/make_grid_variant.py`, `replication/experiments/grid_accuracy_2022/run_grid_check.py`, `replication/experiments/grid_accuracy_2022/make_guard_variant.py`, `replication/experiments/grid_accuracy_2022/run_extended_grid_check.py`.
- How to reproduce: The first command recomputes the table from the saved results. The make/run pairs build and solve the 301- and 401-point benchmarks and the four main policies (the 301-point build also creates the 201-point reference build). make_guard_variant.py then builds evaluators that accept subsidies up to 95%, and run_extended_grid_check.py evaluates the three extended policies using the existing benchmarks. --summary-only rewrites the extended summary from the saved results without solving the model.
- Notes: The three extended-policy gains fall by 0.70–0.78 points from 201 to 401 nodes, and the 9% and 10% wealth-tax points stay tied. Their 201-point values use a newly solved benchmark and are about 0.10 points below the headline values. The only source change in the 95% builds is the subsidy input limit. These are finite-grid comparisons, not a formal error bound.

Repository root — recompute from saved results:

```bash
python3 scripts/check_thesis_results.py
```

`replication/` — build:

```bash
python3 experiments/grid_accuracy_2022/make_grid_variant.py --na 301
```

`replication/` — solve the model (slow):

```bash
python3 experiments/grid_accuracy_2022/run_grid_check.py --na 301
```

`replication/` — build:

```bash
python3 experiments/grid_accuracy_2022/make_grid_variant.py --na 401 --no-reference
```

`replication/` — solve the model (slow):

```bash
python3 experiments/grid_accuracy_2022/run_grid_check.py --na 401
```

`replication/` — build:

```bash
python3 experiments/grid_accuracy_2022/make_guard_variant.py
```

`replication/` — solve the model (slow):

```bash
python3 experiments/grid_accuracy_2022/run_extended_grid_check.py --max-parallel 2
```

`replication/` — rewrite the summary from saved results:

```bash
python3 experiments/grid_accuracy_2022/run_extended_grid_check.py --summary-only
```


### `tab:extended_subsidy_grid` — Extended subsidy grid

- Inputs: `replication/experiments/policy_reoptimization_2022/runs/grid_points.json`, `replication/experiments/policy_reoptimization_2022/runs/edge_points.json`, `replication/experiments/robustness_gkkoc_2022/runs/partB_all.json`, `replication/experiments/robustness_gkkoc_2022/runs/partD_all.json`.
- Code: `scripts/check_thesis_results.py`, `replication/experiments/policy_reoptimization_2022/reoptimize.py`, `replication/experiments/robustness_gkkoc_2022/partB.py`, `replication/experiments/robustness_gkkoc_2022/partD.py`.
- How to reproduce: The first command recomputes the table from the saved results; the four numerical commands solve the grid again, in order, after their benchmark and variant builds.
- Notes: Dashes mark points that were not evaluated. Welfare is still rising at the 95% subsidy, so the grid does not identify an unrestricted optimum.

Repository root — recompute from saved results:

```bash
python3 scripts/check_thesis_results.py
```

`replication/` — solve the model (slow):

```bash
python3 experiments/policy_reoptimization_2022/reoptimize.py --phase grid
```

`replication/` — solve the model (slow):

```bash
python3 experiments/policy_reoptimization_2022/reoptimize.py --phase edge
```

`replication/` — solve the model (slow):

```bash
python3 experiments/robustness_gkkoc_2022/partB.py
```

`replication/` — solve the model (slow):

```bash
python3 experiments/robustness_gkkoc_2022/partD.py
```


### `tab:ch7_fine` — Fine capital-tax grid

- Inputs: `replication/calibration/runs/okit_fine_grid_2022/grid_results.json`.
- Code: `scripts/check_thesis_results.py`, `replication/tools/policy_grid_2022.py`.
- How to reproduce: The first command recomputes the table from the saved results; the second evaluates the ten-rate capital-tax grid after the benchmark and evaluator are prepared.
- Notes: The flat region is assessed on a finite grid.

Repository root — recompute from saved results:

```bash
python3 scripts/check_thesis_results.py
```

`replication/` — solve the model (slow):

```bash
python3 tools/policy_grid_2022.py --grid okit
```


### `tab:ch7_recal_capital` — Recalibrated capital-tax sweep

- Inputs: `replication/experiments/policy_reoptimization_2022/results.json`, `replication/experiments/model_spec_sensitivity_2022/recal_results.json`.
- Code: `scripts/check_thesis_results.py`, `replication/experiments/policy_reoptimization_2022/reoptimize.py`.
- How to reproduce: The first command recomputes the table from the saved results. The recalibrated capital-tax sweep is part of the grid phase of reoptimize.py; its search phase is a separate joint-policy optimisation. Prepare the recalibrated benchmark and evaluator first.
- Notes: Welfare levels are relative to the recalibrated benchmark and are not compared across benchmarks.

Repository root — recompute from saved results:

```bash
python3 scripts/check_thesis_results.py
```

`replication/` — solve the model (slow):

```bash
python3 experiments/policy_reoptimization_2022/reoptimize.py --phase grid
```


### `tab:model_conventions` — Implementation conventions and sensitivity

- Inputs: `replication/experiments/model_spec_sensitivity_2022/results.json`, `replication/experiments/model_spec_sensitivity_2022/recal_results.json`, `replication/experiments/grid_accuracy_2022/results_na401.json`.
- Code: `scripts/check_thesis_results.py`, `replication/experiments/model_spec_sensitivity_2022/make_variants.py`, `replication/experiments/model_spec_sensitivity_2022/run_sensitivity.py`.
- How to reproduce: The first command recomputes the table from the saved results; the build and run commands solve the implementation variants. The asset-grid row uses the asset-grid commands listed under Table XVI.
- Notes: The borrowing-index and pension-cap rows are not evaluated numerically.

Repository root — recompute from saved results:

```bash
python3 scripts/check_thesis_results.py
```

`replication/` — build:

```bash
python3 experiments/model_spec_sensitivity_2022/make_variants.py
```

`replication/` — solve the model (slow):

```bash
python3 experiments/model_spec_sensitivity_2022/run_sensitivity.py
```


### `fig:surface` — Joint welfare surface

- Inputs: `replication/experiments/policy_reoptimization_2022/runs/grid_points.json`, `replication/experiments/robustness_gkkoc_2022/runs/partB_all.json`, `replication/experiments/robustness_gkkoc_2022/runs/partD_all.json`.
- Code: `scripts/thesis_figures/make_thesis_figures.py`.
- How to reproduce: Draws the figure from the saved results; the model is not run.
- Notes: Points come from the saved policy grids; the headline rankings use the re-solved headline policies. Connecting lines are visual guides.

Repository root — draw from saved results:

```bash
python3 scripts/thesis_figures/make_thesis_figures.py --only surface
```


### `fig:estate` — Estate comparison under separate and joint taxes

- Inputs: `replication/calibration/runs/estate_tax_grid_2022/grid_results.json`, `replication/experiments/three_tax_2022/results.json`.
- Code: `scripts/thesis_figures/estate_comparison.py`.
- How to reproduce: Draws both panels from the saved results; the model is not run.
- Notes: The thesis draws this figure with PGFPlots; the script produces an equivalent standalone version.

Repository root — draw from saved results:

```bash
python3 scripts/thesis_figures/estate_comparison.py
```


### `fig:groups` — Age-by-ability welfare heat maps

- Inputs: `replication/experiments/robustness_gkkoc_2022/welfare_by_group.json`.
- Code: `scripts/thesis_figures/make_thesis_figures.py`, `replication/experiments/robustness_gkkoc_2022/welfare_by_group.py`.
- How to reproduce: Draws the figure from the saved results; the model is not run.
- Notes: Values are stationary consumption-equivalent changes by age and ability using benchmark weights, not effects along a transition.

Repository root — draw from saved results:

```bash
python3 scripts/thesis_figures/make_thesis_figures.py --only groups
```


### `fig:estate_incidence` — Effect of estate removal by group

- Inputs: `replication/calibration/runs/estate_tax_grid_2022/grid_results.json`, `replication/calibration/runs/headline_revalidation_2022/validated_headline.json`, `replication/experiments/policy_reoptimization_2022/runs/grid_points.json`.
- Code: `scripts/thesis_figures/estate_incidence.py`.
- How to reproduce: Create the output folder, then rebuild the table and figure from the saved results. The model is not solved.
- Notes: Each value is the difference between two benchmark-relative welfare changes, not the compensation needed to move between the two policies.

Repository root — create the output folder:

```bash
mkdir -p output/figures
```

Repository root — draw from saved results:

```bash
python3 scripts/thesis_figures/estate_incidence.py --model-root replication
```


### `fig:flat` — Flat welfare regions

- Inputs: `replication/calibration/runs/okit_fine_grid_2022/grid_results.json`, `replication/experiments/policy_reoptimization_2022/runs/edge_points.json`, `replication/experiments/robustness_gkkoc_2022/runs/partD_all.json`.
- Code: `scripts/thesis_figures/make_thesis_figures.py`.
- How to reproduce: Draws the figure from the saved results; the model is not run.
- Notes: Finite policy grids and the 0.15-point reporting threshold do not establish a global optimum.

Repository root — draw from saved results:

```bash
python3 scripts/thesis_figures/make_thesis_figures.py --only flat
```


### `sec:groups-household-mechanism` — After-tax wage and top-ability returns

- Inputs: `replication/experiments/three_tax_2022/results.json`, `replication/GKK_Stats.f90`.
- Code: `scripts/check_thesis_results.py`.
- How to reproduce: Recomputes the wage and return figures in the text from the saved results; the joint-policy estate commands regenerate the underlying reports.
- Notes: Recomputes the 2.58% after-tax wage increase and reads ability 9's mean return (14.53% to 14.29%) from the Mean_Return_by_z rows. These are stationary averages and include composition changes.

Repository root — recompute from saved results:

```bash
python3 scripts/check_thesis_results.py
```


### `sec:return_mechanism` — Break-even returns

- Inputs: `replication/validation/saved_comparison.json`.
- Code: `scripts/check_thesis_results.py`.
- How to reproduce: Recomputes the break-even returns from the saved tax rates: the wealth-tax rate divided by the absolute subsidy rate.
- Notes: This is algebra at the stated rates, not an estimated behavioural response.

Repository root — recompute from saved results:

```bash
python3 scripts/check_thesis_results.py
```


### `sec:gkkoc_robustness-additional` — Implementation, on-top wealth tax and misallocation results in the text

- Inputs: `replication/experiments/model_spec_sensitivity_2022/results.json`, `replication/experiments/robustness_gkkoc_2022/runs/side.json`, `replication/experiments/robustness_gkkoc_2022/misallocation_link.json`, `replication/experiments/robustness_gkkoc_2022/misallocation_link_sample.json`.
- Code: `scripts/check_thesis_results.py`, `replication/experiments/robustness_gkkoc_2022/tier1.py`, `replication/experiments/robustness_gkkoc_2022/misallocation_link.py`.
- How to reproduce: The first command recomputes the figures in the text from the saved results. tier1.py solves the on-top wealth tax and looser-credit cases again after its variants and benchmark are prepared. misallocation_link.py rebuilds the 118 correlation observations from the fixed sample. The implementation sensitivities use the commands listed under Table XX.
- Notes: Covers the four on-top wealth-tax cases, the implementation effects and the correlations across all 118 saved evaluations. The fixed-labour cases use a different fiscal closure by design; correlations do not identify causal channels.

Repository root — recompute from saved results:

```bash
python3 scripts/check_thesis_results.py
```

`replication/` — solve the model (slow):

```bash
python3 experiments/robustness_gkkoc_2022/tier1.py
```
