# Policy re-optimisation under the re-calibrated parameters

Newborn CE2 (%).  recal: re-calibrated original code, own benchmark.  thesis: reported calibration, saved benchmark (as in the reported tables).

## Reported calibration, estate tax 40% (reported grid)

| tau_w \ tau_k | +0% | -10% | -20% | -30% | -40% | -50% |
|---|---:|---:|---:|---:|---:|---:|
| 3% | 8.42 | 10.79 | 12.62 | 13.96 | 14.97 | 15.69 |
| 5% | 7.48 | 10.78 | 13.48 | 15.69 | 17.49 | 18.90 |
| 7% | 4.99 | 9.02 | 12.41 | 15.31 | 17.76 | **19.85** |

## Reported calibration, estate tax 0

| tau_w \ tau_k | +0% | -10% | -20% | -30% | -40% | -50% |
|---|---:|---:|---:|---:|---:|---:|
| 3% | 12.21 | 14.62 | 16.47 | 17.84 | 18.84 | 19.56 |
| 5% | 11.03 | 14.42 | 17.17 | 19.46 | 21.34 | 22.87 |
| 7% | 8.16 | 12.29 | 15.79 | 18.80 | 21.36 | **23.54** |

## Re-calibrated, estate tax 40%

| tau_w \ tau_k | +0% | -10% | -20% | -30% | -40% | -50% |
|---|---:|---:|---:|---:|---:|---:|
| 3% | 7.26 | 9.47 | 11.08 | 12.23 | 13.00 | 13.43 |
| 5% | 5.82 | 8.94 | 11.47 | 13.50 | 15.09 | 16.33 |
| 7% | 2.87 | 6.74 | 9.99 | 12.72 | 14.99 | **16.88** |

## Re-calibrated, estate tax 0

| tau_w \ tau_k | +0% | -10% | -20% | -30% | -40% | -50% |
|---|---:|---:|---:|---:|---:|---:|
| 3% | 11.07 | 13.31 | 15.01 | 16.21 | 17.05 | 17.57 |
| 5% | 9.40 | 12.62 | 15.24 | 17.34 | 19.02 | 20.35 |
| 7% | 6.09 | 10.07 | 13.41 | 16.20 | 18.58 | **20.59** |

`*` misses the revenue tolerance.  Bold: highest in the table.

- thesis: best at estate tax 0 minus best at 40% = +3.69 pp
- recal: best at estate tax 0 minus best at 40% = +3.71 pp

## Separate optima, re-calibrated (tau_bq 40%)

| Wealth tax | 2.00% | 2.50% | 3.06% | 3.50% | 4.00% |
|---|---:|---:|---:|---:|---:|
| CE2 | 7.07 | 7.27 | 7.24 | 7.10 | 6.78 |

| Capital-income tax | -22.0% | -18.0% | -13.6% | -10.0% | -6.0% |
|---|---:|---:|---:|---:|---:|
| CE2 | 4.06 | 4.19 | 4.27 | 4.27 | 4.18 |

Best OWT 7.27 at 2.50%; best OKIT 4.27 at -13.6%; gap 3.00 pp (fixed-rate gap in recal_results: 2.97).

## Wealth tax along the edge (tau_k -50%, estate tax 0)

| Calibration | 3.0% | 5.0% | 6.0% | 7.0% | 7.5% | 8.0% | 9.0% | 10.0% |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| thesis | 19.56 | 22.87 | 23.46 | **23.54** | 23.41 | 23.18 | 22.50 | 21.53 |
| recal | 17.57 | 20.35 | **20.73** | 20.59 | 20.39 | 20.08 | 19.23 | 18.15 |

- thesis: best wealth tax on the edge 7.0%, CE2 23.539, population CE2 11.741, labour tax 11.09%, output +19.36%, top 1% 60.15%
- recal: best wealth tax on the edge 6.0%, CE2 20.726, population CE2 10.524, labour tax 14.85%, output +19.02%, top 1% 55.55%
