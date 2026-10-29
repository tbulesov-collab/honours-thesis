# Asset-grid accuracy check: na = 401 vs the standard grid (na = 201)

Fine grid: na = 401, fine_na = 1601. Both sides use the financing calibration, a benchmark solved from scratch on their own grid, and the same evaluator; only the grid differs.

## Newborn CE2 (%)

| Policy | Standard grid | Fine grid | Difference (pp) | Within 0.15 pp |
|---|---:|---:|---:|:---:|
| Separate wealth tax (3.06%) | 8.3912 | 8.0367 | -0.3545 | NO |
| Separate capital-income subsidy (−13.62%) | 4.9511 | 5.1353 | +0.1842 | NO |
| 7% wealth tax, −50% capital-income tax, 40% estate tax | 19.7663 | 19.1649 | -0.6014 | NO |
| 7% wealth tax, −50% capital-income tax, no estate tax | 23.4398 | 22.7848 | -0.6550 | NO |

## Checks

- all_within_0.15pp: NOT passed
- max_abs_difference_pp: 0.6550
- wealth_tax_beats_subsidy: passed
- joint_beats_separate: passed
- estate_removal_raises_welfare: passed
- fine_grid_gaps_pp: owt_minus_okit +2.9014, estate_removal_gain +3.6199

## Benchmark moments

| Grid | Ent. pop. | Ent. wealth | Ent. in top 1% | Top 1% | Top 0.1% | Debt/Y | K | Y |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| standard | 6.13% | 32.32% | 54.75% | 35.58% | 22.12% | 1.5649 | 4.0598 | 1.3461 |
| fine | 6.05% | 31.91% | 55.25% | 35.61% | 22.31% | 1.5502 | 3.9895 | 1.3387 |
