# Three-tax follow-up: estate tax at the joint package and welfare decomposition

Reported calibration, saved benchmark, labour tax residual; wealth tax 7%, capital-income tax -50%.

| Estate tax | Newborn CE2 | Population CE2 | Labour tax | Output | Top 1% | Source |
|---:|---:|---:|---:|---:|---:|---|
| 0% | 23.539 | 11.741 | 11.09% | +19.36% | 60.15% | reoptimisation grid (same context) |
| 10% | 22.710 | 11.421 | 11.15% | +18.73% | 59.35% | this run |
| 20% | 21.839 | 11.082 | 11.21% | +18.09% | 58.52% | this run |
| 30% | 20.893 | 10.720 | 11.29% | +17.42% | 57.64% | this run |
| 40% | 19.865 | 10.334 | 11.37% | +16.72% | 56.71% | this run |

## Checks

- estate 40% here 19.8650 vs headline s5_4 19.8650
- newborn CE2 falls monotonically with the estate tax: yes

## Welfare decomposition (CE2, newborn and population)

- 7.000/-50/40: full-output CE2 19.8650 vs standard run 19.8650

**7.000/-50/40** (wealth / capital-income / estate tax, %)

| Component | Newborn | Population |
|---|---:|---:|
| CE2_total | 19.865 | 10.334 |
| CE2_c | 18.482 | 10.599 |
| CE2_cl | 19.608 | 19.608 |
| CE2_cd | -0.942 | -7.532 |
| CE2_h | 1.173 | -0.222 |
| CE2_hl | -3.231 | -3.231 |
| CE2_hd | 4.551 | 3.110 |
| CE2_b | -0.006 | -0.018 |
| CE2_ch | 19.872 | 10.353 |
| CE2_chl | 15.744 | 15.744 |
| CE2_chd | 3.567 | -4.657 |
- 7.000/-50/0: full-output CE2 23.5385 vs standard run 23.5385

**7.000/-50/0** (wealth / capital-income / estate tax, %)

| Component | Newborn | Population |
|---|---:|---:|
| CE2_total | 23.539 | 11.741 |
| CE2_c | 21.887 | 11.847 |
| CE2_cl | 21.745 | 21.745 |
| CE2_cd | 0.117 | -8.130 |
| CE2_h | 1.358 | -0.093 |
| CE2_hl | -3.185 | -3.185 |
| CE2_hd | 4.692 | 3.193 |
| CE2_b | -0.003 | -0.002 |
| CE2_ch | 23.542 | 11.743 |
| CE2_chl | 17.867 | 17.867 |
| CE2_chd | 4.815 | -5.196 |

c = consumption, h = leisure (hours), b = bequests, ch = consumption and leisure together;
l = level (aggregate) part, d = distribution part (GKKOC Section VI.C, Table X).

