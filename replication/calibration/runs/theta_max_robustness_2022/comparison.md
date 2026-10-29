# theta_max robustness of the headline policy results

Published arm: theta_max = 2.8000000000
Financing arm: theta_max = 2.9521292419

Entrepreneurial parameters identical across arms; only theta_max differs.
All points revenue-neutral via the labour tax.

| Anchor | Metric | Published | Financing | Difference |
|---|---|---:|---:|---:|
| benchmark | CE2 newborn (%) | 0.1096 | 0.0976 | -0.0120 |
| benchmark | CE1 newborn (%) | 0.0943 | 0.0868 | -0.0075 |
| benchmark | Labour tax | 0.2236 | 0.2236 | +0.0000 |
| benchmark | Top 1% wealth share | 0.3598 | 0.3556 | -0.0042 |
| benchmark | Output change (%) | 0.0906 | 0.0827 | -0.0079 |
| benchmark | Consumption change (%) | 0.1309 | 0.1205 | -0.0103 |
| owt | CE2 newborn (%) | 8.4928 | 8.4913 | -0.0015 |
| owt | CE1 newborn (%) | 9.0091 | 9.0369 | +0.0278 |
| owt | Labour tax | 0.1543 | 0.1538 | -0.0005 |
| owt | Top 1% wealth share | 0.4484 | 0.4448 | -0.0036 |
| owt | Output change (%) | 5.7064 | 5.7649 | +0.0585 |
| owt | Consumption change (%) | 7.6061 | 7.6412 | +0.0352 |
| okit | CE2 newborn (%) | 5.2171 | 5.0525 | -0.1646 |
| okit | CE1 newborn (%) | 4.2294 | 4.0683 | -0.1611 |
| okit | Labour tax | 0.3118 | 0.3125 | +0.0007 |
| okit | Top 1% wealth share | 0.4693 | 0.4651 | -0.0042 |
| okit | Output change (%) | 15.6765 | 15.5047 | -0.1717 |
| okit | Consumption change (%) | 13.9233 | 13.7332 | -0.1901 |

Equilibrium iteration cap per anchor: benchmark 700, owt 700, okit 2000.  Every result passed the validated convergence checks; the cap only matters when a solve reaches it.

## Welfare ranking (OWT minus OKIT, CE2 newborn)

- Published arm: +3.2757
- Financing arm: +3.4388
- Change: +0.1631

The ranking **is preserved** between the two arms.
