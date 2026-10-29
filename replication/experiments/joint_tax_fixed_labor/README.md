# Fixed-labour joint tax optimizer

This isolated experiment fixes the benchmark labour-tax schedule (`psi=0.776`)
and directly optimizes the wealth, capital-income, and estate tax rates subject
to the benchmark-government-revenue constraint.

The copied `GKK_Main_fixed_labor.f90` contains the experiment-specific model
change. The build script compiles a separate executable into `build/`; it does
not reconfigure or overwrite the main model executable. Candidate results and
logs are stored locally under `results/` and `logs/`.

The optimizer reads the combined 2022 SCF and 2022 business-financing benchmark
from `calibration/runs/business_financing_2022/rn_reform` in the main project.
