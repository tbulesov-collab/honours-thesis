# Frozen public 2022 Survey of Consumer Finances inputs

This directory contains the three unmodified Federal Reserve public-data ZIPs
used in the thesis's SCF calculations. No download is needed to rebuild the
estimates. These are public disclosure-limited survey files, not the
confidential SCF data.

| Archive | Member | Purpose |
|---|---|---|
| `scfp2022excel.zip` | `SCFP2022.csv` | Official summary variables, including wealth, income components and weights |
| `scf2022s.zip` | `p22i6.dta` | Full public Stata data, including business-management status and raw income components |
| `scf2022rw1s.zip` | `p22_rw1.dta` | Official bootstrap weights for the standard-error calculation |

The largest archive is 26,941,391 bytes; every archive is below GitHub's 100 MiB
per-file limit. Keep the full Stata data compressed in Git: its extracted member
is 236,952,250 bytes. The audited-definition builder reads the ZIPs directly.

`MANIFEST.json` records the source URLs, archive and member SHA-256 hashes and
byte sizes; the hashes identify the version used. The Federal Reserve can revise
its online extracts, including their inflation base, so use these files rather
than a newer download to reproduce the thesis values.

Official sources:

- [2022 SCF data and documentation](https://www.federalreserve.gov/econres/scf_2022.htm)
- [Summary extract ZIP](https://www.federalreserve.gov/econres/files/scfp2022excel.zip)
- [Full public Stata ZIP](https://www.federalreserve.gov/econres/files/scf2022s.zip)
- [Replicate-weight Stata ZIP](https://www.federalreserve.gov/econres/files/scf2022rw1s.zip)
- [2022 codebook](https://www.federalreserve.gov/econres/files/codebk2022.txt)
- [Federal Reserve summary-variable program](https://www.federalreserve.gov/econres/files/bulletin.macro.txt)

## Rebuild the audited definitions (Table III)

From the repository root, with the Python dependencies in
`replication/requirements.txt` installed:

```bash
python3 scripts/rebuild_scf_audit.py --check
```

This verifies all three archive hashes, reads the summary and full-data members,
checks the 22,975-record/4,595-family merge and all five implicates, rebuilds the
seven definitions, and compares all 28 numeric cells against
`replication/calibration/scf_2022_definition_moments_audited.csv`.
It does not run the model, access the network or change the reference CSV.

Optional new outputs, whose paths must not already exist:

```bash
python3 scripts/rebuild_scf_audit.py --check \
  --output /tmp/scf2022-audited-rebuilt.csv \
  --report /tmp/scf2022-audited-check.json
```

`audit_reproduction_check.json` holds the saved output of this command: every
comparison, all per-implicate estimates and the input and reference hashes. The
rebuilt values match the reference CSV within floating-point rounding (absolute
tolerance `1e-12`).

## Definitions and numerical conventions

For each definition, calculate weighted ratios separately in each of the five
implicates and take their equal average. For the richest one percent, rank
families by `NETWORTH` within each implicate, group equal-wealth observations,
and use the required fractional mass at the cutoff. Equal-wealth families get
the same inclusion fraction. The entrepreneur top-tail statistic is a population
share within that tail, not a wealth share.

Let `B = BUSSEFARMINC` and
`D = BUSSEFARMINC + WAGEINC + INTDIVINC + SSRETINC`. The first four definitions
appear in Table III:

1. Active manager: `X3104 == 1`.
2. Business-majority flows: `D > 0` and `B > 0.5 * D`.
3. Active manager and business majority: both conditions above.
4. Business-majority total income: `INCOME > 0` and `B > 0.5 * INCOME`.

The three additional definitions are:

5. Sole-proprietorship/farm income only in the numerator:
   `D > 0` and `(4315/3992) * X5704 > 0.5 * D`. The denominator retains the
   broad business component, including `X5714`.
6. Exclude pension-account withdrawals from the denominator:
   `D - PENACCTWD > 0` and `B > 0.5 * (D - PENACCTWD)`.
7. Change exactly `-1` to zero in raw income variables `X5702`, `X5704`,
   `X5706`, `X5708`, `X5710`, `X5714` and `X5722`. Add the resulting
   inflation-adjusted increments to the supplied summary numerator/denominator;
   retain other negative values and pension withdrawals. Apply the same
   positive-denominator and strict-majority conditions.

The exact income factor `4315/3992` is the Federal Reserve's 2022 `CPILAG`,
converting prior-year income to survey-year dollars in the frozen extract.
The script checks reconstructed income components against the summary inputs,
allowing the summary CSV's serialization rounding. It uses the summary
values for classification. Recovering the factor from rounded wages, or
reconstructing every income component from raw variables, can change
classifications at an exact 50% boundary.

## Calibration targets and standard errors

The calibration targets are built by the pooled-implicate/category-cutoff
builder `replication/tools/build_scf_definition_bridge.py`, which uses a different
procedure from the Table III builder above. `replication/tools/scf_2022_standard_errors.py`
computes the active-manager standard errors with the replicate weights.

To run them with extracted files, run these commands from the repository root:

```bash
python3 -m zipfile -e data/scf2022/scfp2022excel.zip replication/.cache/scf_2022_raw/summary
python3 -m zipfile -e data/scf2022/scf2022s.zip replication/.cache/scf_2022_raw/full
python3 -m zipfile -e data/scf2022/scf2022rw1s.zip replication/.cache/scf_2022_raw/weights
python3 replication/tools/build_scf_definition_bridge.py \
  --summary-csv replication/.cache/scf_2022_raw/summary/SCFP2022.csv \
  --full-dta replication/.cache/scf_2022_raw/full/p22i6.dta \
  --output /tmp/scf2022-definitions.csv
python3 replication/tools/scf_2022_standard_errors.py \
  --summary-csv replication/.cache/scf_2022_raw/summary/SCFP2022.csv \
  --full-dta replication/.cache/scf_2022_raw/full/p22i6.dta \
  --replicate-dta replication/.cache/scf_2022_raw/weights/p22_rw1.dta \
  --output /tmp/scf2022-standard-errors.csv
```

The extracted files are local runtime inputs, not additional files to commit.
