param(
    [ValidateSet("250m", "500m", "1000m", "2000m", "5000m", "12000m")]
    [string]$Stage = "250m",

    [string]$ModDevRoot = "C:\Program Files (x86)\Steam\steamapps\common\rFactor 2\ModDev"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$locationRoot = Join-Path $ModDevRoot "Locations\BlackLake"
$layoutName = "BlackLake_$Stage"
$layoutRoot = Join-Path $locationRoot $layoutName
$mapsRoot = Join-Path $locationRoot "Assets\Maps"
$gmtFiles = @(
    "BlackLake_Surface.gmt",
    "BlackLake_Markings.gmt",
    "BlackLake_Reference.gmt",
    "xfinish.gmt",
    "xsector1.gmt",
    "xsector2.gmt",
    "xpitin.gmt",
    "xpitout.gmt"
)

$requiredFiles = @(
    (Join-Path $locationRoot "BlackLake.tdf"),
    (Join-Path $layoutRoot "$layoutName.gdb"),
    (Join-Path $layoutRoot "$layoutName.scn"),
    (Join-Path $layoutRoot "$layoutName.AIW"),
    (Join-Path $layoutRoot "$layoutName.wet"),
    (Join-Path $mapsRoot "DIFFUSE01.DDS")
)
$requiredFiles += $gmtFiles | ForEach-Object { Join-Path $layoutRoot $_ }

$missing = @()
foreach ($file in $requiredFiles) {
    if (-not (Test-Path $file)) {
        $missing += $file
    }
}

$staleVenueGdb = Join-Path $locationRoot "BlackLake.gdb"
if (Test-Path $staleVenueGdb) {
    throw "Stale venue-level GDB found and should be removed: $staleVenueGdb"
}

if ($missing.Count -gt 0) {
    Write-Host "BlackLake ModDev install is incomplete:"
    foreach ($file in $missing) {
        Write-Host "  Missing: $file"
    }
    exit 1
}

$gdbText = Get-Content (Join-Path $layoutRoot "$layoutName.gdb") -Raw
if ($gdbText -notmatch "TrackName\s*=\s*BlackLake $Stage") {
    throw "Stage GDB does not contain the expected TrackName for $layoutName"
}

$aiwText = Get-Content (Join-Path $layoutRoot "$layoutName.AIW") -Raw
if ($aiwText -notmatch "\[GRID\]" -or $aiwText -notmatch "\[Waypoint\]") {
    throw "Stage AIW is missing GRID or Waypoint sections: $layoutName.AIW"
}

Write-Host "BlackLake ModDev install OK:"
Write-Host "  Stage:  $Stage"
Write-Host "  Layout: $layoutRoot"
Write-Host "  Track:  BlackLake $Stage"
