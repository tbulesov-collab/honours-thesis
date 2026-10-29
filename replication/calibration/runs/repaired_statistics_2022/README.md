# Model wealth-percentile statistics

This folder holds the model's entrepreneur top-tail statistics and the
revenue-neutral reform's top-0.1% wealth shares, computed with fractional cutoff
bins (`Statistics_Schema 3`; see `docs/PERCENTILE_STATISTICS.md`). The thesis
uses these values for the model's percentile statistics in Table IV.

## Method (no equilibrium solve)

- `published_vector`, `scf_step`, `financing`: `GKK_Main.f90` with
  `Benchmark_Only=.true.` and `Tax_Reform_tktw=.false.`, built with the makefile
  flags and run with `GKK_RESULT_FOLDER` pointing at a folder whose `Bench_Files`
  links to the saved benchmark state. The environment for each run is in
  `summary.json`.
- `published_vector_original_test`: the same, but with the original GKKOC
  entrepreneur test in `GKK_Stats.f90`. It reproduces the original code's
  entrepreneur population share (7.0608%) and wealth share (38.5323%).
- The reform's tail shares come from `tail_shares.py`, a Python version of
  `PERCENTILE_BIN_WEIGHTS`, applied to the saved distributions.

## Results (entrepreneurs within the top 1% of wealth)

| State | Share |
|---|---:|
| Published vector, original test | 60.84% |
| Published vector, corrected test | 56.28% |
| SCF-only step | 57.11% |
| SCF + financing | 54.77% |

Revenue-neutral reform, top-0.1% wealth share: benchmark 22.15%, reform 29.13%.
