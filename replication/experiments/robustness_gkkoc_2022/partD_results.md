# Part D: subsidies beyond -80% (thesis calibration, saved benchmark, estate tax 0)

Newborn CE2 (%). The -50% column is from the re-optimisation grid and edge sweep; -60% to -80% at 7-8% from Part B; the rest from Part D (guard-relaxed build).

| τ_w \ τ_k | -50% | -60% | -70% | -80% | -90% | -95% |
|---|---:|---:|---:|---:|---:|---:|
| 7.0% | 23.54 | 25.37 | 26.96 | 28.30 | — | — |
| 7.5% | 23.41 | — | — | — | — | — |
| 8.0% | 23.18 | 25.28 | 27.12 | 28.71 | 30.09 | 30.70 |
| 9.0% | 22.50 | — | — | 28.71 | 30.29 | **31.01** |
| 10.0% | 21.53 | — | — | 28.36 | 30.13 | 30.95 |

Best tested: τ_w 9.0%, τ_k -95%, estate 0: newborn CE2 31.01 (population 15.99, labour tax 11.10%, output +28.56%, top 1% 66.64%).
The best tested point is at the -95% input limit: no interior peak is identified.
- τ_w 7%: highest at τ_k -80% (edge of the tested range)
- τ_w 8%: highest at τ_k -95% (edge of the tested range)
- τ_w 9%: highest at τ_k -95% (edge of the tested range)
- τ_w 10%: highest at τ_k -95% (edge of the tested range)
Consistency check check_7_50_0: 23.539 vs 23.5385 → passed
