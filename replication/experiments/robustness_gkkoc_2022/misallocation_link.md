# Welfare gain and misallocation across validated policies

Sample: the 118 evaluations reported in the thesis (misallocation_link_sample.json).  Misallocation = 1 - (TFP/TFP*)^alpha (GKKOC's output-based measure; alpha = 0.4), TFP* from each benchmark.  Change in misallocation is in percentage points (negative = less misallocation).  Correlations are Pearson, across policies.  Fixed-labour (revenue-unmatched) evaluations are excluded. The zero or near-zero estate-tax group uses rates below 0.5%.

| Group | Policies | corr(CE2, -Δmisallocation) | corr(CE2, ΔK) | corr(CE2, Δoutput) | Benchmark misallocation |
|---|---:|---:|---:|---:|---:|
| all | 118 | 0.83 | 0.06 | 0.48 | 0.135, 0.150, 0.151, 0.152, 0.155 |
| thesis (saved benchmark) | 44 | 0.87 | -0.10 | 0.38 | 0.150 |
| re-calibrated, original code | 53 | 0.71 | 0.32 | 0.61 | 0.135 |
| re-calibrated, productivity fix | 5 | 0.91 | -0.26 | 0.45 | 0.135 |
| thesis params, control code | 5 | 0.93 | -0.20 | 0.56 | 0.151 |
| thesis params, productivity code | 5 | 0.93 | -0.20 | 0.57 | 0.152 |
| estate tax 40% | 61 | 0.93 | -0.25 | 0.22 | 0.135, 0.150, 0.151, 0.152, 0.155 |
| estate tax zero or near-zero | 52 | 0.66 | 0.59 | 0.79 | 0.135, 0.150, 0.151, 0.152 |
| separate taxes, estate tax 40% | 37 | 0.46 | -0.63 | -0.57 | 0.135, 0.150, 0.151, 0.152, 0.155 |
| joint packages (wealth tax and subsidy) | 69 | 0.58 | 0.45 | 0.69 | 0.135, 0.150, 0.151, 0.152 |

## Regression of newborn CE2 on the two channels, by benchmark

| Benchmark | Policies | β(-Δmisallocation, pp) | β(ΔK, %) | R² |
|---|---:|---:|---:|---:|
| thesis (saved benchmark) | 44 | 5.27 | 0.07 | 0.80 |
| re-calibrated, original code | 53 | 4.71 | 0.14 | 0.74 |

## Selected policies

| Benchmark | τ_w | τ_k | τ_b | CE2 | ΔTFP % | Misallocation (bench → policy) | ΔK % |
|---|---:|---:|---:|---:|---:|---:|---:|
| re-calibrated, original code | 7.00% | -50.0% | 0% | 20.59 | +12.57 | 0.135 → 0.093 | +21.48 |
| re-calibrated, original code | 0.00% | -13.6% | 40% | 4.27 | +4.48 | 0.135 → 0.120 | +37.05 |
| re-calibrated, original code | 3.06% | +0.0% | 40% | 7.24 | +6.40 | 0.135 → 0.113 | +0.80 |
| re-calibrated, original code | 7.00% | -50.0% | 40% | 16.88 | +13.18 | 0.135 → 0.091 | +14.16 |
| re-calibrated, productivity fix | 0.00% | -13.6% | 40% | 4.55 | +4.80 | 0.135 → 0.119 | +37.56 |
| re-calibrated, productivity fix | 3.06% | +0.0% | 40% | 7.60 | +6.78 | 0.135 → 0.112 | +1.28 |
| re-calibrated, productivity fix | 7.00% | -50.0% | 40% | 17.05 | +13.52 | 0.135 → 0.090 | +14.45 |
| thesis (saved benchmark) | 7.00% | -50.0% | 0% | 23.54 | +14.34 | 0.150 → 0.103 | +25.48 |
| thesis (saved benchmark) | 0.00% | -13.6% | 40% | 5.05 | +4.83 | 0.150 → 0.134 | +38.96 |
| thesis (saved benchmark) | 3.06% | +0.0% | 40% | 8.49 | +7.06 | 0.150 → 0.127 | +2.44 |
| thesis (saved benchmark) | 7.00% | -50.0% | 40% | 19.86 | +15.12 | 0.150 → 0.101 | +17.85 |
| thesis params, both code | 0.00% | -13.6% | 40% | 5.15 | +5.16 | 0.152 → 0.134 | +38.84 |
| thesis params, both code | 3.06% | +0.0% | 40% | 8.59 | +7.42 | 0.152 → 0.127 | +2.52 |
| thesis params, control code | 0.00% | -13.6% | 40% | 4.95 | +4.93 | 0.151 → 0.134 | +38.58 |
| thesis params, control code | 3.06% | +0.0% | 40% | 8.39 | +7.17 | 0.151 → 0.127 | +2.16 |
| thesis params, control code | 7.00% | -50.0% | 40% | 19.77 | +15.24 | 0.151 → 0.101 | +17.55 |
| thesis params, productivity code | 0.00% | -13.6% | 40% | 5.14 | +5.16 | 0.152 → 0.134 | +38.81 |
| thesis params, productivity code | 3.06% | +0.0% | 40% | 8.60 | +7.43 | 0.152 → 0.127 | +2.52 |
| thesis params, productivity code | 7.00% | -50.0% | 40% | 19.96 | +15.59 | 0.152 → 0.101 | +17.96 |
| thesis params, theta_max 2.8 | 0.00% | -13.6% | 40% | 5.22 | +4.90 | 0.155 → 0.138 | +39.29 |
| thesis params, theta_max 2.8 | 3.06% | +0.0% | 40% | 8.49 | +7.18 | 0.155 → 0.131 | +2.26 |
| thesis params, timing code | 0.00% | -13.6% | 40% | 4.96 | +4.93 | 0.151 → 0.134 | +38.62 |
| thesis params, timing code | 3.06% | +0.0% | 40% | 8.39 | +7.17 | 0.151 → 0.127 | +2.17 |
