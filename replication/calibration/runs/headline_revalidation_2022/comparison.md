# Headline points under the validated evaluator

Every validated value satisfies: equilibrium residual < 1e-7, aggregate residual < 1e-6, iteration count within the cap, tax rates and benchmark revenue verified.

| Point | Reported CE2 | Validated CE2 | Change | Labour tax | Revenue gap | Feasible | Status |
|---|---:|---:|---:|---:|---:|---|---|
| Optimal wealth tax (Table VII) | 8.5089 | 8.4913 | -0.0176 | 0.1538 | 6.02e-05 | yes | reused from theta_max_robustness_2022 |
| Optimal capital-income tax (Table VII) | 5.0535 | 5.0525 | -0.0010 | 0.3125 | 4.89e-05 | yes | reused from theta_max_robustness_2022 |
| Three taxes, labour residual (Table VIII) | 19.4279 | 19.4291 | +0.0013 | 0.1434 | 4.86e-05 | yes | solved |
| Three taxes, labour fixed (Table VIII) | 16.8400 | 16.8392 | -0.0008 | 0.2240 | 2.14e-03 | **NO** | solved |
| Wealth-capital, estate fixed (Table VIII) | 19.8137 | 19.8276 | +0.0140 | 0.1104 | 3.07e-05 | yes | solved |
| Best subsidy-cap grid point (Section 5.4) | 19.8497 | 19.8650 | +0.0152 | 0.1137 | 3.17e-05 | yes | solved |

Largest change in newborn CE2 across completed points: 0.0176 percentage points.

**Not revenue-feasible under the validated solve:** s5_2. The revenue gap exceeds 0.0001; the paper must not report these as feasible optima without qualification.
