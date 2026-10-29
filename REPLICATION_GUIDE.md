# Replication guide

This guide explains how to inspect the saved results, rebuild the thesis tables
and figures from them, and solve the model again. Run all commands in a separate
copy of the repository, so that new runs do not overwrite the saved results.

## 1. Inspect the saved results

```bash
git clone https://github.com/tbulesov-collab/honours-thesis.git
cd honours-thesis
python3 scripts/verify_replication_package.py
python3 scripts/check_saved_policy_tables.py
```

`verify_replication_package.py` confirms that the files match their recorded
SHA-256 hashes and that the Python and shell scripts parse. It does not compile
or run the model.

`check_saved_policy_tables.py` rebuilds the five policy columns of Table VIII
(`tab:joint_mechanism`) and its output decomposition from the saved reports in
`replication/validation/policy_table_inputs/`, and compares them with
`replication/validation/saved_comparison.json`. It also recomputes the gain from
removing the estate tax at fixed lifetime tax rates and the tie between the 9% and
10% wealth taxes at a 95% capital-income subsidy. It needs no solver files or
compiled programs. Add `--show-table` to print the rows.

After installing the dependencies in Section 2, rebuild the SCF table, the thesis
tables and the figure data from the repository root:

```bash
python3 scripts/rebuild_scf_audit.py --check
python3 scripts/check_thesis_results.py
python3 scripts/thesis_figures/make_thesis_figures.py --check-data
python3 scripts/thesis_figures/estate_incidence.py --model-root replication --check-data
python3 scripts/test_reproduction_portability.py --model-root replication
python3 scripts/test_marginal_run_map.py --model-root replication
```

The last two commands test the reproduction runner and the marginal-return run
mapping without solving the model.

[THESIS_RESULT_MAP.md](THESIS_RESULT_MAP.md) links each of the 20 tables and five
figures in the thesis to its data, code and commands.

### Where each result comes from

Paths in the last two columns are relative to `replication/`. Different
experiments use different benchmarks (saved, newly solved or recalibrated), so
compare numbers within an experiment. Each experiment folder's manifest and README
give its exact settings.

| Result | Driver or analysis code | Saved results |
| --- | --- | --- |
| 2022 SCF calibration targets and standard errors | `tools/build_scf_definition_bridge.py`, `tools/scf_2022_standard_errors.py` | `calibration/scf_2022_*.csv` |
| Audited SCF definitions (Table III), with fractional top-tail cutoffs within implicates | `../scripts/rebuild_scf_audit.py` | `calibration/scf_2022_definition_moments_audited.csv`; raw archives in `../data/scf2022/` |
| SCF and financing calibration stages | `tools/recalibrate_scf.py`, `tools/recalibrate_financing_2022.py` | `calibration/runs/scf_2022/best.json`, `calibration/runs/business_financing_2022/best.json` |
| Revenue-neutral reform and separate taxes | `tools/run_mac.sh`, `tools/rn_reform_tables.py` | `calibration/runs/business_financing_2022/rn_reform/` |
| Three-tax search and estate-fixed search | `tools/optimize_joint_taxes.py` varies all three rates; `tools/revalidate_headline_points_2022.py` re-solves the selected candidates | `calibration/runs/joint_tax_2022/`, `calibration/runs/joint_wealth_capital_2022/` |
| Fixed-labour candidate | `experiments/joint_tax_fixed_labor/` | its `results/` records; this candidate does not meet the strict revenue tolerance |
| Headline policies, re-solved at strict tolerances | `tools/revalidate_headline_points_2022.py` | `calibration/runs/headline_revalidation_2022/validated_headline.json` |
| Marginal returns and borrowing constraints (Table VII) | `experiments/marginal_returns_2022/extract_marginal_returns.py` | that folder's `results.json/.md` and the detailed marginal-return, constraint and asset reports for the seven policy runs |
| Five-policy comparison and output decomposition (Table VIII) | `../scripts/check_saved_policy_tables.py` | `validation/saved_comparison.json`, `validation/policy_table_inputs/` |
| Fine capital-tax grid and estate-tax sweep | `tools/policy_grid_2022.py` | `calibration/runs/okit_fine_grid_2022/`, `calibration/runs/estate_tax_grid_2022/` |
| Implementation sensitivity | `experiments/model_spec_sensitivity_2022/make_variants.py`, `run_sensitivity.py` | that folder's `results.json` and `results.md` |
| Recalibration | `experiments/model_spec_sensitivity_2022/recalibrate.py` | that folder's `recal_results.json` and `recal/` |
| Calibration parameter direction (Table XIV) | `experiments/model_spec_sensitivity_2022/flat_direction.py` | `flat/results.json/.md`, `flat/minus/`, `flat/plus/`, the saved Jacobian solves under `recal/control/solves/` and the results with a newly solved benchmark |
| Robustness summary (Table XV) | `experiments/table15_estate_2022/run_table15_estate.py` | that folder's `results.json`, `results.md` and `runs/points.json`, with context manifests and point records |
| Common grids, separate-policy re-optimisation and edge sweep | `experiments/policy_reoptimization_2022/reoptimize.py` | that folder's `results.json`, `runs/grid_points.json`, `runs/edge_points.json` |
| Misallocation and age–ability comparisons | `experiments/robustness_gkkoc_2022/misallocation_link.py`, `welfare_by_group.py` | that folder's matching JSON/Markdown records; `misallocation_link_sample.json` fixes the 118 evaluations used in the thesis (`--rescan --out DIR` uses every saved evaluation instead) |
| On-top wealth tax and looser credit | `experiments/robustness_gkkoc_2022/tier1.py` | `runs/side.json`, `runs/looser_policies.json`, `runs/looser_rbracket.json`, `tier1_results.md` |
| Larger subsidies and near-zero capital-income tax (Part B) | `experiments/robustness_gkkoc_2022/make_partb.py`, `partB.py` | `runs/partB_all.json`, `runs/partB_b4.json`, `partB_results.md` |
| Subsidies up to 95% without estate taxation (Part D) | `experiments/robustness_gkkoc_2022/partD.py` | `runs/partD_all.json`, `partD_results.md` |
| Constant borrowing limit (C6) | `experiments/robustness_gkkoc_2022/make_constant_theta.py`, `partC6.py` | `runs/c6_theta.json`, `runs/c6_policies.json`, `c6_results.md` |
| Higher markups (C7) | `experiments/robustness_gkkoc_2022/make_mu08.py`, `partC7.py` | `runs/c7/mu08/scf.json`, `runs/c7/mu08/financing.json`, `runs/c7_policies.json`, `c7_results.md` |
| Pure-rents variant (C5) | `experiments/robustness_gkkoc_2022/make_purerents.py`, `partC.py` | the `runs/purerents*` records; this variant has no market-clearing equilibrium and is not used in the thesis |
| Asset grids with 201, 301 and 401 points (Table XVI) | `experiments/grid_accuracy_2022/make_grid_variant.py`, `run_grid_check.py`, `make_guard_variant.py`, `run_extended_grid_check.py` | `results_na301.json`, `results_na401.json`, `results_extended.json`, frozen `variants/`, compact benchmark and policy `runs/`, including `points_extended.json` |

The thesis range for the estate-tax gain, 2.82–3.78 percentage points across seven
matched variants, includes the 3.78 result in `experiments/table15_estate_2022/`;
the comparison note at the end of that folder's `results.md` uses a narrower
reference range (2.82–3.75). Each estate-tax pair uses one benchmark; benchmarks
differ across variants.

The five-policy comparison includes the 7% wealth-tax and 50% subsidy policy with
a 40% estate tax, the same policy without the estate tax, and the 9% wealth-tax and
95% subsidy policy without estate taxation, which gives newborn CE2 of 31.01%.
Welfare is still rising at the 95% subsidy, so the saved results do not identify
an unrestricted joint optimum.

`replication/validation/` holds the saved inputs for the five-policy table and the
age–ability welfare records.

### Rebuild tables from saved reports

From the repository root, the marginal-return extractor writes a new summary
without solving the model:

```bash
python3 replication/experiments/marginal_returns_2022/extract_marginal_returns.py --out output/marginal_returns
```

The extractor reads 42 detailed reports across seven policy runs, plus their
output and rate records. It computes after-tax marginal returns from the
before-tax values, because the `After_Tax` field in the model reports leaves out
the subsidy under joint policies. By default it reads the bundled reports. For
new runs, copy
`replication/experiments/marginal_returns_2022/run_map.example.json` and replace
the seven run folders with the new model-relative directories. Then run:

```bash
python3 replication/experiments/marginal_returns_2022/extract_marginal_returns.py \
  --run-map /path/to/my_runs.json --out output/marginal_returns_fresh
```

The extractor confirms the policy IDs, tax rates and shared benchmark before
writing results, so changed cache names need no code edits.

The misallocation extractor also runs from the repository root and reads saved
reports only:

```bash
python3 replication/experiments/robustness_gkkoc_2022/misallocation_link.py --out output/misallocation
```

Its default sample is the 118 evaluations listed in
`misallocation_link_sample.json`, which is the sample used in Section 7.4.1.
The output should match the saved summary, including the overall correlation of
0.82688 (reported as 0.83). The optional `--rescan` mode uses every saved
evaluation and needs a separate `--out` folder; it does not reproduce the thesis
sample. Recorded paths are resolved inside the current copy of the repository.

From `replication/`, these commands show the parameter direction or rebuild
summaries from saved records. The two `--summary-only` commands rewrite summary
files in your copy; they do not solve the model.

```bash
python3 experiments/model_spec_sensitivity_2022/flat_direction.py --plan
python3 experiments/model_spec_sensitivity_2022/flat_direction.py --summary-only
python3 experiments/grid_accuracy_2022/run_extended_grid_check.py --summary-only
```

The parameter-direction comparison uses the saved Jacobian at the original
starting values, moves the thesis parameters by up to 10% along the locally
undetected direction and re-fits the financing parameter on each side. Its centre
uses a newly solved benchmark. The extended-grid results also use newly solved
benchmarks: their 201-point values are about 0.10 welfare points below the
headline values. The 9% and 10% wealth taxes remain tied on all three grids.
These results are separate from the seven variants in the robustness summary.

## 2. Dependencies and build

Use Python 3.10 or newer and install the numerical dependencies in a virtual
environment. GNU Fortran with OpenMP, GNU Make, Bash and Perl are used by the
macOS/Unix scripts. Windows versions of some scripts are also included.

```bash
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -r replication/requirements.txt
cd replication
bash tools/run_mac.sh build
```

`build` only compiles. The `make GKK_Main` target also runs the executable.
Build products are ignored by Git. The build uses `-ffp-contract=off` where the
scripts specify it; keep each variant's recorded flags, because compiler and
platform differences can change numerical results. The optional PDF-report
scripts need ReportLab and, where imported, PyMuPDF/Pillow; they are not needed to
solve the model.

The joint-search launch scripts use `python3` from PATH. To use a different
environment, set `PYTHON_BIN` to its Python executable; paths containing spaces
are supported.

## 3. Empirical inputs

The derived target CSVs, saved parameter files and the three official public
**2022** SCF archives are included. [data/scf2022/README.md](data/scf2022/README.md)
gives the source links, archive members and rebuild commands; `MANIFEST.json`
gives their exact sizes and SHA-256 hashes. The archives are included instead of
the much larger extracted Stata files.

From the repository root, `python3 scripts/rebuild_scf_audit.py --check` rebuilds
all seven audited SCF definitions directly from the archives and compares every
number with the saved CSV. These are the definitions in Table III. To write a
separate CSV, pass `--output PATH`.

The calibration targets and their standard errors are built by the
pooled-implicate scripts below. To run them, extract the archives in a separate
folder with `python3 -m zipfile -e ARCHIVE DIRECTORY`, then run these commands
from `replication/`, supplying the actual member paths and separate output files:

```bash
python3 tools/build_scf_definition_bridge.py \
  --summary-csv /path/to/SCFP2022.csv --full-dta /path/to/p22i6.dta \
  --output /path/to/rebuilt_bridge.csv
python3 tools/scf_2022_standard_errors.py \
  --summary-csv /path/to/SCFP2022.csv --full-dta /path/to/p22i6.dta \
  --replicate-dta /path/to/extracted_replicate_weights.dta \
  --output /path/to/rebuilt_standard_errors.csv
```

Use all five implicates and the replicate weights as the scripts specify.
`docs/SCF_2022_CALIBRATION.md` describes the empirical definitions; the percentile
statistics used in the thesis are in `calibration/runs/repaired_statistics_2022/`
(see `docs/PERCENTILE_STATISTICS.md`).

The financing calculation uses the saved observations in
`calibration/business_financing_2022.csv`: liabilities `FL144190005`, gross
nonfinancial stock issuance from Table 1.46 line 9 and nominal GDP `GDPA`, with
issuance capitalised at 5%. See `docs/BUSINESS_FINANCING_2022.md` and the source
links in that CSV. The online series may since have been revised; use the saved
observations to reproduce the reported calibration.

## 4. Solving the model again

### Benchmark and four main policies

From the repository root:

```bash
python3 scripts/reproduce_reported_2022.py --stage plan
python3 scripts/reproduce_reported_2022.py --stage build
# The following commands run the economic model and can take hours:
python3 scripts/reproduce_reported_2022.py --stage benchmark --threads 4
python3 scripts/reproduce_reported_2022.py --stage policies --threads 4
```

`--stage all` runs build, benchmark and policies together. The runner reads the
saved SCF parameter vector and financing parameter, confirms the hashes of the
model source, and works in a separate folder under
`replication/runtime/reproduction/reported_2022/`. It does not change the saved
results or need any files outside the repository. The build stage does not run
the model. The runner records compiler, source and calibration hashes and confirms
the complete benchmark state before reusing it. Use a new `--run-id NAME` when
inputs change or to keep an interrupted run.

The four policies are the separate wealth tax, the separate capital-income
subsidy, and the 7% wealth tax with a 50% subsidy, with estate taxes of 40% and
zero. `--policies anchor` also runs the unchanged benchmark tax system. Compare
the results with the saved values computed against a newly solved benchmark (the
**fresh-control** records), not with the headline values in the thesis, which use
the saved benchmark; the two differ by about 0.10 CE2 points. This runner does not
cover the calibration searches, the extended subsidy grids or the robustness
experiments.

### Full experiment sequence

The experiment drivers expect benchmarks at two fixed paths. In a separate copy of
the repository, prepare and install both from the repository root:

```bash
python3 scripts/reproduce_reported_2022.py --profile reported --stage benchmark --threads 4
python3 scripts/reproduce_reported_2022.py --profile reported --stage install-legacy --threads 4
python3 scripts/reproduce_reported_2022.py --profile theta2800 --stage benchmark --threads 4
python3 scripts/reproduce_reported_2022.py --profile theta2800 --stage install-legacy --threads 4
```

The reported profile uses the calibrated value of theta; the theta2800 profile
keeps the same entrepreneurial parameters and sets theta to 2.8. They use separate
folders. Installation confirms and copies the matching output **and** solver state
together. Existing folders at those paths are kept as
`*.before-fresh-<unique-id>`. Keep the same thread count and any explicit
`--run-id`/`--model-root` across the benchmark and installation commands. The
theta2800 profile cannot use the reported profile's four-policy reference values.

The remaining commands in this subsection run from `replication/`:

```bash
cd replication
```

Large `Bench_Files/` and experiment equilibrium states are not included. They are
solver outputs, not empirical inputs, and must be regenerated before the benchmark
can be read. The variant sources and build scripts are included; compiled programs
must be rebuilt on your machine.

The generic `tools/run_mac.sh bench-recompute` command uses the default parameter
vector and does not by itself reproduce the thesis calibration; the profile
commands above supply the thesis values. For policies under the reported
calibration, use the parameters in the saved SCF and financing `best.json` files
and the benchmark folder required by each driver. The environment overrides are
`GKK_RHO_Z`, `GKK_SIGMA_Z_EPS`, `GKK_X_HI`, `GKK_P1_X`, `GKK_P2_X`,
`GKK_THETA_MAX` and `GKK_RESULT_FOLDER`. See the numerical settings in each saved
context manifest. Running the calibration again is a separate recalibration and
need not retrace the original calibration path.

A fresh clone includes completion records but not the large solver files, so a
saved `result.json` does not mean that `Bench_Files/` is present. For full reruns,
use a separate copy with new run and cache folders, keep the saved parameter and
input files, and follow each experiment's order: benchmark, then build and
evaluation, then summary. Some saved manifests contain absolute paths from the
original machine; they record provenance and are not paths to use. Scripts with
fixed benchmark locations need the regenerated states at those locations.

The order is: the SCF and financing calibration (or the saved parameter vector),
the reported benchmark and reform, the separate policies, the joint searches and
headline policies, then implementation sensitivity and recalibration, the common
grids and the robustness experiments. Where supported, experiment scripts offer
`--check-only` or `--summary-only`; see each script's options. A `--check-only`
run can still require rebuilt programs, although it does not solve new policies.

The saved estate-fixed search and 40% estate-tax grid are kept as records. The
three-tax optimiser varies all three rates and does not retrace those searches;
`tools/revalidate_headline_points_2022.py` re-solves their selected candidates,
and the common-grid driver produces the reported and recalibrated comparisons.

For the revenue-neutral wealth-tax reform, keep the reported parameters and use
the installed benchmark. This writes new reform outputs in your copy:

```bash
GKK_RESULT_FOLDER=calibration/runs/business_financing_2022/rn_reform/ \
GKK_RHO_Z=0.1 GKK_SIGMA_Z_EPS=0.27830776649078415 \
GKK_X_HI=1.4620688061231504 GKK_P1_X=0.0502979531819958 \
GKK_P2_X=0.032874368735997382 GKK_THETA_MAX=2.9521292419330263 \
MODEL_DIR=calibration/runs/business_financing_2022/rn_reform THREADS=4 \
bash tools/reproduce_rn_reform.sh --skip-bench
```

The policy and robustness builds and drivers, in dependency order:

```bash
bash tools/run_mac.sh joint-build
bash experiments/joint_tax_fixed_labor/build_fixed_labor.sh
python3 tools/theta_max_robustness_2022.py
python3 tools/revalidate_headline_points_2022.py
python3 tools/policy_grid_2022.py --grid estate
python3 tools/policy_grid_2022.py --grid okit
python3 experiments/model_spec_sensitivity_2022/make_variants.py
python3 experiments/model_spec_sensitivity_2022/run_sensitivity.py --policies owt okit s5_1 s5_3 s5_4 benchmark_anchor
python3 experiments/model_spec_sensitivity_2022/recalibrate.py
python3 experiments/policy_reoptimization_2022/reoptimize.py --phase grid
python3 experiments/policy_reoptimization_2022/reoptimize.py --phase edge
python3 experiments/policy_reoptimization_2022/reoptimize.py --phase search
python3 experiments/three_tax_2022/run_three_tax.py --with-separate
python3 experiments/robustness_gkkoc_2022/make_rbracket.py
python3 experiments/robustness_gkkoc_2022/tier1.py
python3 experiments/robustness_gkkoc_2022/tier1.py --part rbracket
python3 experiments/robustness_gkkoc_2022/make_partb.py
python3 experiments/robustness_gkkoc_2022/partB.py
python3 experiments/robustness_gkkoc_2022/partD.py
python3 experiments/robustness_gkkoc_2022/make_constant_theta.py
python3 experiments/robustness_gkkoc_2022/partC6.py
python3 experiments/robustness_gkkoc_2022/make_mu08.py
python3 experiments/robustness_gkkoc_2022/partC7.py
python3 experiments/table15_estate_2022/run_table15_estate.py
python3 experiments/grid_accuracy_2022/make_grid_variant.py --na 301
python3 experiments/grid_accuracy_2022/run_grid_check.py --na 301
python3 experiments/grid_accuracy_2022/make_grid_variant.py --na 401 --no-reference
python3 experiments/grid_accuracy_2022/run_grid_check.py --na 401
python3 experiments/grid_accuracy_2022/make_guard_variant.py
python3 experiments/grid_accuracy_2022/run_extended_grid_check.py --max-parallel 2
python3 experiments/model_spec_sensitivity_2022/flat_direction.py --max-parallel 2
```

The 301-point build also creates the 201-point reference build. The extended-grid
driver needs the newly solved control benchmark and the 301- and 401-point
benchmarks; it does not solve them itself. Its 95% builds change only the subsidy
input limit and record the source hashes and patch. The parameter-direction driver
needs the control build and the Jacobian records from the recalibration; it
re-fits the financing parameter and evaluates both sides.

These commands compile variants and run long model computations. Memory and run
time grow with the number of solvers running at once; lower the parallel and
thread options in each driver for a smaller machine, and do not launch all
commands together. The robustness-summary driver (`run_table15_estate.py`) also
compares selected points with the saved reference values at a 0.01-point
tolerance. With a newly solved benchmark this comparison can print `NOT passed`
because of the roughly 0.10-point benchmark offset; the driver still reports the
newly computed results. Compare matched benchmarks and differences rather than
replacing the saved reference values.

## 5. Interpreting differences

Keep results computed against the saved benchmark separate from those computed
against a newly solved one; the two differ by about 0.1 welfare points. The
headline policies are solved with a distribution residual below `1e-7`, an
aggregate residual below `1e-6` and a relative revenue gap of at most `1e-4`.
These tolerances do not establish global optimality or a formal numerical error
bound. The asset-grid experiment measures sensitivity at 201, 301 and 401 nodes;
it does not establish convergence in the upper tail or Euler-equation accuracy.

The best tested joint policy is at the 95% subsidy limit, and welfare is still
rising there, so an unrestricted joint optimum is not identified. The fixed-labour
headline candidate does not meet the strict revenue tolerance. Transitions under
the joint policies are not computed. The pure-rents variant has no market-clearing
equilibrium and gives no policy result.
