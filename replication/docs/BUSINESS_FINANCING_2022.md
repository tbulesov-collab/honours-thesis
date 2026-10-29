# 2022 business-financing calibration

The paper targets business debt plus external funds relative to GDP. Its footnote 25
constructs the 2015 target as nonfinancial-business liabilities plus the capitalized
annual flow of equity issues, divided by nominal GDP. The equity flow is capitalized
at 5%.

The same calculation for 2022 is:

| Component | 2022 value |
| --- | ---: |
| Nonfinancial-business total liabilities, end of year | $40.065223 trillion |
| Gross nonfinancial stock issuance | $32.760 billion |
| Capitalized issuance at 5% | $0.655200 trillion |
| Nominal GDP | $26.054614 trillion |
| Business financing / GDP | **1.562887** |

The inputs are versioned in `calibration/business_financing_2022.csv`. Liabilities are
Federal Reserve Financial Accounts series `FL144190005`; gross stock issuance is line
9 of Federal Reserve table 1.46; and nominal GDP is BEA series `GDPA`, distributed by
FRED. The current data vintage contains historical revisions, while the observation
year remains aligned with the 2022 SCF.

The borrowing constraint in the code is a nine-point linear schedule from 1 to 2.8.
The financing update holds the staged 2022 SCF entrepreneurial parameters fixed and
searches only for the upper endpoint of that schedule. This isolates the financing-data
update rather than silently re-solving the entire underidentified entrepreneurial block.

Run on macOS with:

```bash
python3 tools/recalibrate_financing_2022.py --threads 4
```

The search caches each model evaluation under
`calibration/runs/business_financing_2022/` and writes the selected result to
`calibration/runs/business_financing_2022/best.json`. Use `--skip-build` after the
first compile, or `--evaluate THETA_MAX` to inspect one candidate.

## Recalibration result

Holding the staged SCF entrepreneurial-process parameters fixed, the search selected
`theta_max=2.95212924`, compared with 2.8 in the published parameterization. The
resulting linear constraint schedule runs from 1 to 2.95212924. The solved model
produces debt/output of 1.56295665, only 0.00006944 above the 2022 target.

| Benchmark moment | SCF calibration with old financing | Updated financing | Change |
| --- | ---: | ---: | ---: |
| Debt plus external funds / output | 1.49225 | 1.56296 | +0.07071 |
| Wealth / output | 3.00826 | 3.01103 | +0.00277 |
| Top 1% wealth share | 35.90% | 35.47% | -0.43 pp |
| Top 0.1% wealth share | 22.80% | 22.60% | -0.20 pp |
| Entrepreneur population share | 6.40% | 6.13% | -0.26 pp |
| Entrepreneurs among top 1% | 64.61% | 61.58% | -3.02 pp |
| Entrepreneur wealth share | 33.94% | 32.23% | -1.71 pp |

The looser borrowing schedule matches the financing target but worsens all three
entrepreneurship moments relative to the 2022 SCF targets. This result should therefore
be treated as a sequential robustness calibration. A later joint recalibration can let
the entrepreneurial-process parameters respond to the financing update.
