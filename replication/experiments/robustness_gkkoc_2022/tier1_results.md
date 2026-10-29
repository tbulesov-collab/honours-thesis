# GKKOC Tier-1 robustness checks with the thesis model

## Wealth tax on top of the existing system (GKKOC Table E.10 vi-ix)

Thesis calibration, saved benchmark; capital-income tax stays 25%, estate tax 40%.  *Wasted*: labour tax fixed, surplus revenue not used for anything valued.  *Rebated*: labour tax lowered to keep revenue at the benchmark.

| Wealth tax | Revenue use | Labour tax | Newborn CE2 | Population CE2 | CE1 | Output | Consumption | K | TFP | GKKOC CE2 |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 2.00% | wasted | 22.40% | -10.07 | -9.55 | -8.33 | -6.63% | -9.66% | -20.47% | +3.43% | −9.9 |
| 2.00% | rebated | 14.79% | 0.12 | -1.75 | 1.20 | -3.94% | -2.34% | -15.21% | +2.69% | 0.0 |
| 3.06% | wasted | 22.40% | -14.37 | -13.66 | -12.03 | -9.69% | -13.77% | -28.75% | +5.17% | −14.2 |
| 3.06% | rebated | 11.87% | -1.03 | -3.42 | 0.66 | -6.34% | -4.20% | -22.63% | +4.20% | −1.0 |

GKKOC's on-top experiments use 2% and their 3.03% optimum.

## Looser borrowing constraints (GKKOC Table E.10 i)

theta_max re-fitted to debt/output 2.503 (target 2.5): theta_max = 9.656 (thesis 2.952, debt/output 1.565).  Fit path: 2.95→1.565, 8.00→2.392, 12.80→2.637, 10.11→2.530, 9.66→2.503.

| Benchmark | Debt/output | Top 1% | Top 0.1% | Misallocation |
|---|---:|---:|---:|---:|
| thesis (θ 2.952) | 1.565 | 35.58% | 22.12% | 0.151 |
| looser (θ 9.656) | 2.503 | 35.82% | 26.12% | 0.064 |

| Policy | τ_w | τ_k | τ_b | Baseline CE2 | Looser CE2 | Looser labour tax | Looser output | Misallocation (bench → policy) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| owt_0.015 | 1.50% | +0.0% | 40% | — | 4.42 | 22.10% | +5.47% | 0.064 → 0.055 |
| owt_0.02 | 2.00% | +0.0% | 40% | — | 4.80 | 20.09% | +4.51% | 0.064 → 0.054 |
| owt_0.025 | 2.50% | +0.0% | 40% | — | 4.91 | 18.26% | +3.45% | 0.064 → 0.053 |
| owt_0.030618 | 3.06% | +0.0% | 40% | 8.39 | 4.83 | 16.38% | +2.22% | 0.064 → 0.052 |
| owt_0.035 | 3.50% | +0.0% | 40% | — | 4.62 | 15.04% | +1.21% | 0.064 → 0.051 |
| okit_-0.05 | 0.00% | -5.0% | 40% | — | FAILED | | | |
| okit_-0.1 | 0.00% | -10.0% | 40% | — | FAILED | | | |
| okit_-0.13618 | 0.00% | -13.6% | 40% | 4.95 | FAILED | | | |
| okit_-0.2 | 0.00% | -20.0% | 40% | — | FAILED | | | |
| joint_7_50_40 | 7.00% | -50.0% | 40% | 19.77 | 10.08 | 14.13% | +7.63% | 0.064 → 0.040 |
| joint_7_50_0 | 7.00% | -50.0% | 0% | 23.44 | 13.83 | 13.83% | +9.86% | 0.064 → 0.041 |
| joint_6_50_0 | 6.00% | -50.0% | 0% | — | 14.25 | 16.40% | +12.18% | 0.064 → 0.042 |

## Looser constraints, bounded interest-rate search (OKIT follow-up)

Same benchmark, calibration and policies; evaluator built by make_rbracket.py (interest-rate search on [-0.1, 0.5] from the current R instead of [-0.1, 10] from 0.01).

| Policy | τ_w | τ_k | τ_b | CE2 | Labour tax | Output | Misallocation (bench → policy) | Original build |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| okit_-0.05 | 0.00% | -5.0% | 40% | 1.480 | 30.51% | +9.07% | 0.064 → 0.057 | failed |
| okit_-0.1 | 0.00% | -10.0% | 40% | 1.212 | 31.83% | +10.28% | 0.064 → 0.056 | failed |
| okit_-0.13618 | 0.00% | -13.6% | 40% | 0.952 | 32.77% | +11.11% | 0.064 → 0.055 | failed |
| okit_-0.2 | 0.00% | -20.0% | 40% | 0.368 | 34.42% | +12.51% | 0.064 → 0.054 | failed |
| check_owt_0.025 | 2.50% | +0.0% | 40% | 4.906 | 18.26% | +3.45% | 0.064 → 0.053 | 4.906 |
| check_joint_6_50_0 | 6.00% | -50.0% | 0% | 14.253 | 16.40% | +12.18% | 0.064 → 0.042 | 14.253 |

Consistency check (re-evaluated points within 0.01 pp of the original build): **passed**.
Looser constraints on the original subsidy grid: best OKIT -5.0% (CE2 1.48) against best OWT 2.50% (CE2 4.91): wealth-tax advantage 3.43 pp (baseline 3.44).

Part B adds capital-income-tax rates of -2.5%, zero and +5%. The best tested rate is +5% (CE2 1.64%), and the wealth-tax advantage is 3.27 percentage points; the optimum remains unidentified. See [Part B results](partB_results.md).
