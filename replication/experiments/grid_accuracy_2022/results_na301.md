# Asset-grid accuracy check: na = 301 vs the standard grid (na = 201)

Fine grid: na = 301, fine_na = 1201. Both sides use the financing calibration, a benchmark solved from scratch on their own grid, and the same evaluator; only the grid differs.

## Newborn CE2 (%)

| Policy | Standard grid | Fine grid | Difference (pp) | Within 0.15 pp |
|---|---:|---:|---:|:---:|
| Separate wealth tax (3.06%) | 8.3912 | 8.1265 | -0.2647 | NO |
| Separate capital-income subsidy (−13.62%) | 4.9511 | 5.0670 | +0.1159 | yes |
| 7% wealth tax, −50% capital-income tax, 40% estate tax | 19.7663 | 19.3383 | -0.4280 | NO |
| 7% wealth tax, −50% capital-income tax, no estate tax | 23.4398 | 22.9699 | -0.4699 | NO |

## Checks

- all_within_0.15pp: NOT passed
- max_abs_difference_pp: 0.4699
- wealth_tax_beats_subsidy: passed
- joint_beats_separate: passed
- estate_removal_raises_welfare: passed
- fine_grid_gaps_pp: owt_minus_okit +3.0594, estate_removal_gain +3.6316

## Benchmark moments

| Grid | Ent. pop. | Ent. wealth | Ent. in top 1% | Top 1% | Top 0.1% | Debt/Y | K | Y |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| standard | 6.13% | 32.32% | 54.75% | 35.58% | 22.12% | 1.5649 | 4.0598 | 1.3461 |
| fine | 6.07% | 32.03% | 55.07% | 35.60% | 22.23% | 1.5549 | 4.0119 | 1.3411 |
