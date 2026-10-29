# Mac Run Guide

This guide is for running the Guvenen wealth-tax replica code on macOS, including Apple Silicon machines.

## 1. Install The Compiler

The Fortran model needs `gfortran`. If Homebrew is already installed:

```bash
brew install gcc
```

Check that the compiler is available:

```bash
gfortran --version
```

If `brew` is not available, install Homebrew first from <https://brew.sh/>.

## 2. Start In The Repo Root

```bash
cd path/to/honours-thesis/replication
```

## 3. Run Common Modes

The Mac helper script configures `GKK_Main.f90` and runs the Fortran target.

Compile only, without running the model:

```bash
bash tools/run_mac.sh build
```

Recompute the benchmark from scratch:

```bash
THREADS=4 bash tools/run_mac.sh bench-recompute
```

Read existing benchmark files and run benchmark output logic:

```bash
THREADS=4 bash tools/run_mac.sh bench-read
```

Run benchmark with simulation outputs:

```bash
THREADS=4 bash tools/run_mac.sh bench-sim
```

Run the wealth-tax reform experiment:

```bash
THREADS=4 bash tools/run_mac.sh tax-reform
```

Run the optimal wealth-tax grid:

```bash
THREADS=4 bash tools/run_mac.sh optw
```

Run the optimal capital-tax grid:

```bash
THREADS=4 bash tools/run_mac.sh optk
```

Run the Python tables/figures pipeline:

```bash
bash tools/run_mac.sh python
```

## 4. What The Modes Change

- `bench-recompute`: `Benchmark_Only=.true.`, `compute_bench=.true.`, `Simul_Switch=.false.`
- `bench-read`: `Benchmark_Only=.true.`, `compute_bench=.false.`, `Simul_Switch=.false.`
- `bench-sim`: same as `bench-read`, but `Simul_Switch=.true.`
- `tax-reform`: `Tax_Reform=.true.`, reads benchmark files, and recomputes the experiment.
- `optw`: `Opt_Tax=.true.` and `Opt_Tax_KW=.false.` for wealth taxes.
- `optk`: `Opt_Tax=.true.` and `Opt_Tax_KW=.true.` for capital taxes.
- `build`: compiles `Compiled_Files_Baseline/GKK_Main.a` without running it.

Important code behavior: in `Solve_Benchmark`, `compute_bench=.true.` solves and writes benchmark results; `compute_bench=.false.` reads benchmark files.

## 5. Outputs

- Benchmark outputs: `Revision/Model_2.1_Local/`
- Benchmark cached files: `Revision/Model_2.1_Local/Bench_Files/`
- Wealth-tax outputs: `Revision/Model_2.1_Local/Opt_Tax_W/`
- Capital-tax outputs: `Revision/Model_2.1_Local/Opt_Tax_K/`
- Python outputs: `paper_python/outputs/`

## 6. Python Dependencies

The Python pipeline needs:

```bash
python3 -m pip install -r paper_python/requirements.txt
```

Then run:

```bash
python3 paper_python/run_pipeline.py
```

or:

```bash
bash tools/run_mac.sh python
```

## 7. Troubleshooting

If the script says `gfortran was not found`, install GCC with Homebrew and reopen Terminal.

If benchmark files are missing, run:

```bash
THREADS=4 bash tools/run_mac.sh bench-recompute
```

If a run crashes or gives suspicious numbers, lower the thread count:

```bash
THREADS=2 bash tools/run_mac.sh bench-recompute
```

If Matplotlib is slow on first import, the Mac script sets `MPLCONFIGDIR` and `XDG_CACHE_HOME` to `.cache/` inside the project.
