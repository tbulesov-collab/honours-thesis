# Asset-grid check for the extended-subsidy policies

Newborn CE2 (%) against each grid's own freshly solved benchmark (no estate tax). 201 points: control build and benchmark of model_spec_sensitivity_2022. 301/401 points: the builds and benchmarks of run_grid_check.py.

| Policy | 201 | 301 | 401 | 401 − 201 (pp) |
|---|---:|---:|---:|---:|
| 7% wealth tax, −50% capital-income tax (existing check) | 23.4398 | 22.9699 | 22.7848 | -0.6550 |
| 8% wealth tax, −80% capital-income tax | 28.6136 | 28.0837 | 27.9102 | -0.7033 |
| 9% wealth tax, −95% capital-income tax | 30.9078 | 30.3326 | 30.1508 | -0.7571 |
| 10% wealth tax, −95% capital-income tax | 30.8477 | 30.2493 | 30.0655 | -0.7822 |

## Checks

- Largest 201→401 move among the four existing policies: 0.6550 pp
- 201 points: 9% minus 10% at −95%: +0.0602 pp (tied); welfare rises 7%/−50% → 8%/−80% → 95%: yes
- 301 points: 9% minus 10% at −95%: +0.0833 pp (tied); welfare rises 7%/−50% → 8%/−80% → 95%: yes
- 401 points: 9% minus 10% at −95%: +0.0853 pp (tied); welfare rises 7%/−50% → 8%/−80% → 95%: yes

## Extended points in detail

| Grid | Policy | Population CE2 | Labour tax | Output | Top 1% | Agg. residual | Revenue gap | Hours |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| 201 | w8_s80 | 14.796% | 11.98% | +26.43% | 64.62% | 8.3e-07 | 8.1e-05 | 0.87 |
| 201 | w9_s95 | 15.945% | 11.13% | +28.47% | 66.66% | 7.0e-07 | 9.3e-05 | 0.82 |
| 201 | w10_s95 | 15.577% | 8.96% | +26.34% | 67.02% | 6.6e-07 | 2.2e-05 | 0.80 |
| 301 | w8_s80 | 14.304% | 12.26% | +26.52% | 64.99% | 7.4e-07 | 6.2e-05 | 1.32 |
| 301 | w9_s95 | 15.428% | 11.43% | +28.56% | 67.01% | 9.0e-07 | 7.9e-05 | 1.25 |
| 301 | w10_s95 | 15.044% | 9.27% | +26.43% | 67.38% | 9.2e-07 | 9.1e-05 | 1.21 |
| 401 | w8_s80 | 14.109% | 12.35% | +26.60% | 65.11% | 6.9e-07 | 7.3e-05 | 1.73 |
| 401 | w9_s95 | 15.221% | 11.52% | +28.66% | 67.13% | 9.2e-07 | 8.1e-05 | 1.68 |
| 401 | w10_s95 | 14.833% | 9.37% | +26.53% | 67.47% | 9.4e-07 | 9.3e-05 | 1.63 |
