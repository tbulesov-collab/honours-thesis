# Run Guide

## Start In The Repo Root

```powershell
Set-Location "path\to\honours-thesis\replication"
```

## Main Commands

Build only:

```powershell
powershell -ExecutionPolicy Bypass -File .\tools\build.ps1 -Profile release
```

Benchmark only:

```powershell
powershell -ExecutionPolicy Bypass -File .\tools\run_benchmark.ps1 -Mode bench -BuildProfile release -Threads 4
```

Benchmark plus simulation outputs:

```powershell
powershell -ExecutionPolicy Bypass -File .\tools\run_benchmark.ps1 -Mode bench_sim -BuildProfile release -Threads 4
```

Optimal wealth-tax grid:

```powershell
$rid = Get-Date -Format "yyyyMMdd_HHmmss"
powershell -ExecutionPolicy Bypass -File .\auto_run_missing_outputs_and_python.ps1 -Mode optw -RunId $rid -BuildProfile release -Threads 4
```

Optimal capital-tax grid:

```powershell
$rid = Get-Date -Format "yyyyMMdd_HHmmss"
powershell -ExecutionPolicy Bypass -File .\auto_run_missing_outputs_and_python.ps1 -Mode optk -RunId $rid -BuildProfile release -Threads 4
```

Full automation:

```powershell
$rid = Get-Date -Format "yyyyMMdd_HHmmss"
powershell -ExecutionPolicy Bypass -File .\auto_run_missing_outputs_and_python.ps1 -Mode auto -RunId $rid -BuildProfile release -Threads 4
```

Python pipeline only:

```powershell
C:\ProgramData\anaconda3\python.exe .\paper_python\run_pipeline.py
```

## What Each Mode Does

- `bench`: sets `compute_bench=.true.`, disables tax reform, optimal tax, and transitions, and leaves `Simul_Switch=.false.`.
- `bench_sim`: same as `bench`, but turns `Simul_Switch=.true.`.
- `optw`: turns on `Opt_Tax=.true.` and sets `Opt_Tax_KW=.false.`.
- `optk`: turns on `Opt_Tax=.true.` and sets `Opt_Tax_KW=.true.`.
- `auto`: runs `optw`, then `optk`, then the Python pipeline.
- `build`: compiles only.

## Build Profiles

- `release`: default and recommended.
- `debug`: slower, but safer for diagnosing array bounds issues.
- `aggressive`: fastest candidate, but may slightly change floating-point results.

## Output Locations

- Benchmark and model outputs: `Revision\Model_2.1_Local\`
- Wealth-tax outputs: `Revision\Model_2.1_Local\Opt_Tax_W\`
- Capital-tax outputs: `Revision\Model_2.1_Local\Opt_Tax_K\`
- Archived runs: `Revision\Model_2.1_Local\Run_History\Run_<RunId>\`
- Python outputs: `paper_python\outputs\`
- Build artifacts: `Compiled_Files_Baseline\`

## Monitoring

Watch the master automation log:

```powershell
Get-Content .\automation_logs\master_automation.log -Wait
```

Watch a specific phase:

```powershell
Get-Content .\automation_logs\run_optw.log -Tail 60
Get-Content .\automation_logs\run_optw.err.log -Tail 60
```

## Thread Tuning

Tune benchmark speed across thread counts:

```powershell
powershell -ExecutionPolicy Bypass -File .\tools\tune_threads.ps1 -Mode bench -BuildProfile release
```

The results are saved to `automation_logs/thread_tuning/thread_tuning_results.csv`.

## Cleanup

```powershell
powershell -ExecutionPolicy Bypass -File .\tools\clean_workspace.ps1 -KeepRunHistory 2
```

## Common Problems

- Missing `Bench_Files\cons`: run `bench` once to regenerate benchmark files.
- Crashes or suspicious output in `release`: retry with `-BuildProfile debug`.
- Small speed gains or changed numbers in `aggressive`: compare outputs before trusting it for final tables.
