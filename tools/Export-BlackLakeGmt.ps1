param(
    [ValidateSet("250m", "500m", "1000m", "2000m", "5000m", "12000m")]
    [string]$Stage = "250m",

    [string]$BlenderExe = "",

    [switch]$InstallModDev
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $PSScriptRoot
$script = Join-Path $projectRoot "tools\blender_export_blacklake.py"

if ([string]::IsNullOrWhiteSpace($BlenderExe)) {
    $BlenderExe = Join-Path $projectRoot "tools\downloads\blacklake_export\blender-2.83.20-windows-x64\blender.exe"
}

if (-not (Test-Path $BlenderExe)) {
    throw "Blender executable not found: $BlenderExe. Run tools\Install-BlackLakeExportToolchain.ps1 first."
}
if (-not (Test-Path $script)) {
    throw "Blender export script not found: $script"
}

$args = @(
    "--background",
    "--factory-startup",
    "--python",
    $script,
    "--",
    "--stage",
    $Stage
)

if ($InstallModDev) {
    $args += "--install-moddev"
}

& $BlenderExe @args
if ($LASTEXITCODE -ne 0) {
    throw "Blender export failed with exit code $LASTEXITCODE"
}
