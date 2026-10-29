param(
    [int]$KeepRunHistory = 0,
    [string]$OrganizeBenchmarkSummaries = "0"
)

$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

$modelRoot = Join-Path $root "Revision\Model_2.1_Local"
$artifactRoot = Join-Path $modelRoot "_Artifacts"
$runtimeRoot = Join-Path $artifactRoot "fortran_runtime"
$modelRuntimeRoot = Join-Path $modelRoot "Model_Inputs_Runtime"

function To-Bool {
    param([string]$v)
    if ($null -eq $v) { return $false }
    switch -Regex ($v.Trim().ToLowerInvariant()) {
        "^(1|true|t|yes|y)$" { return $true }
        "^(0|false|f|no|n|)$" { return $false }
        default { return $false }
    }
}

$organizeSummaries = To-Bool $OrganizeBenchmarkSummaries

New-Item -ItemType Directory -Force -Path $runtimeRoot | Out-Null
New-Item -ItemType Directory -Force -Path $modelRuntimeRoot | Out-Null

Write-Host "[clean] moving root fort.* runtime files into $runtimeRoot"
Get-ChildItem -Path $root -File -Filter "fort.*" -ErrorAction SilentlyContinue | ForEach-Object {
    $dst = Join-Path $runtimeRoot $_.Name
    if (Test-Path $dst) {
        $stamp = Get-Date -Format "yyyyMMdd_HHmmss"
        $dst = Join-Path $runtimeRoot ($_.BaseName + "_" + $stamp + $_.Extension)
    }
    Move-Item -Force -Path $_.FullName -Destination $dst
}

$runHistory = Join-Path $modelRoot "Run_History"
if (Test-Path $runHistory) {
    $runs = Get-ChildItem -Path $runHistory -Directory | Sort-Object LastWriteTime -Descending
    $toDelete = @()
    if ($KeepRunHistory -lt $runs.Count) {
        $toDelete = $runs | Select-Object -Skip $KeepRunHistory
    }
    if ($toDelete.Count -gt 0) {
        Write-Host ("[clean] deleting {0} run history folder(s)" -f $toDelete.Count)
        $toDelete | ForEach-Object { Remove-Item -Recurse -Force $_.FullName }
    } else {
        Write-Host "[clean] no run history folders deleted"
    }
}

$runtimeModelFiles = @("params", "agrid", "zgrid", "lambdagrid", "egrid", "Ret_Y", "P_e", "eff_un", "survP")
Write-Host "[clean] moving model runtime files into Model_Inputs_Runtime"
foreach ($name in $runtimeModelFiles) {
    $src = Join-Path $modelRoot $name
    if (Test-Path $src) {
        Move-Item -Path $src -Destination (Join-Path $modelRuntimeRoot $name) -Force
    }
}

$benchSummaryRoot = Join-Path $modelRoot "Benchmark_Summaries"
if ($organizeSummaries) {
    New-Item -ItemType Directory -Force -Path $benchSummaryRoot | Out-Null
    $latestDir = Join-Path $benchSummaryRoot "latest"
    New-Item -ItemType Directory -Force -Path $latestDir | Out-Null

    # Keep files used by paper_python at model root.
    $keepAtRoot = @("output.txt", "Entrepreneur_by_age.txt")
    # Also mirror these key files into latest summary folder for convenience.
    $copyToLatest = @("output.txt", "Entrepreneur_by_age.txt")

    Write-Host "[clean] organizing root benchmark *.txt into Benchmark_Summaries/latest"
    Get-ChildItem -Path $modelRoot -File -Filter "*.txt" -ErrorAction SilentlyContinue |
        Where-Object { $keepAtRoot -notcontains $_.Name } |
        ForEach-Object {
            $dst = Join-Path $latestDir $_.Name
            Move-Item -Path $_.FullName -Destination $dst -Force
        }

    foreach ($name in $copyToLatest) {
        $src = Join-Path $modelRoot $name
        if (Test-Path $src) {
            Copy-Item -Path $src -Destination (Join-Path $latestDir $name) -Force
        }
    }
}

$autoLogs = Join-Path $root "automation_logs"
if (Test-Path $autoLogs) {
    Write-Host "[clean] deleting per-run logs in automation_logs (keeping master/duration)"
    Get-ChildItem -Path $autoLogs -File -ErrorAction SilentlyContinue |
        Where-Object { $_.Name -like "run_*.log" -or $_.Name -like "run_*.err.log" } |
        Remove-Item -Force
}

Write-Host "[clean] workspace cleanup complete"
