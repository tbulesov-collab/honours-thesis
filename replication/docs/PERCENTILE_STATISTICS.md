# Wealth-percentile statistics

The percentile statistics are computed in `GKK_Stats.f90`.

## Definition

Wealth lies on a discrete grid, so a percentile can fall inside a bin with
positive population mass. The statistics allocate only the required fraction of
that bin. Every household state in the cutoff bin receives the same fraction,
which treats equal-wealth households symmetrically.

`PERCENTILE_BIN_WEIGHTS(mass, lower, upper)` takes ascending wealth-bin masses and
percentile endpoints in [0,1]. It returns inclusion fractions in [0,1], with
weighted population mass `(upper-lower)*sum(mass)`, up to floating-point rounding.
It handles empty bins, both endpoints in one bin, and non-unit total mass. It
rejects negative/non-finite masses, empty distributions and invalid endpoints.

## Statistics that use fractional cutoffs

- Entrepreneur population shares within the top 1%, top 10% and bottom 10%, for
  all six reported entrepreneur definitions.
- Entrepreneur wealth shares within the top 1% and top 10%, with the same
  fractional boundary in numerator and denominator.
- Top 1%, 0.1% and 0.01% wealth shares.
- Ability/state composition of wealth tails.
- Capital-income shares ranked by wealth.
- Returns within age-specific wealth-percentile intervals, so neighbouring
  intervals do not double-count a cutoff bin.
- Savings aggregates for the bottom 90%, next 9% and top 1%, using a partition
  that preserves total population and aggregates.

Population and wealth denominators are saved when the full distribution is
processed, before work arrays are reused for age-specific calculations.

## Output version and calibration caches

Benchmark and policy summaries contain `Statistics_Schema 3`. The SCF and
financing calibration drivers reject outputs without this statistics version.
The financing driver's theta=2.8 shortcut also requires the statistics version,
parameter vector and saved theta endpoint. Cached calibration moments are read
from the raw, versioned statistics. Policy-evaluation caches include the
statistics source in their context fingerprint.

## Build and tests

```bash
bash tools/run_mac.sh build
bash experiments/joint_tax_fixed_labor/build_fixed_labor.sh
python3 -m unittest discover -s tests -v
```

`build` keeps the current main-program mode. Statistics at a fixed parameter
vector can be recomputed from a completed benchmark state without solving a new
equilibrium; see `calibration/runs/repaired_statistics_2022/README.md`.
