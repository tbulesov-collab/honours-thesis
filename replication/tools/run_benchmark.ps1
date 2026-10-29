param(
  [ValidateSet("bench", "bench_sim")]
  [string]$Mode = "bench",
  [ValidateSet("release", "debug", "aggressive")]
  [string]$BuildProfile = "release",
  [int]$Threads = 4,
  [switch]$SkipBuild,
  [switch]$KeepSwitches
)

$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

function Set-FortranLogicalAssignment {
  param(
    [string]$Content,
    [string]$Name,
    [string]$Value
  )

  $pattern = "(?im)^(\s*" + [regex]::Escape($Name) + "\s*=\s*)(\.true\.|\.false\.)"
  return [regex]::Replace($Content, $pattern, ('$1' + $Value), 1)
}

function Configure-BenchmarkMode {
  param([string]$RunMode)

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
  if ($RunMode -eq "bench_sim") { $simulValue = ".true." }
  $content = Set-FortranLogicalAssignment -Content $content -Name "Simul_Switch" -Value $simulValue

  Set-Content -Path $path -Value $content -Encoding ascii
}

if (-not $KeepSwitches) {
  Configure-BenchmarkMode -RunMode $Mode
  Write-Host ("[run_benchmark] configured GKK_Main.f90 for {0}" -f $Mode) -ForegroundColor Cyan
}

if (-not $SkipBuild) {
  & powershell -ExecutionPolicy Bypass -File (Join-Path $PSScriptRoot "build.ps1") -Profile $BuildProfile
}

$env:OMP_NUM_THREADS = "$Threads"
$env:OMP_DYNAMIC = "FALSE"

Write-Host ("[run_benchmark] starting {0} with OMP_NUM_THREADS={1} using {2} build" -f $Mode, $Threads, $BuildProfile) -ForegroundColor Green
& cmd /c Compiled_Files_Baseline\GKK_Main.a
