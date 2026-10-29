# Joint revenue-neutral tax optimization

This experiment jointly chooses the flat annual wealth tax (`tauW_at`), the
capital-income tax (`tauK`), and the estate tax (`tau_bq`). The labor tax is the
residual fiscal instrument: at every candidate policy, the model iterates `psi`
until government revenue matches the SCF-plus-financing benchmark.

The objective is newborn CE2 welfare, matching the criterion used in the
one-dimensional OWT and OKIT searches. Structural parameters remain fixed at
the 2022 SCF calibration and `theta_max=2.9521292419330263`.

Run from the repository root:

```bash
THREADS=9 bash tools/run_joint_tax_optimization.sh
```

The default search uses a small differential-evolution stage followed by a
bounded Powell refinement. It is deliberately sequential because each model
process is memory intensive. Every completed candidate is cached under
`calibration/runs/joint_tax_2022/`; restarting the same command reuses those
results.

Default bounds are 0-6% for the wealth tax, -30% to 25% for the capital-income
tax, 0-80% for the estate tax, and 0-60% for the balancing labor tax. The final
summary is written to `calibration/runs/joint_tax_2022/best.json`, and all
feasible candidates are ranked in `all_results.csv`.

For a shorter diagnostic search:

```bash
THREADS=9 bash tools/run_joint_tax_optimization.sh \
  --global-generations 0 --population 3 --local-max-evals 12
```

This shorter run is useful for testing but should not be reported as a global
optimum. The full result should also be checked with tighter bounds and repeated
nearby evaluations because the simulated welfare surface is not perfectly
smooth.

## Boundary continuation

If a reported tax equals a search bound, it is a constrained solution rather
than a confirmed unconstrained optimum. Bounds and the initial vector can be
supplied as decimal rates. For example, the continuation after the first search
focuses on wealth taxes of 3.5-6.5%, capital taxes of -50% to -25%, and estate
taxes of 0-5%:

```bash
THREADS=9 bash tools/run_joint_tax_optimization.sh \
  --run-root calibration/runs/joint_tax_2022_extended \
  --tau-w-min 0.035 --tau-w-max 0.065 \
  --tau-k-min -0.50 --tau-k-max -0.25 \
  --tau-bq-min 0.0 --tau-bq-max 0.05 \
  --initial-tau-w 0.04909963880661732 \
  --initial-tau-k -0.30 \
  --initial-tau-bq 0.0011395892219886016 \
  --global-generations 3 --population 5 --local-max-evals 60
```

If the extended solution again reaches the capital-tax lower bound, extend it
again before interpreting the rate as optimal. A credible final optimum should
be interior in the capital-tax dimension, stable under tighter local searches,
and revenue-neutral at the requested tolerance. An estate-tax optimum of exactly
zero is economically interpretable even though it is a natural lower boundary.
