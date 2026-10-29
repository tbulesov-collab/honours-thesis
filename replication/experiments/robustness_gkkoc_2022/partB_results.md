# Part B: beyond the boundary results

## B3: subsidies beyond −50% (thesis calibration, saved benchmark, estate tax 0)

Newborn CE2 (%).  −50% column from the re-optimisation grid/edge sweep (original build); beyond −50% from the guard-relaxed build.

| τ_w \ τ_k | -50% | -60% | -70% | -80% |
|---|---:|---:|---:|---:|
| 5.0% | 22.87 | — | — | — |
| 6.0% | 23.46 | — | — | — |
| 7.0% | 23.54 | 25.37 | 26.96 | 28.30 |
| 7.5% | 23.41 | — | — | — |
| 8.0% | 23.18 | 25.28 | 27.12 | **28.71** |
| 9.0% | 22.50 | — | — | — |
| 10.0% | 21.53 | — | — | — |

Best: τ_w 8.0%, τ_k -80%, estate 0: newborn CE2 28.71 (population 14.84, labour tax 11.95%, output +26.52%, top 1% 64.61%).  At −50% the best is 23.54.
Consistency check check_7_50_0: 23.539 vs 23.5385 → **passed**

## B4: capital-income tax near zero under looser constraints (bounded build)

| τ_k | -20.0% | -13.6% | -10.0% | -5.0% | -2.5% | +0.0% | +5.0% |
|---|---:|---:|---:|---:|---:|---:|---:|
| Newborn CE2 | 0.37 | 0.95 | 1.21 | 1.48 | 1.57 | 1.63 | 1.64 |
| Labour tax | 34.4% | 32.8% | 31.8% | 30.5% | 29.8% | 29.2% | 27.8% |

Best capital-income tax +5.0% (CE2 1.64); best wealth tax 2.50% (CE2 4.91); wealth-tax advantage 3.27 pp (baseline 3.44).
The best capital-income tax is at the edge of the tested range (+5.0%).
