param(
  [string]$Threads = "2,4,6,8,10,12,16",
  [string]$ExePath = ".\Compiled_Files_Baseline\GKK_Main.a",
  [string]$LogDir = ".\automation_logs\thread_tuning",
  [ValidateSet("current", "bench", "bench_sim")]
  [string]$Mode = "bench",
  [ValidateSet("release", "debug", "aggressive")]
  [string]$BuildProfile = "release"
)

$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

$threadValues = @(
  $Threads -split '[,\s]+' |
    Where-Object { -not [string]::IsNullOrWhiteSpace($_) } |
    ForEach-Object { [int]$_ }
)

function Set-FortranLogicalAssignment {
  param(
    [string]$Content,
    [string]$Name,
    [string]$Value
  )

  $pattern = "(?im)^(\s*" + [regex]::Escape($Name) + "\s*=\s*)(\.true\.|\.false\.)"
  return [regex]::Replace($Content, $pattern, ('$1' + $Value), 1)
}

if ($Mode -eq "bench" -or $Mode -eq "bench_sim") {
  $path = Join-Path $root "GKK_Main.f90"
  $content = Get-Content $path -Raw
  $pairs = @(
    @{ Name = "Benchmark_Only";        Value = ".true."  },
    @{ Name = "Tax_Reform";            Value = ".false." },
    @{ Name = "compute_bench";         Value = ".true."  },
    @{ Name = "compute_exp";           Value = ".false." },
    @{ Name = "compute_exp_pf";        Value = ".false." },
    @{ Name = "compute_exp_prices";    Value = ".false." },
    @{ Name = "Tax_Reform_tktw";       Value = ".false." },
    @{ Name = "Opt_Tax";               Value = ".false." },
    @{ Name = "Opt_Threshold";         Value = ".false." },
    @{ Name = "Transition_Tax_Reform"; Value = ".false." },
    @{ Name = "Transition_OT";         Value = ".false." }
  )

  foreach ($pair in $pairs) {
    $content = Set-FortranLogicalAssignment -Content $content -Name $pair.Name -Value $pair.Value
  }

  $simulValue = ".false."
  if ($Mode -eq "bench_sim") { $simulValue = ".true." }
  $content = Set-FortranLogicalAssignment -Content $content -Name "Simul_Switch" -Value $simulValue
  Set-Content -Path $path -Value $content -Encoding ascii
}

powershell -ExecutionPolicy Bypass -File ".\tools\build.ps1" -Profile $BuildProfile

New-Item -ItemType Directory -Force -Path $LogDir | Out-Null

$results = @()

foreach ($t in $threadValues) {
  $log = Join-Path $LogDir ("run_threads_{0}.log" -f $t)
  $errLog = Join-Path $LogDir ("run_threads_{0}.err.log" -f $t)
  Write-Host ("[tune_threads] running with OMP_NUM_THREADS={0}" -f $t)
  $env:OMP_NUM_THREADS = "$t"
  $env:OMP_DYNAMIC = "FALSE"

  if (Test-Path $log) { Remove-Item $log -Force }
  if (Test-Path $errLog) { Remove-Item $errLog -Force }

  $start = Get-Date
  $exeFullPath = (Resolve-Path $ExePath).Path
  $proc = Start-Process -FilePath $exeFullPath `
    -RedirectStandardOutput $log `
    -RedirectStandardError $errLog `
    -PassThru `
    -Wait `
    -NoNewWindow
  $end = Get-Date

  if ($proc.ExitCode -ne 0) {
    throw "Run failed for OMP_NUM_THREADS=$t with exit code $($proc.ExitCode). See $log and $errLog"
  }

  $elapsed = ($end - $start).TotalMinutes
  $results += [pscustomobject]@{
    OMP_NUM_THREADS = $t
    Minutes         = [math]::Round($elapsed, 3)
    Log             = $log
  }
}

$outCsv = Join-Path $LogDir "thread_tuning_results.csv"
$results | Sort-Object Minutes | Tee-Object -Variable sorted | Export-Csv -NoTypeInformation -Path $outCsv

Write-Host "[tune_threads] done. Fastest first:"
$sorted | Format-Table -AutoSize | Out-String | Write-Host
Write-Host ("[tune_threads] saved: {0}" -f $outCsv)
