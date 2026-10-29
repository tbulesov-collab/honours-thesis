# Model-specification sensitivity (results in results.md)

**Result:**

- The timing correction is negligible (≤ 0.01 pp).
- The productivity correction raises newborn CE2 by about 0.2 pp under both OWT and OKIT.
- The OWT−OKIT gap is unchanged (3.44 pp).
- The control's benchmark policy re-solves to 0.00%, which confirms the 0.1 pp offset of
  the saved benchmark.
- The OKIT points needed `GKK_DBN_MAX_ITER=2000`: at 700 iterations the aggregate residual
  was ~2.2e-6 against the 1e-6 limit.
- **Joint policies** (s5_1, s5_3, s5_4; control and productivity only):
  - The productivity correction adds +0.19 to +0.20 pp, the same as for the separate
    regimes.
  - The re-solve offset is 0.10 for each.
  - The ordering s5_4 > s5_3 > s5_1 holds; the grid-search gap is 0.037 in the control
    and 0.039 with the correction.
  - All six converged with `GKK_DBN_MAX_ITER=2000`: aggregate residual ≤ 9.9e-7.
  - To reproduce, add `--variants control productivity --policies s5_1 s5_3 s5_4`.
- The [thesis result map](../../../THESIS_RESULT_MAP.md) links these results to the
  thesis tables.

Measures how much two inherited differences between the GKKOC code and the published
model matter. Parameters are held at the financing calibration; nothing is recalibrated.

| Variant | Change (in a copy of the sources; the live sources are untouched) |
|---|---|
| `control` | none — the live code, benchmark solved from scratch |
| `productivity` | below-median ability types (nodes 1–4, z ≤ 1) start at base productivity `z`, not `z^x_hi` (GKKOC eq. 3) |
| `timing` | expectations at the last working age keep the current earnings shock, which fixes the pension `y_R(κ, e_{R−1})`; the distribution already does this |
| `both` | both corrections |

Not changed: the pension cap (code 1.10 against the paper's 1.13). It affects 1 of 25
worker types by 2–3% of their pension.

## Patches (`make_variants.py`)

- **productivity:** `INITIALIZE` in `programfunctions.f90` sets
  `xz_grid(1,1:4) = zgrid(1:4)` and `xz_grid(2,:) = z**x_lo`. A guard stops the build if
  `zgrid(4) ≠ 1`.
- **timing:** a new function `Pr_e_Next(age, e)` returns `pr_e(e,:)` for ages below
  RetAge−1, and "keep e" otherwise. It replaces `pr_e(e,:)` in the eight routines that
  take expectations of next period's earnings shock:
  - `FOC_WH`, `FOC_H_NSU`, `EGM_Working_Period`, `COMPUTE_VALUE_FUNCTION_LINEAR`,
    `Firm_Value`;
  - the three transition counterparts of the FOC and EGM routines.

  The expected replacement count is asserted for each routine.

## Run

From `replication/`:

```bash
python3 experiments/model_spec_sensitivity_2022/make_variants.py      # ~5–10 min
nohup caffeinate -i python3 experiments/model_spec_sensitivity_2022/run_sensitivity.py \
  > experiments/model_spec_sensitivity_2022/run.log 2>&1 &
```

- **Phase 1:** four benchmark solves in parallel (~1–1.5 h).
- **Phase 2:** nine policy evaluations, four at a time (~2.5–3 h). These are OWT and OKIT
  for each variant, plus the benchmark policy for the control.
- **Memory:** each solver needs about 3 GB. Lower `--max-parallel` if memory runs short.
- **Resume:** re-running the same command reuses finished benchmarks and cached policies.
- **Stopping:** check the running processes and stop both the driver and the solvers
  belonging to that run. Stopping only Python can leave solver processes running;
  confirm they have stopped before restarting or reusing the run directory.

## Re-calibration (option A, `recalibrate.py`)

**Result (`recal_results.md`):**

- All 10 policies converged.
- **Productivity fix after re-calibration:** +0.17 to +0.36 pp; no ranking changes.
- **Re-calibration itself** lowers newborn CE2 by 0.7–2.9 pp. The OWT−OKIT gap is
  2.97, down from 3.44.
- **The joint ranking reverses:** s5_1 > s5_4 > s5_3, by +0.45 pp, against s5_4 > s5_3 >
  s5_1 in the thesis. This happens at a fit (objective 244) no better than the thesis
  parameters (254).
- The policy rates were not re-optimised.

The runs above hold parameters at the thesis calibration. `recalibrate.py` instead
re-fits the parameters for the control and productivity code:

- it repeats the thesis SCF and financing steps with each arm's `bench.a`;
- it then evaluates OWT, OKIT, s5_1, s5_3 and s5_4 at the reported rates against each
  arm's own benchmark.

The control arm repeats the calibration with the control code, so both arms are
comparable.
Outputs are in `recal/`, plus `recal_results.{json,md}`. Re-running resumes the run.

```bash
nohup caffeinate -i python3 \
  experiments/model_spec_sensitivity_2022/recalibrate.py \
  > experiments/model_spec_sensitivity_2022/run_recal.log 2>&1 &
```

## Outputs

- `runs/<variant>/benchmark/` — solved benchmark (Bench_Files, output.txt, run.log,
  done.json).
- `runs/<variant>/policies/` — validated policy evaluations.
- `results.json`, `results.md` — summary; rebuild with `run_sensitivity.py --summary-only`.
- `variants/provenance.json` — source and executable hashes for each variant.
