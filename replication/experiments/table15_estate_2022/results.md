# Table 15 estate-tax cells (7% wealth tax, -50% capital-income tax)

| Comparison | Separate-policy gap (pp) | Newborn CE2 (%) estate 40% → 0% | Estate-removal gain (pp) |
|---|---:|---:|---:|
| Financial constraints, θ_max = 2.800 | 3.28 | 19.93 → 23.58 | +3.66 |
| Financial constraints, θ_max = 2.952 | 3.44 | 19.86 → 23.54 | +3.67 |
| Recalibration, alternative productivity convention | 3.04 | 17.05 → 20.83 | +3.78 |

Gains are computed before rounding. Each estate-tax pair uses one benchmark; benchmarks differ across rows.

## Points

- recal_alt_bq40: newborn CE2 17.0505, population 8.5802, labour tax 12.52%, top 1% 52.57%, revenue gap 0.0035%, residual 1.7e-09, feasible True (experiments/model_spec_sensitivity_2022/recal/productivity/policies/v2_00c9e2e4acd3/481b7529db377b95_7de69f05)
- theta_2952_bq40: newborn CE2 19.8650, population 10.3335, labour tax 11.37%, top 1% 56.71%, revenue gap 0.0032%, residual 1.5e-09, feasible True (experiments/three_tax_2022/runs/estate/v2_fecede9519f7/0f17cb8e58562d19_8148a55d)
- theta_2952_bq0: newborn CE2 23.5385, population 11.7406, labour tax 11.09%, top 1% 60.15%, revenue gap 0.0078%, residual 2.4e-09, feasible True (experiments/policy_reoptimization_2022/runs/thesis/v2_fecede9519f7/54b48c5df64e6d40_35be0941)
- theta_2800_bq40: newborn CE2 19.9291, population 10.4650, labour tax 11.46%, top 1% 56.99%, revenue gap 0.0031%, residual 1.5e-09, feasible True (experiments/table15_estate_2022/runs/theta_2800/v2_bf1c556574d7)
- theta_2800_bq0: newborn CE2 23.5848, population 11.8696, labour tax 11.19%, top 1% 60.45%, revenue gap 0.0076%, residual 2.3e-09, feasible True (experiments/table15_estate_2022/runs/theta_2800/v2_bf1c556574d7)
- recal_alt_bq0: newborn CE2 20.8285, population 10.0124, labour tax 12.14%, top 1% 56.28%, revenue gap 0.0098%, residual 2.2e-09, feasible True (experiments/table15_estate_2022/runs/recal_alt/v2_00c9e2e4acd3)

## Checks

- theta_2952 bq40: 19.8650 vs 19.8650 → passed
- theta_2952 bq0: 23.5385 vs 23.5385 → passed
- recal_alt bq40: 17.0505 vs 17.0505 → passed
- recal_alt: gain 3.78 lies outside the Table 15 range 2.82–3.75
