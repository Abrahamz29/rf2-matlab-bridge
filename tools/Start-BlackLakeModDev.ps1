param(
    [ValidateSet("Viewer", "Game")]
    [string]$Mode = "Viewer",

    [ValidateSet("250m", "500m", "1000m", "2000m", "5000m", "12000m")]
    [string]$Stage = "250m",

    [string]$Rf2Root = "C:\Program Files (x86)\Steam\steamapps\common\rFactor 2"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$modDevRoot = Join-Path $Rf2Root "ModDev"
$layoutName = "BlackLake_$Stage"
$sceneRel = "Locations\BlackLake\$layoutName\$layoutName.scn"
$sceneAbs = Join-Path $modDevRoot $sceneRel

if (-not (Test-Path $sceneAbs)) {
    throw "BlackLake scene not found: $sceneAbs"
}

if ($Mode -eq "Viewer") {
    $exe = Join-Path $modDevRoot "Viewerx64Release DX11.exe"
    if (-not (Test-Path $exe)) {
        throw "Viewer executable not found: $exe"
    }

    Start-Process -FilePath $exe -WorkingDirectory $modDevRoot
    Write-Host "Started ModDev Viewer for $layoutName"
    Write-Host "Configured scene: $sceneRel"
    exit 0
}

throw "Direct Game mode is not reliable for loose ModDev scenes in the current rFactor 2 UI. Use -Mode Viewer until BlackLake is packaged as rfcmp."
