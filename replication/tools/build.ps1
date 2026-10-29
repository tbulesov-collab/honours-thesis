param(
  [ValidateSet("release", "debug", "aggressive")]
  [string]$Profile = "release",
  [string]$BuildDir = "Compiled_Files_Baseline"
)

$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

New-Item -ItemType Directory -Force -Path $BuildDir | Out-Null

$sources = @(
  @{ Source = "NRTYPE.F90";            Object = "NRTYPE.o";            OpenMP = $false; Bounds = $false },
  @{ Source = "NRUTIL.F90";            Object = "NRUTIL.o";            OpenMP = $false; Bounds = $false },
  @{ Source = "Toolbox.f90";           Object = "Toolbox.o";           OpenMP = $false; Bounds = $false },
  @{ Source = "parameters.f90";        Object = "parameters.o";        OpenMP = $false; Bounds = $false },
  @{ Source = "global.f90";            Object = "global.o";            OpenMP = $false; Bounds = $false },
  @{ Source = "programfunctions.f90";  Object = "programfunctions.o";  OpenMP = $true;  Bounds = $true  },
  @{ Source = "Simulation_Module.f90"; Object = "Simulation_Module.o"; OpenMP = $true;  Bounds = $true  },
  @{ Source = "GKK_Stats.f90";         Object = "GKK_Stats.o";         OpenMP = $true;  Bounds = $true  },
  @{ Source = "Opt_Tax_Parameters.f90";Object = "Opt_Tax_Parameters.o";OpenMP = $false; Bounds = $false },
  @{ Source = "Opt_Tax_Functions.f90"; Object = "Opt_Tax_Functions.o"; OpenMP = $false; Bounds = $false }
)

switch ($Profile) {
  "release" {
    $banner = "[build] compiling release profile (O3 + OpenMP, no bounds-check)..."
    $baseFlags = @("-O3")
  }
  "debug" {
    $banner = "[build] compiling debug profile (O3 + OpenMP + bounds-check)..."
    $baseFlags = @("-O3")
  }
  "aggressive" {
    $banner = "[build] compiling aggressive profile (O3 + OpenMP + native CPU + fast-math)..."
    $baseFlags = @("-O3", "-march=native", "-funroll-loops", "-ffast-math", "-fno-protect-parens")
  }
}

Write-Host $banner

function Get-CompileFlags {
  param([bool]$UseOpenMP, [bool]$UseBounds)

  $flags = @()
  if ($UseOpenMP) { $flags += "-fopenmp" }
  $flags += $baseFlags
  if ($Profile -eq "debug" -and $UseBounds) { $flags += "-fbounds-check" }
  return $flags
}

foreach ($entry in $sources) {
  $sourcePath = $entry.Source
  $objectPath = Join-Path $BuildDir $($entry.Object)
  $flags = Get-CompileFlags -UseOpenMP $entry.OpenMP -UseBounds $entry.Bounds
  $compileArgs = @()
  $compileArgs += $flags
  $compileArgs += "-J$BuildDir"
  $compileArgs += "-c"
  $compileArgs += $sourcePath
  $compileArgs += "-o"
  $compileArgs += $objectPath
  & gfortran @compileArgs
}

$linkFlags = Get-CompileFlags -UseOpenMP $true -UseBounds $true
$linkInputs = @(
  "GKK_Main.f90",
  (Join-Path $BuildDir "NRTYPE.o"),
  (Join-Path $BuildDir "NRUTIL.o"),
  (Join-Path $BuildDir "Toolbox.o"),
  (Join-Path $BuildDir "parameters.o"),
  (Join-Path $BuildDir "global.o"),
  (Join-Path $BuildDir "programfunctions.o"),
  (Join-Path $BuildDir "Simulation_Module.o"),
  (Join-Path $BuildDir "GKK_Stats.o"),
  (Join-Path $BuildDir "Opt_Tax_Parameters.o"),
  (Join-Path $BuildDir "Opt_Tax_Functions.o")
)
$linkArgs = @()
$linkArgs += $linkFlags
$linkArgs += "-I$BuildDir"
$linkArgs += $linkInputs
$linkArgs += "-o"
$linkArgs += (Join-Path $BuildDir "GKK_Main.a")
& gfortran @linkArgs

Write-Host ("[build] done: {0}" -f (Join-Path $BuildDir "GKK_Main.a"))
if ($Profile -eq "aggressive") {
  Write-Host "[build] note: aggressive flags can slightly change floating-point results."
}
