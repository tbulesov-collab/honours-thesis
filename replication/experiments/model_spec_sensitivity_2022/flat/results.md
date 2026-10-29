# Policy rankings along the unidentified calibration direction

Direction (proportional changes, largest = 1): sigma_z_eps -0.926, x_hi +0.695, p1_x -1.000, p2_x +0.238. Step ±0.1. Singular values of the scaled Jacobian: 1.1101, 0.1475, 0.0111.

Centre: thesis parameters with a fresh benchmark (run_sensitivity.py control). Each side re-fits theta_max to the financing target and uses its own benchmark.

## Parameters

| Parameter | minus | centre | plus |
|---|---:|---:|---:|
| sigma_z_eps | 0.304068 | 0.278308 | 0.252548 |
| x_hi | 1.360505 | 1.462069 | 1.563632 |
| p1_x | 0.055328 | 0.050298 | 0.045268 |
| p2_x | 0.032093 | 0.032874 | 0.033656 |
| theta_max | 2.952129 | 2.952129 | 2.957688 |

## Benchmark moments

| Moment | Target | minus | centre | plus |
|---|---:|---:|---:|---:|
| Top 1% wealth share | 36.00% | 35.76% | 35.58% | 34.98% |
| Entrepreneurs in top 1% | 64.45% | 54.57% | 54.75% | 54.70% |
| Entrepreneur wealth share | 44.96% | 32.19% | 32.32% | 32.35% |
| Entrepreneur population |  | 6.01% | 6.13% | 6.31% |
| Top 0.1% wealth share |  | 22.11% | 22.12% | 21.61% |
| Debt/output |  | 1.5632 | 1.5649 | 1.5632 |

## Newborn CE2 (%)

| Policy | minus | centre | plus |
|---|---:|---:|---:|
| Separate wealth tax (3.06%) | 8.178 | 8.391 | 8.450 |
| Separate subsidy (−13.62%) | 4.870 | 4.951 | 4.991 |
| Three-tax candidate (4.91%, −30%, ≈0.1%) | 18.678 | 19.330 | 19.615 |
| 7.13%, −49.82%, 40% | 18.387 | 19.729 | 20.229 |
| 7%, −50%, 40% estate tax | 18.432 | 19.766 | 20.271 |
| 7%, −50%, no estate tax | 22.266 | 23.440 | 23.871 |

## Rankings

- minus: wealth-tax lead +3.31 pp (holds); joint beats separate: yes; estate-removal gain +3.83 pp; joint order s5_1 > s5_4 > s5_3
- centre: wealth-tax lead +3.44 pp (holds); joint beats separate: yes; estate-removal gain +3.67 pp; joint order s5_4 > s5_3 > s5_1
- plus: wealth-tax lead +3.46 pp (holds); joint beats separate: yes; estate-removal gain +3.60 pp; joint order s5_4 > s5_3 > s5_1
