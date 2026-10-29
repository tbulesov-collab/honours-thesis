# Wealth taxation: replication code and evidence

This repository contains the code, data and saved numerical results for the
honours thesis *Taxing Wealth, Capital Income and Estates: Heterogeneous Returns
and Dynastic Wealth Transmission* (Research School of Economics, The Australian
National University).

## What the thesis studies

The thesis uses the overlapping-generations model of Guvenen, Kambourov, Kuruscu,
Ocampo and Chen, in which entrepreneurs differ in productivity and so earn
different returns on their wealth. It updates the model's entrepreneurship and
business-financing targets with 2022 U.S. data and asks:

- how a wealth tax and a capital-income tax compare when each is used on its own;
- whether combining the two gives larger newborn welfare gains than either alone;
- how keeping or removing the estate tax changes these results.

The repository also contains the robustness checks reported in the thesis,
including alternative borrowing limits and markups, recalibration,
re-optimisation of the policies, wider capital-income subsidy ranges and finer
asset grids.

## Where to start

- [REPLICATION_GUIDE.md](REPLICATION_GUIDE.md) explains how to check the saved
  results without running the model, how to run the model again, which software
  is needed and where the data come from.
- [THESIS_RESULT_MAP.md](THESIS_RESULT_MAP.md) lists each of the 20 tables and
  five figures in the thesis, with the script and saved results behind it.

## What is included

- Fortran and Python source code for the model and each model variant.
- Calibration inputs and empirical targets.
- The three public 2022 Survey of Consumer Finances (SCF) archives used for the
  empirical targets, with source links and SHA-256 checksums, so the SCF table can
  be rebuilt directly from the original files.
- Saved results and numerical checks for each experiment.

Large equilibrium arrays, simulated populations and compiled programs are not
included. They are regenerated when the model is run.

## Repository layout

| Material | Location |
| --- | --- |
| Model and variants | [replication](replication), including frozen `src/` and `source/` directories |
| Empirical targets | [replication/calibration](replication/calibration) |
| Public SCF inputs and checksums | [data/scf2022](data/scf2022) |
| Audited SCF table rebuild | [scripts/rebuild_scf_audit.py](scripts/rebuild_scf_audit.py) |
| Policy evaluation and numerical grids | [replication/tools](replication/tools) |
| Implementation, recalibration and re-optimisation experiments | [replication/experiments](replication/experiments) |
| Saved policy-table inputs and age–ability welfare records | [replication/validation](replication/validation) |
| File hashes and source provenance | [SNAPSHOT_MANIFEST.json](replication/SNAPSHOT_MANIFEST.json) |
| File and script integrity, without running the model | [scripts/verify_replication_package.py](scripts/verify_replication_package.py) |
| Saved policy comparison, without running the model | [scripts/check_saved_policy_tables.py](scripts/check_saved_policy_tables.py) |
| Thesis result map and recomputation of reported values | [THESIS_RESULT_MAP.md](THESIS_RESULT_MAP.md), [scripts/check_thesis_results.py](scripts/check_thesis_results.py) |
| Portable model build and numerical rerun | [scripts/reproduce_reported_2022.py](scripts/reproduce_reported_2022.py) |

## Original model and licence

The model code is adapted from the code accompanying Guvenen, Kambourov, Kuruscu,
Ocampo and Chen, **“Use It or Lose It: Efficiency and Redistributional Effects of
Wealth Taxation”**, *Quarterly Journal of Economics* (2023),
[doi:10.1093/qje/qjac047](https://doi.org/10.1093/qje/qjac047). The original
code is at [ocamp020/GKKOC_QJE](https://github.com/ocamp020/GKKOC_QJE), branch
`Model_2.1`, commit `8e3de79`. The original authors' attribution is retained.
No licence is applied to third-party code or data.
