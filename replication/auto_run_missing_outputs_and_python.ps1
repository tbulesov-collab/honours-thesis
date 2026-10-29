param(
    [ValidateSet("status", "build", "bench", "bench_sim", "optw", "optk", "python", "auto", "guided")]
    [string]$Mode = "status",
    [string]$RunId = "",
    [int]$HeartbeatSeconds = 10,
    [switch]$PauseAfterPhase,
    [ValidateSet("release", "debug", "aggressive")]
    [string]$BuildProfile = "release",
    [int]$Threads = 4
)

$ErrorActionPreference = "Stop"
$ProgressPreference = "Continue"

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $root

if ([string]::IsNullOrWhiteSpace($RunId)) {
    $RunId = Get-Date -Format "yyyyMMdd_HHmmss"
}

$logDir = Join-Path $root "automation_logs"
New-Item -ItemType Directory -Force -Path $logDir | Out-Null
$masterLog = Join-Path $logDir "master_automation.log"
$durationFile = Join-Path $logDir "phase_duration_history.csv"

if (-not (Test-Path $durationFile)) {
    "timestamp,run_id,phase,duration_seconds,status" | Set-Content -Path $durationFile -Encoding ascii
}

function Log([string]$msg) {
    $ts = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    $line = "[$ts] $msg"
    $line | Tee-Object -FilePath $masterLog -Append
}

function Banner([string]$msg) {
    $bar = ("=" * 90)
    Write-Host $bar -ForegroundColor Cyan
    Write-Host $msg -ForegroundColor Cyan
    Write-Host $bar -ForegroundColor Cyan
    Log $msg
}

function Get-EstimatedSeconds([string]$phase) {
    if (-not (Test-Path $durationFile)) { return 0 }
    $rows = Import-Csv $durationFile | Where-Object { $_.phase -eq $phase -and $_.status -eq "success" }
    if ($null -eq $rows -or $rows.Count -eq 0) { return 0 }
    $vals = $rows | Select-Object -Last 5 | ForEach-Object { [double]$_.duration_seconds }
    if ($vals.Count -eq 0) { return 0 }
    return [int][Math]::Round(($vals | Measure-Object -Average).Average)
}

function Record-PhaseDuration([string]$phase, [datetime]$start, [string]$status = "success") {
    $dur = [int]((Get-Date) - $start).TotalSeconds
    $ts = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    Add-Content -Path $durationFile -Value "$ts,$RunId,$phase,$dur,$status"
}

function Get-FortranAssignment([string]$content, [string]$name) {
    $pat = "(?im)^\s*" + [regex]::Escape($name) + "\s*=\s*([^\r\n!]+)"
    $m = [regex]::Match($content, $pat)
    if ($m.Success) { return $m.Groups[1].Value.Trim() }
    return "<not found>"
}

function Write-RunConfiguration([string]$tag, [string]$targetDir) {
    New-Item -ItemType Directory -Force -Path $targetDir | Out-Null
    $f = Join-Path $root "GKK_Main.f90"
    $c = Get-Content $f -Raw
    $switches = @(
        "Benchmark_Only", "Tax_Reform", "compute_bench", "compute_exp", "compute_exp_pf", "compute_exp_prices",
        "Tax_Reform_tktw", "Opt_Tax", "Opt_Tax_KW", "Opt_Threshold", "Transition_Tax_Reform",
        "Transition_OT", "Simul_Switch", "NSU_Switch", "Log_Switch", "Progressive_Tax_Switch"
    )

    $lines = @()
    $lines += "Run ID: $RunId"
    $lines += "Tag: $tag"
    $lines += "Timestamp: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')"
    $lines += ""
    $lines += "Switch values parsed from GKK_Main.f90:"
    foreach ($s in $switches) {
        $lines += ("  {0} = {1}" -f $s, (Get-FortranAssignment -content $c -name $s))
    }
    $lines += ""
    $lines += "In this script mode, '$tag' means:"
    if ($tag -eq "optw") { $lines += "  Optimal wealth-tax run (Opt_Tax=.true., Opt_Tax_KW=.false.)" }
    elseif ($tag -eq "optk") { $lines += "  Optimal capital-tax run (Opt_Tax=.true., Opt_Tax_KW=.true.)" }
    elseif ($tag -eq "python") { $lines += "  Python paper pipeline run" }

    $metaFile = Join-Path $targetDir ("RUN_CONFIGURATION_" + $tag + ".txt")
    $lines | Set-Content -Path $metaFile -Encoding ascii
    Log "Wrote run configuration file: $metaFile"
}

function Set-FortranLogicalAssignment([string]$content, [string]$name, [string]$value) {
    $pattern = "(?im)^(\s*" + [regex]::Escape($name) + "\s*=\s*)(\.true\.|\.false\.)"
    return [regex]::Replace($content, $pattern, ('$1' + $value), 1)
}

function Update-GKKMainMode([string]$mode) {
    $f = Join-Path $root "GKK_Main.f90"
    $c = Get-Content $f -Raw

    # If benchmark files are missing, force a bootstrap benchmark solve first.
    $benchFile = Join-Path $root "Revision\\Model_2.1_Local\\Bench_Files\\cons"
    $needBenchmarkBootstrap = -not (Test-Path $benchFile)

    # Shared defaults
    $c = Set-FortranLogicalAssignment -content $c -name "Benchmark_Only" -value ".false."
    if ($needBenchmarkBootstrap) {
        $c = Set-FortranLogicalAssignment -content $c -name "compute_bench" -value ".true."
        Log "Benchmark files missing; setting compute_bench = .true. for this run."
    } else {
        $c = Set-FortranLogicalAssignment -content $c -name "compute_bench" -value ".false."
    }
    $c = Set-FortranLogicalAssignment -content $c -name "compute_exp" -value ".false."
    $c = Set-FortranLogicalAssignment -content $c -name "Simul_Switch" -value ".false."
    $c = Set-FortranLogicalAssignment -content $c -name "Tax_Reform" -value ".false."
    $c = Set-FortranLogicalAssignment -content $c -name "Opt_Tax" -value ".true."

    if ($mode -eq "optw") {
        $c = Set-FortranLogicalAssignment -content $c -name "Opt_Tax_KW" -value ".false."
        Log "Configured GKK_Main.f90 for optimal wealth-tax grid run."
    } elseif ($mode -eq "optk") {
        $c = Set-FortranLogicalAssignment -content $c -name "Opt_Tax_KW" -value ".true."
        Log "Configured GKK_Main.f90 for optimal capital-tax grid run."
    } else {
        throw "Unknown mode: $mode"
    }

    Set-Content -Path $f -Value $c -Encoding ascii
}

function Build-GKKMain {
    $phase = "build"
    $eta = Get-EstimatedSeconds $phase
    if ($eta -gt 0) {
        Write-Host ("[ETA] build ~ {0} min {1} sec" -f [int]($eta/60), ($eta%60)) -ForegroundColor DarkCyan
    }
    $start = Get-Date
    Write-Host "[BUILD] Compiling and linking GKK_Main.a ..." -ForegroundColor Green
    Log "Building GKK_Main executable (profile=$BuildProfile)."
    & powershell -ExecutionPolicy Bypass -File .\tools\build.ps1 -Profile $BuildProfile
    Write-Host "[BUILD] Completed." -ForegroundColor Green
    Log "Build completed."
    Record-PhaseDuration -phase $phase -start $start -status "success"
}

function Ensure-ResultFolders {
    $dirs = @(
        "Revision\\Model_2.1_Local\\Bench_Files",
        "Revision\\Model_2.1_Local\\Tax_Reform",
        "Revision\\Model_2.1_Local\\Tax_Reform\\Exp_Files",
        "Revision\\Model_2.1_Local\\Opt_Tax_W",
        "Revision\\Model_2.1_Local\\Opt_Tax_W\\Exp_Files",
        "Revision\\Model_2.1_Local\\Opt_Tax_K",
        "Revision\\Model_2.1_Local\\Opt_Tax_K\\Exp_Files"
    )
    foreach ($d in $dirs) {
        New-Item -ItemType Directory -Force -Path (Join-Path $root $d) | Out-Null
    }
    Log "Ensured required result folders exist."
}

function Run-GKKMain([string]$tag) {
    $phase = "run_" + $tag
    $eta = Get-EstimatedSeconds $phase
    if ($eta -gt 0) {
        Write-Host ("[ETA] {0} ~ {1} min {2} sec" -f $phase, [int]($eta/60), ($eta%60)) -ForegroundColor DarkCyan
    }

    $runLog = Join-Path $logDir ("run_" + $tag + ".log")
    $errLog = Join-Path $logDir ("run_" + $tag + ".err.log")
    if (Test-Path $runLog) { Remove-Item $runLog -Force }
    if (Test-Path $errLog) { Remove-Item $errLog -Force }

    $env:OMP_NUM_THREADS = "$Threads"
    $env:OMP_DYNAMIC = "FALSE"
    Banner "RUN START: $tag | run_id=$RunId"
    Log "Starting GKK_Main.a for $tag. Stdout: $runLog"

    $start = Get-Date
    $p = Start-Process -FilePath "cmd.exe" `
        -ArgumentList "/c", "Compiled_Files_Baseline\GKK_Main.a" `
        -RedirectStandardOutput $runLog `
        -RedirectStandardError $errLog `
        -PassThru

    while (-not $p.HasExited) {
        Start-Sleep -Seconds $HeartbeatSeconds
        $elapsed = [int]((Get-Date) - $start).TotalSeconds
        $lastLine = ""
        if (Test-Path $runLog) {
            $last = Get-Content $runLog -Tail 1 -ErrorAction SilentlyContinue
            if ($null -ne $last) { $lastLine = ($last -join " ").Trim() }
        }

        $pct = -1
        if ($eta -gt 0) {
            $pct = [Math]::Min(99, [int](100.0 * $elapsed / $eta))
        }
        Write-Progress -Activity "Running GKK_Main ($tag)" -Status "Elapsed ${elapsed}s" -PercentComplete $pct

        if ([string]::IsNullOrWhiteSpace($lastLine)) {
            Write-Host ("[{0}] [{1}] elapsed {2}s (waiting for first log line)" -f (Get-Date -Format "HH:mm:ss"), $tag, $elapsed) -ForegroundColor Yellow
            Log "[$tag] running... elapsed ${elapsed}s"
        } else {
            Write-Host ("[{0}] [{1}] elapsed {2}s | {3}" -f (Get-Date -Format "HH:mm:ss"), $tag, $elapsed, $lastLine) -ForegroundColor Yellow
            Log "[$tag] running... elapsed ${elapsed}s | last: $lastLine"
        }
        $p.Refresh()
    }
    $p.WaitForExit()

    $exitCode = $p.ExitCode
    $interrupted = $false
    if (Test-Path $errLog) {
        $errTail = Get-Content $errLog -Tail 40 -ErrorAction SilentlyContinue
        if (($errTail -join "`n") -match "\^C") { $interrupted = $true }
    }
    if ($interrupted) {
        Record-PhaseDuration -phase $phase -start $start -status "interrupted"
        throw "GKK_Main.a for $tag was interrupted by user (Ctrl+C). See $runLog and $errLog"
    }

    # Some Windows wrappers report null/non-zero exit code even when run completed successfully.
    # Infer completion from terminal markers in stdout.
    $completed = $false
    if (Test-Path $runLog) {
        $tail = Get-Content $runLog -Tail 200 -ErrorAction SilentlyContinue
        $tailText = ($tail -join "`n")
        if ($tailText -match "Total time\s*=" -or $tailText -match "Writing of experimental results completed") {
            $completed = $true
        }
    }
    if ($completed -and ($null -eq $exitCode -or $exitCode -ne 0)) {
        Write-Host ("[{0}] [{1}] completed (exit code {2}, inferred from log)." -f (Get-Date -Format "HH:mm:ss"), $tag, $exitCode) -ForegroundColor Green
        Log "[$tag] completion inferred from run log despite wrapper exit code '$exitCode'."
        $exitCode = 0
    } elseif ($null -eq $exitCode) {
        $exitCode = -1
    }
    if ($exitCode -ne 0) {
        Record-PhaseDuration -phase $phase -start $start -status "failed"
        throw "GKK_Main.a failed for $tag with exit code $exitCode. See $runLog and $errLog"
    }

    Record-PhaseDuration -phase $phase -start $start -status "success"
    Write-Host ("[{0}] [{1}] completed successfully." -f (Get-Date -Format "HH:mm:ss"), $tag) -ForegroundColor Green
    Log "Finished GKK_Main.a for $tag."
}

function Archive-RunOutputs([string]$tag) {
    $modelRoot = Join-Path $root "Revision\Model_2.1_Local"
    $runRoot = Join-Path $modelRoot ("Run_History\Run_" + $RunId)
    New-Item -ItemType Directory -Force -Path $runRoot | Out-Null

    if ($tag -eq "optw") {
        $src = Join-Path $modelRoot "Opt_Tax_W"
    } elseif ($tag -eq "optk") {
        $src = Join-Path $modelRoot "Opt_Tax_K"
    } else {
        throw "Unknown archive tag: $tag"
    }

    if (-not (Test-Path $src)) {
        Log "WARNING: Cannot archive $tag because source folder is missing: $src"
        return
    }

    $dst = Join-Path $runRoot (Split-Path -Leaf $src)
    if (Test-Path $dst) { Remove-Item -Recurse -Force $dst }
    Copy-Item -Path $src -Destination $dst -Recurse -Force
    Write-RunConfiguration -tag $tag -targetDir $runRoot
    Write-Host ("[ARCHIVE] {0} -> {1}" -f $src, $dst) -ForegroundColor Green
    Log "Archived run outputs: $src -> $dst"
}

function Ensure-WideGridOutputs {
    $wDir = Join-Path $root "Revision\Model_2.1_Local\Opt_Tax_W\Wide_Grid"
    $kDir = Join-Path $root "Revision\Model_2.1_Local\Opt_Tax_K\Wide_Grid"
    New-Item -ItemType Directory -Force -Path $wDir | Out-Null
    New-Item -ItemType Directory -Force -Path $kDir | Out-Null

    $wSrc = Join-Path $root "Revision\Model_2.1_Local\Opt_Tax_W\Stats_by_tau_w.txt"
    $kSrc1 = Join-Path $root "Revision\Model_2.1_Local\Opt_Tax_K\Stats_by_tau_k.txt"
    $kSrc2 = Join-Path $root "Revision\Model_2.1_Local\Opt_Tax_K\Stats_by_tau_k_2.txt"

    if (Test-Path $wSrc) {
        Copy-Item $wSrc (Join-Path $wDir "Stats_by_tau_w.txt") -Force
        Log "Copied Stats_by_tau_w.txt into Wide_Grid."
    } else {
        Log "WARNING: Missing $wSrc"
    }

    if (Test-Path $kSrc1) {
        Copy-Item $kSrc1 (Join-Path $kDir "Stats_by_tau_k.txt") -Force
        Log "Copied Stats_by_tau_k.txt into Wide_Grid."
    } elseif (Test-Path $kSrc2) {
        Copy-Item $kSrc2 (Join-Path $kDir "Stats_by_tau_k.txt") -Force
        Log "Copied Stats_by_tau_k_2.txt into Wide_Grid as Stats_by_tau_k.txt."
    } else {
        Log "WARNING: Missing both $kSrc1 and $kSrc2"
    }
}

function Run-PythonPipeline {
    $phase = "python_pipeline"
    $eta = Get-EstimatedSeconds $phase
    if ($eta -gt 0) {
        Write-Host ("[ETA] python pipeline ~ {0} min {1} sec" -f [int]($eta/60), ($eta%60)) -ForegroundColor DarkCyan
    }

    $start = Get-Date
    $py = "C:\ProgramData\anaconda3\python.exe"
    Log "Running Python pipeline using $py"
    & $py paper_python\run_pipeline.py
    Log "Python pipeline completed."
    Record-PhaseDuration -phase $phase -start $start -status "success"
}

function Show-Status {
    Banner "RUN STATUS / HOW TO RUN MANUALLY"
    Write-Host ("Current run id: {0}" -f $RunId) -ForegroundColor Green
    Write-Host "Modes:"
            Write-Host "  -Mode build"
            Write-Host "  -Mode bench"
            Write-Host "  -Mode bench_sim"
            Write-Host "  -Mode optw"
    Write-Host "  -Mode optk"
    Write-Host "  -Mode python"
    Write-Host "  -Mode auto   (full automation)"
    Write-Host "  -Mode guided (auto with prompts between phases)"
    Write-Host ""
    Write-Host "Suggested manual sequence (intervenable):"
    Write-Host ("  1) powershell -ExecutionPolicy Bypass -File .\auto_run_missing_outputs_and_python.ps1 -Mode optw -RunId {0}" -f $RunId)
    Write-Host ("  2) inspect outputs/logs in Revision\Model_2.1_Local\Run_History\Run_{0}" -f $RunId)
    Write-Host ("  3) powershell -ExecutionPolicy Bypass -File .\auto_run_missing_outputs_and_python.ps1 -Mode optk -RunId {0}" -f $RunId)
    Write-Host ("  4) powershell -ExecutionPolicy Bypass -File .\auto_run_missing_outputs_and_python.ps1 -Mode python -RunId {0}" -f $RunId)
    Write-Host ""
    $phases = @("build","run_optw","run_optk","python_pipeline")
    foreach ($p in $phases) {
        $eta = Get-EstimatedSeconds $p
        if ($eta -gt 0) {
            Write-Host ("ETA {0}: ~{1} min {2} sec (avg of last <=5 runs)" -f $p, [int]($eta/60), ($eta%60)) -ForegroundColor DarkCyan
        } else {
            Write-Host ("ETA {0}: no history yet" -f $p) -ForegroundColor DarkYellow
        }
    }
}

function Confirm-Continue([string]$nextStep) {
    $ans = Read-Host ("Continue to {0}? (Y/N)" -f $nextStep)
    if ($ans -notmatch '^(?i)y(es)?$') {
        throw "Stopped by user before phase: $nextStep"
    }
}

try {
    switch ($Mode) {
        "status" {
            Show-Status
        }
        "build" {
            Banner "MODE: build"
            Build-GKKMain
        }
        "bench" {
            Banner "MODE: bench"
            & powershell -ExecutionPolicy Bypass -File .\tools\run_benchmark.ps1 -Mode bench -BuildProfile $BuildProfile -Threads $Threads
        }
        "bench_sim" {
            Banner "MODE: bench_sim"
            & powershell -ExecutionPolicy Bypass -File .\tools\run_benchmark.ps1 -Mode bench_sim -BuildProfile $BuildProfile -Threads $Threads
        }
        "optw" {
            Banner "MODE: optw"
            Update-GKKMainMode -mode "optw"
            Ensure-ResultFolders
            Build-GKKMain
            Run-GKKMain -tag "optw"
            Archive-RunOutputs -tag "optw"
        }
        "optk" {
            Banner "MODE: optk"
            Update-GKKMainMode -mode "optk"
            Ensure-ResultFolders
            Build-GKKMain
            Run-GKKMain -tag "optk"
            Archive-RunOutputs -tag "optk"
        }
        "python" {
            Banner "MODE: python"
            Ensure-WideGridOutputs
            Run-PythonPipeline
            Write-RunConfiguration -tag "python" -targetDir (Join-Path $root ("Revision\Model_2.1_Local\Run_History\Run_" + $RunId))
        }
        "auto" {
            Banner "AUTOMATION STARTED"
            Get-Process -ErrorAction SilentlyContinue | Where-Object { $_.ProcessName -like "*GKK_Main*" } | ForEach-Object {
                try { Stop-Process -Id $_.Id -Force } catch {}
            }
            Log "Stopped existing GKK_Main processes (if any)."

            Update-GKKMainMode -mode "optw"
            Ensure-ResultFolders
            Build-GKKMain
            Run-GKKMain -tag "optw"
            Archive-RunOutputs -tag "optw"
            if ($PauseAfterPhase) { Confirm-Continue -nextStep "optk" }

            Update-GKKMainMode -mode "optk"
            Ensure-ResultFolders
            Build-GKKMain
            Run-GKKMain -tag "optk"
            Archive-RunOutputs -tag "optk"
            if ($PauseAfterPhase) { Confirm-Continue -nextStep "python pipeline" }

            Ensure-WideGridOutputs
            Banner "PYTHON PIPELINE START"
            Run-PythonPipeline
            Write-RunConfiguration -tag "python" -targetDir (Join-Path $root ("Revision\Model_2.1_Local\Run_History\Run_" + $RunId))

            Banner "ALL RUNS COMPLETED SUCCESSFULLY"
            Log "All requested runs completed: optw + optk + python pipeline."
        }
        "guided" {
            Banner "GUIDED MODE STARTED"
            Get-Process -ErrorAction SilentlyContinue | Where-Object { $_.ProcessName -like "*GKK_Main*" } | ForEach-Object {
                try { Stop-Process -Id $_.Id -Force } catch {}
            }
            Log "Stopped existing GKK_Main processes (if any)."

            Update-GKKMainMode -mode "optw"
            Ensure-ResultFolders
            Build-GKKMain
            Run-GKKMain -tag "optw"
            Archive-RunOutputs -tag "optw"
            Confirm-Continue -nextStep "optk"

            Update-GKKMainMode -mode "optk"
            Ensure-ResultFolders
            Build-GKKMain
            Run-GKKMain -tag "optk"
            Archive-RunOutputs -tag "optk"
            Confirm-Continue -nextStep "python pipeline"

            Ensure-WideGridOutputs
            Banner "PYTHON PIPELINE START"
            Run-PythonPipeline
            Write-RunConfiguration -tag "python" -targetDir (Join-Path $root ("Revision\Model_2.1_Local\Run_History\Run_" + $RunId))

            Banner "GUIDED MODE COMPLETED SUCCESSFULLY"
            Log "All requested runs completed in guided mode."
        }
    }
}
catch {
    Log ("ERROR: " + $_.Exception.Message)
    throw
}
