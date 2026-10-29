# Asset-grid accuracy check (thesis Appendix A.3)

Does refining the asset grid change the headline welfare comparisons? The experiment
covers seven policies on asset grids with 201, 301 and 401 points, with
corresponding distribution grids of 801, 1,201 and 1,601 points. Four headline policies
are evaluated by `run_grid_check.py`; `run_extended_grid_check.py` adds the no-estate-tax
8%/−80%, 9%/−95% and 10%/−95% policies. Each grid uses its own freshly solved benchmark.
The 201-point reference is the control variant in
`experiments/model_spec_sensitivity_2022`, reported in thesis Section 7.3.

| Policy | (τ_w, τ_k, τ_b) | Standard grid |
|---|---|---:|
| Separate wealth tax | (3.06%, 0, 40%) | 8.3912 |
| Separate capital-income subsidy | (0, −13.62%, 40%) | 4.9511 |
| Joint, estate tax 40% | (7%, −50%, 40%) | 19.7663 |
| Joint, no estate tax | (7%, −50%, 0) | 23.4398 |

**Comparison criteria:**
- every |fine − standard| is below 0.15 pp, the thesis tie threshold;
- the three robust rankings hold on the fine grid: the wealth tax beats the subsidy, both
  joint policies beat both separate ones, and removing the estate tax raises newborn CE2.

The first criterion is not met: newborn CE2 changes by up to 0.66 percentage points
for the four headline policies and 0.78 points for the extended policies between 201
and 401 points. The policy ordering remains unchanged, and the 9% and 10% wealth-tax
points at a 95% subsidy remain tied on every grid. Welfare rises along the tested
7%/−50%, 8%/−80% and 95%-subsidy combinations on all three grids. Benchmark moments
are compared as well. These are grid-sensitivity results, not a numerical error bound.

**Like for like:** the build copies the control sources (`variants/control/src`, verified
against that build's provenance), changes only the grid line in `parameters.f90` and uses
the same compiler commands. The procedure is the control's: financing calibration,
benchmark solved from scratch, the validated `PolicyEvaluator` and labour-tax adjustment.
The grid builds use the same sources and compiler (GCC 16.1.0) as the control build.

The default build also rebuilds the standard grid and reports whether its executables are
byte-identical to the control's.

## Run

From the model root (`replication/` in the exported repository), after preparing the
fresh control benchmark and policy results as described in the root
[replication guide](../../../REPLICATION_GUIDE.md). Use a disposable working copy:

```bash
python3 experiments/grid_accuracy_2022/make_grid_variant.py --dry-run
python3 experiments/grid_accuracy_2022/make_grid_variant.py        # ~10-20 min, two builds
python3 experiments/grid_accuracy_2022/run_grid_check.py --plan    # runs no executable
python3 experiments/grid_accuracy_2022/run_grid_check.py
python3 experiments/grid_accuracy_2022/make_grid_variant.py --na 401 --no-reference
python3 experiments/grid_accuracy_2022/run_grid_check.py --na 401
python3 experiments/grid_accuracy_2022/run_grid_check.py --summary-only
```

The default build also creates the 201-point reference build. Once the fresh control
benchmark and the 301-/401-point benchmarks and builds are ready, run the extension:

```bash
python3 experiments/grid_accuracy_2022/make_guard_variant.py
python3 experiments/grid_accuracy_2022/run_extended_grid_check.py --plan
python3 experiments/grid_accuracy_2022/run_extended_grid_check.py --max-parallel 2
python3 experiments/grid_accuracy_2022/run_extended_grid_check.py --summary-only
```

The guard variants change only the capital-income-tax input limit to −95%. The extended
driver does not solve benchmarks; all three complete benchmark states are required.
Both `--summary-only` commands rebuild summaries from saved records without solving
the model and write those summaries in the working copy.

- **Time:** on the standard grid the control took 29 minutes for the benchmark and 50–155
  minutes per policy, while other jobs were running. Expect roughly 1.5× per solve here:
  about 45–60 minutes for the benchmark, then four policies two at a time. In total, about
  5–8 hours.
- **Memory:** about 4–5 GB per solver at na = 301. `--max-parallel 3` is possible if
  nothing else heavy is running.
- **Resume:** re-running reuses complete benchmark states and validated cached policies.
  A saved `done.json` or summary alone does not replace the omitted equilibrium arrays.
- **Options:**
  - `--with-anchor` also re-solves the benchmark policy, as a self-check (CE2 ≈ 0).
  - `--na 401` (after `make_grid_variant.py --na 401 --no-reference`) checks an even finer grid.
- **Stopping:** check the running processes and stop both the driver and the solvers
  belonging to that run. Stopping only Python can leave solver processes running;
  confirm they have stopped before restarting or reusing the run directory.

## Outputs

- `variants/na<NA>/`: the builds and `provenance.json`.
- `runs/na<NA>/benchmark`, `runs/na<NA>/policies/v2_<context>/`: the solves.
- `results_na<NA>.md` / `.json`: the comparison and the checks.
- `variants/na<NA>_guard/`: extended-subsidy builds and provenance.
- `runs/na<NA>/policies_extended/`, `runs/na<NA>/points_extended.json`: extended solves.
- `results_extended.md` / `.json`: the three extended policies on all three grids.

The control's saved result tree is read as the reference; new grid results are written
under this experiment's directories.
