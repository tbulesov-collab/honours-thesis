# Re-calibration sensitivity (option A)

Each arm repeats the thesis's SCF and financing calibration steps with its own code (repaired percentile statistic), then evaluates the reported policies at their reported rates against its own benchmark.

## Calibrated parameters

| Parameter | Thesis | Re-calibrated control | Re-calibrated productivity |
|---|---:|---:|---:|
| sigma_z_eps | 0.278308 | 0.275237 | 0.286331 |
| x_hi | 1.462069 | 1.394094 | 1.355882 |
| p1_x | 0.050298 | 0.049617 | 0.049531 |
| p2_x | 0.032874 | 0.034478 | 0.034609 |
| theta_max | 2.952129 | 2.994952 | 3.017170 |

## Benchmark moments (financing-step benchmark; repaired statistic)

| Moment | Target | Thesis calibration, original code | Re-calibrated control | Re-calibrated productivity |
|---|---:|---:|---:|---:|
| Top 1% wealth share | 36.00% | 35.58% | 33.32% | 33.53% |
| Entrepreneurs in top 1% | 64.45% | 54.75% | 55.54% | 54.29% |
| Entrepreneur wealth share | 44.96% | 32.32% | 32.43% | 31.50% |
| Entrepreneur population |  | 6.13% | 6.50% | 6.26% |
| Top 0.1% wealth share |  | 22.12% | 19.36% | 19.71% |
| Debt/output | 1.5629 | 1.5649 | 1.5630 | 1.5630 |
| SCF objective (at theta_max = 2.8) | 0 | 121.57 (old statistic) | 155.13 | 183.69 |

## Newborn CE2 (%)

| Policy | Thesis | Fixed params, control | Fixed params, productivity | Re-calibrated control | Re-calibrated productivity | Productivity effect, re-calibrated |
|---|---:|---:|---:|---:|---:|---:|
| owt | 8.491 | 8.391 | 8.596 | 7.241 | 7.595 | +0.355 |
| okit | 5.052 | 4.951 | 5.142 | 4.269 | 4.553 | +0.284 |
| s5_1 | 19.429 | 19.330 | 19.534 | 17.336 | 17.645 | +0.309 |
| s5_3 | 19.828 | 19.729 | 19.919 | 16.828 | 16.995 | +0.167 |
| s5_4 | 19.865 | 19.766 | 19.958 | 16.884 | 17.051 | +0.166 |

OWT − OKIT gap (newborn CE2): control: 2.97, productivity: 3.04

## Policy details (re-calibrated)

| Arm | Policy | Newborn CE2 | Population CE2 | Labour tax | Output | Top 1% | Agg. residual | Revenue gap |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| control | owt | 7.241% | 3.377% | 15.87% | +4.69% | 41.47% | 7.95e-07 | 6.7e-05 |
| control | okit | 4.269% | 4.005% | 31.62% | +14.47% | 43.63% | 8.06e-07 | 5.9e-05 |
| control | s5_1 | 17.336% | 8.618% | 15.14% | +14.92% | 51.97% | 9.46e-07 | 5.3e-05 |
| control | s5_3 | 16.828% | 8.465% | 12.26% | +13.85% | 52.43% | 7.91e-07 | 3.4e-05 |
| control | s5_4 | 16.884% | 8.573% | 12.59% | +14.16% | 52.37% | 7.75e-07 | 3.3e-05 |
| productivity | owt | 7.595% | 3.497% | 15.68% | +5.12% | 42.12% | 9.93e-07 | 6.4e-05 |
| productivity | okit | 4.553% | 4.122% | 31.47% | +14.88% | 44.23% | 9.04e-07 | 5.1e-05 |
| productivity | s5_1 | 17.645% | 8.683% | 14.99% | +15.38% | 52.60% | 9.80e-07 | 5.4e-05 |
| productivity | s5_3 | 16.995% | 8.474% | 12.19% | +14.14% | 52.62% | 8.20e-07 | 3.5e-05 |
| productivity | s5_4 | 17.051% | 8.580% | 12.52% | +14.45% | 52.57% | 8.23e-07 | 3.5e-05 |
