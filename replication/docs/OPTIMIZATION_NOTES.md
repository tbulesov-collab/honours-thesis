# Optimization Notes

## Safe Speed Order

1. Tune `OMP_NUM_THREADS` first.
2. Use the `release` build for most production runs.
3. Try `aggressive` only after comparing outputs against `release`.
4. Use `debug` only when you are investigating errors.

## What The Build Profiles Mean

- `release`: `-O3` plus OpenMP where needed. This is the default and usually the best tradeoff.
- `debug`: same structure, but with bounds checks in the heavy OpenMP files to catch array mistakes.
- `aggressive`: adds `-march=native`, `-funroll-loops`, and fast-math style flags. It can be faster, but it is less conservative numerically and is less portable across machines.

## Recommended Commands

Release benchmark:

```powershell
powershell -ExecutionPolicy Bypass -File .\tools\run_benchmark.ps1 -Mode bench -BuildProfile release -Threads 4
```

Thread tuning:

```powershell
powershell -ExecutionPolicy Bypass -File .\tools\tune_threads.ps1 -Mode bench -BuildProfile release
```

Aggressive benchmark comparison:

```powershell
powershell -ExecutionPolicy Bypass -File .\tools\tune_threads.ps1 -Mode bench -BuildProfile aggressive
```

## Practical Advice

- Start with `release`.
- If you want the fastest trustworthy setting, compare a few `release` runs across thread counts and keep the best thread count.
- Only move to `aggressive` if it saves meaningful time and the key output files still match closely enough for your purpose.
- Do not merge Fortran files just to make the code faster. That mostly hurts maintainability and rarely changes runtime materially.

## Higher-Risk Future Speedups

- Split wide optimal-tax scans into coarse and fine passes.
- Reduce file writes inside dense optimal-tax loops.
- Keep full distributional outputs only for the final selected policy points.
- Profile the hottest routines in `programfunctions.f90`, `Simulation_Module.f90`, and `GKK_Stats.f90` before doing deep code refactors.
