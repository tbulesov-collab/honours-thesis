# Numerical model and saved results

This directory contains the Fortran model, numerical drivers, frozen variant
sources, calibration inputs and compact saved results. For installation, data and
instructions for reproducing each thesis result, see the
[replication guide](../REPLICATION_GUIDE.md) and the
[thesis result map](../THESIS_RESULT_MAP.md).

- `tools/`: build, calibration, policy-evaluation and post-processing code.
- `experiments/`: implementation sensitivity, recalibration, policy
  re-optimisation and robustness experiments, each with its own README.
- `calibration/`: empirical inputs, calibrated parameters and saved policy results.
- `validation/`: the saved inputs for Table VIII and the age–ability welfare
  records.
- `docs/`: notes on the empirical definitions, financing data, percentile
  statistics and run options.
- `SNAPSHOT_MANIFEST.json`: SHA-256 hashes and sizes of the files in this directory.

Large solver states and compiled programs are not included; they are regenerated
when the model is run. Saved run manifests record each run's settings; absolute
paths in them refer to the original machine and are not paths to use.

The model code is adapted from the code accompanying Guvenen, Kambourov, Kuruscu,
Ocampo and Chen, "Use It or Lose It: Efficiency and Redistributional Effects of
Wealth Taxation", *Quarterly Journal of Economics* (2023). Their attribution is
kept in the sources and in the root README.
