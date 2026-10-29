param(
    [ValidateSet("bench_no_sim", "bench_sim")]
    [string]$Mode = "bench_no_sim",
    [ValidateSet("release", "debug", "aggressive")]
    [string]$BuildProfile = "release",
    [int]$Threads = 4,
    [switch]$SkipBuild,
    [switch]$SkipClean,
    [int]$KeepRunHistory = 0,
    [switch]$OrganizeBenchmarkSummaries
)

$ErrorActionPreference = "Stop"

if (-not $PSBoundParameters.ContainsKey("OrganizeBenchmarkSummaries")) {
    $OrganizeBenchmarkSummaries = $true
}

$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

$running = Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -match "GKK_Main\.a" }
if ($running) {
    throw "A GKK_Main.a process is already running. Stop it first, then rerun."
}

Write-Host ("[run_and_clean] mode={0}" -f $Mode) -ForegroundColor Cyan
$benchMode = if ($Mode -eq "bench_sim") { "bench_sim" } else { "bench" }
& powershell -ExecutionPolicy Bypass -File .\tools\run_benchmark.ps1 `
    -Mode $benchMode `
    -BuildProfile $BuildProfile `
    -Threads $Threads `
    -SkipBuild:$SkipBuild

if (-not $SkipClean) {
    $organizeFlag = 0
    if ($OrganizeBenchmarkSummaries) { $organizeFlag = 1 }
    & powershell -ExecutionPolicy Bypass -File .\tools\clean_workspace.ps1 `
        -KeepRunHistory $KeepRunHistory `
        -OrganizeBenchmarkSummaries $organizeFlag
}

Write-Host "[run_and_clean] done" -ForegroundColor Green
