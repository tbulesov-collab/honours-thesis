# 2022 SCF calibration moments

The updated SCF moments are stored in
`calibration/scf_2022_moments.csv`. The two rows marked `target` replace
the SCF-derived moments used to discipline entrepreneurial productivity:

| Moment | Original | 2022 SCF |
| --- | ---: | ---: |
| Entrepreneurs among the wealthiest 1% | 65.0% | 64.45% |
| Wealth held by entrepreneurs | 41.6% | 44.96% |

The file also records the entrepreneur population share, top wealth shares,
and wealth Gini as validation or cross-check moments. The top 1% SCF estimate
does not automatically replace the model's 36% target because the paper
sources that target from Vermeulen (2018), not Cagetti and De Nardi's SCF
statistics.

## Definitions and calculation

- Data: Federal Reserve 2022 Survey of Consumer Finances public files.
- Entrepreneur: the family reports an active management role in a privately
  held business (`X3104=1`), matching Cagetti and De Nardi's definition.
- Wealth: `NETWORTH` from the Federal Reserve summary extract.
- Weights: `WGT`, which the Federal Reserve defines as `X42001/5` so all five
  implicates can be pooled.
- Entrepreneur prevalence within the top 1% uses the Federal Reserve's
  `NWPCTLECAT=12` category. The standalone top wealth shares rank families by
  `NETWORTH` and split boundary weights so the groups contain exactly 1% or
  0.1% of weighted families.
- The reported estimates average over the five implicates. Replicate-weight
  sampling standard errors are not included.

## Compare with the current benchmark

From the project root, run:

```bash
python3 tools/compare_scf_moments.py
```

The model counterpart uses the paper's definition of an entrepreneur: more
than 50% of before-tax income comes from business profits. Consequently, the
SCF and model definitions are conceptually aligned but not literally identical.

## Definition bridge and model-statistics correction

The public code originally omitted parentheses around the complete business-income
numerator in six entrepreneur tests. It evaluated `business capital return +
profits/total income`, although the comments and paper describe `(business capital
return + profits)/total income`. The corrected formula changes only reported
entrepreneur classifications; aggregate equilibrium results are unchanged to numerical
precision. At the published parameter vector, the corrected model reports:

| Model moment | Original-code statistic | Corrected statistic |
|---|---:|---:|
| Entrepreneurs among top 1% | 67.87% | 62.41% |
| Entrepreneur wealth share | 38.53% | 33.03% |
| Entrepreneur population share | 7.06% | 6.32% |

The Federal Reserve files allow several defensible empirical definitions. Their results
are versioned in `calibration/scf_2022_definition_bridge.csv`:

| 2022 SCF definition | Population | Wealth | Entrepreneurs in top 1% |
|---|---:|---:|---:|
| Active manager (`X3104=1`; paper continuity) | 13.09% | 44.96% | 64.45% |
| Business majority of model-comparable income flows | 6.71% | 24.33% | 39.84% |
| Active manager and business-income majority | 4.03% | 21.12% | 33.60% |
| Business majority of total SCF income | 5.85% | 20.51% | 34.36% |

The first row remains the headline calibration target because it updates the paper's
empirical definition. The other rows are specification sensitivities. They should not be
silently substituted: doing so reverses the diagnosis from “too little entrepreneur
wealth” to “too much concentration among income-defined entrepreneurs.” Rebuild the
table from the official files with:

```bash
python3 tools/build_scf_definition_bridge.py \
  --summary-csv /path/to/SCFP2022.csv \
  --full-dta /path/to/p22i6.dta
```

The income-aligned sensitivity targets are stored separately in
`calibration/scf_2022_moments_income_aligned.csv`; the headline file is not overwritten.

At the corrected published parameter vector, the definition choice produces opposite
calibration residuals:

| Target specification | Top-1 entrepreneur gap | Entrepreneur-wealth gap | Three-moment objective |
|---|---:|---:|---:|
| Active manager (paper continuity) | -2.03 pp | -11.93 pp | 147.22 |
| Business-income majority (income aligned) | +22.57 pp | +8.70 pp | 585.86 |

The third fitted moment is the paper's 36% top-1 wealth-share target; its gap is
-0.82 pp under both specifications. This divergence is why a single new parameter
vector is not treated as the next baseline automatically.

## Staged recalibration

The paper jointly fits the entrepreneurial process parameters to five moments. The
local driver holds the directly identified intergenerational persistence at
`rho_z=0.1`, preserves the paper's 36% top-1% wealth target, and updates the two SCF
entrepreneurship targets. It estimates finite-difference sensitivities for
`sigma_z_eps`, `x_hi` (the paper's fast-lane productivity boost), `p1_x`, and `p2_x`,
then takes a regularized minimum-change Gauss-Newton step. Each candidate is cached
under `calibration/runs/scf_2022/`; the published benchmark is not overwritten.

On macOS, run:

```bash
python3 tools/recalibrate_scf.py --threads 4 --iterations 1
```

Benchmark the corrected published parameters against both empirical definitions before
launching a search:

```bash
python3 tools/recalibrate_scf.py \
  --threads 4 --iterations 0 --skip-build

python3 tools/recalibrate_scf.py \
  --threads 4 --iterations 0 --skip-build \
  --targets calibration/scf_2022_moments_income_aligned.csv
```

Custom target files receive their own `best.<target-stem>.json` summary, preventing a
result optimized for one entrepreneur definition from being mistaken for the other.

One iteration requires the baseline, four finite-difference runs, and one or two
candidate runs. The paper's self-made-billionaire target is retained as a final
validation rather than included in this staged search: the supplied simulation uses
20 million agents for 5,000 periods and is not practical inside every local-search
evaluation.

### Corrected one-step robustness results

One local-search iteration was completed for each definition. These are specification
results, not replacements for the published defaults:

| Parameter | Published | Active-manager targets | Income-aligned targets |
|---|---:|---:|---:|
| `sigma_z_eps` | 0.277000 | 0.278308 | 0.262713 |
| `x_hi` | 1.500000 | 1.462069 | 1.815338 |
| `p1_x` | 0.050000 | 0.050298 | 0.049440 |
| `p2_x` | 0.030000 | 0.032874 | 0.022869 |

| Search result | Baseline | After one step |
|---|---:|---:|
| Active-manager objective | 147.22 | 121.57 |
| Active-manager: top-1 entrepreneur gap | -2.03 pp | +0.16 pp |
| Active-manager: entrepreneur-wealth gap | -11.93 pp | -11.02 pp |
| Income-aligned objective | 585.86 | 184.16 |
| Income-aligned: top-1 entrepreneur gap | +22.57 pp | +9.30 pp |
| Income-aligned: entrepreneur-wealth gap | +8.70 pp | +7.03 pp |

The active-manager step fits the 36% top-1 wealth target to -0.10 pp and the top-1
entrepreneur target to +0.16 pp, but barely changes the entrepreneur-wealth shortfall.
The income-aligned step reduces its entrepreneur gaps substantially but raises the model
top-1 wealth share to 42.95% and top-0.1 share to 32.37%. This is a strong warning that
the four-parameter local update does not jointly resolve the definition sensitivity or
the upper-tail validation moments.
