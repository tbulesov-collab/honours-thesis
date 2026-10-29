# Policy re-optimisation under the re-calibrated parameters

**Question.** Under the re-calibrated parameters
(`experiments/model_spec_sensitivity_2022/recal_results.md`), the three-tax candidate
overtook the estate-fixed candidates. That candidate has estate tax ~0 and the
capital-income subsidy at its −30% bound; the estate-fixed candidates have estate tax
40% and a subsidy near −50%.

Neither reported search could reach the region between them: estate tax near 0 *and* a
subsidy beyond −30%. The estate-tax sweep at the optimal wealth tax
(`calibration/runs/estate_tax_grid_2022`) raises newborn CE2 by ~1 point per 10 points
of estate tax removed, so that region is the most promising. This experiment:

1. maps it under both calibrations;
2. re-optimises under the re-calibrated one.

## Design (`reoptimize.py`)

**Phase 1: grids.** 62 evaluations, 2 at a time, ordered from the −50% subsidy
downwards.

| Calibration | Estate tax | Points |
|---|---|---|
| re-calibrated | 40% | the reported 18-point grid: τ_w {3,5,7}% × τ_k {0,−10,…,−50}% |
| re-calibrated | 0 | same 18 points |
| reported (saved benchmark) | 0 | same 18 points; the 40% grid is `calibration/runs/subsidy_cap_grid_2022` |
| re-calibrated | 40% | OWT sweep τ_w {2, 2.5, 3.5, 4}% and OKIT sweep τ_k {−22, −18, −10, −6}% |

**Phase 2: one wide search** under the re-calibrated parameters, all three taxes free.

- **Bounds:** τ_w 0–8%, τ_k −50% to +25% (−50% is the executable's guard), τ_b 0–80%.
- **Algorithm:** that of `tools/optimize_joint_taxes.py`, with its objective:
  - anchors;
  - differential evolution, 2 generations, population 4;
  - bounded Powell refinement, at most 45 evaluations.
- **Differences from the original:**
  - the global stage evaluates 2 candidates at once (`updating="deferred"`);
  - it starts from the best phase-1 point;
  - the anchors are the three best grid points, s5_1, s5_3, s5_4, OWT and OKIT.

**Settings.**

- **"re-calibrated"** is the control arm of `recalibrate.py`: its benchmark
  (`recal/control/solves/6063645eb5a8`) and parameters, with
  `variants/control/build/eval.a`, which is built from the live sources and checked
  against `provenance.json`.
- **"reported"** uses the same executable with the thesis calibration and the saved
  benchmark, so it compares directly with the reported grid.
- `GKK_DBN_MAX_ITER=2000`. Outputs go only under this folder. Re-running resumes from
  the evaluator cache.

## Run

```bash
nohup caffeinate -i python3 experiments/policy_reoptimization_2022/reoptimize.py \
  > experiments/policy_reoptimization_2022/run.log 2>&1 &
```

- `--phase grid` stops after phase 1.
- `--summary-only` rebuilds `results.md` at any time.
- Expected time: phase 1 ~1 day, phase 2 ~1–1.5 days.

## Outputs

- `runs/{recal,thesis,recal_search}/v2_*/` — evaluator caches.
- `runs/grid_points.json` — phase-1 results.
- `runs/search_best.json` — phase-2 best candidate.
- `results.md`, `results.json` — summary.
