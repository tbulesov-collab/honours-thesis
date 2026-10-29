# Quick Commands

```powershell
Set-Location "path\to\honours-thesis\replication"
```

```powershell
C:\ProgramData\anaconda3\python.exe -m pip install -r .\paper_python\requirements.txt
```

```powershell
powershell -ExecutionPolicy Bypass -File .\tools\build.ps1 -Profile release
```

```powershell
powershell -ExecutionPolicy Bypass -File .\tools\run_benchmark.ps1 -Mode bench -BuildProfile release -Threads 4
```

```powershell
powershell -ExecutionPolicy Bypass -File .\tools\run_benchmark.ps1 -Mode bench_sim -BuildProfile release -Threads 4
```

```powershell
$rid = Get-Date -Format "yyyyMMdd_HHmmss"
powershell -ExecutionPolicy Bypass -File .\auto_run_missing_outputs_and_python.ps1 -Mode auto -RunId $rid -BuildProfile release -Threads 4
```

```powershell
Get-Content .\automation_logs\master_automation.log -Wait
```

```powershell
powershell -ExecutionPolicy Bypass -File .\tools\tune_threads.ps1 -Mode bench -BuildProfile release
```

```powershell
powershell -ExecutionPolicy Bypass -File .\tools\clean_workspace.ps1 -KeepRunHistory 2
```
