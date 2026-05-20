param(
    [ValidateSet("250m", "500m", "1000m", "2000m", "5000m", "12000m")]
    [string]$Stage = "250m",

    [string]$ProjectRoot = "C:\Users\Victor\Documents\PYTHON\RFactor2",

    [string]$Rf2Root = "C:\Program Files (x86)\Steam\steamapps\common\rFactor 2",

    [string]$PythonExe = "C:\Users\Victor\.platformio\penv\Scripts\python.exe",

    [string]$ComponentName = "BlackLake_2026",

    [string]$ComponentVersion = "0.10",

    [switch]$Install
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$script = Join-Path $ProjectRoot "tools\mas2_blacklake_package.py"
if (-not (Test-Path $script)) {
    throw "MAS2 BlackLake package automation script not found: $script"
}
if (-not (Test-Path $PythonExe)) {
    throw "Python executable not found: $PythonExe"
}

$argsList = @(
    $script,
    "--stage", $Stage,
    "--project-root", $ProjectRoot,
    "--rf2-root", $Rf2Root,
    "--component-name", $ComponentName,
    "--component-version", $ComponentVersion
)

if ($Install) {
    $argsList += "--install"
}

& $PythonExe @argsList
if ($LASTEXITCODE -ne 0) {
    throw "BlackLake rfcmp build failed with exit code $LASTEXITCODE"
}
