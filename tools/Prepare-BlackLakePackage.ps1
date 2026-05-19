param(
    [ValidateSet("250m", "500m", "1000m", "2000m", "5000m", "12000m")]
    [string]$Stage = "250m",

    [string]$ProjectRoot = "C:\Users\Victor\Documents\PYTHON\RFactor2",

    [string]$Rf2Root = "C:\Program Files (x86)\Steam\steamapps\common\rFactor 2"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$layoutName = "BlackLake_$Stage"
$sourceRoot = Join-Path $ProjectRoot "tracks\blacklake\source\$Stage\moddev\BlackLake"
$layoutRoot = Join-Path $sourceRoot $layoutName
$gmtSourceRoot = Join-Path $ProjectRoot "tracks\blacklake\source\$Stage\gmt"
$modDevBlackLake = Join-Path $Rf2Root "ModDev\Locations\BlackLake"
$mapsRoot = Join-Path $modDevBlackLake "Assets\Maps"
$gmtRoot = $gmtSourceRoot
$packageRoot = Join-Path $ProjectRoot "build\blacklake_package\$Stage"
$componentName = "BlackLake_2026"
$componentVersion = "0.10"

if (-not (Test-Path $layoutRoot)) {
    throw "BlackLake layout source not found: $layoutRoot"
}

$required = @(
    (Join-Path $sourceRoot "BlackLake.tdf"),
    (Join-Path $layoutRoot "$layoutName.gdb"),
    (Join-Path $layoutRoot "$layoutName.scn"),
    (Join-Path $layoutRoot "$layoutName.AIW"),
    (Join-Path $layoutRoot "$layoutName.wet"),
    (Join-Path $gmtRoot "BlackLake_Surface.gmt"),
    (Join-Path $gmtRoot "BlackLake_Markings.gmt")
)

foreach ($path in $required) {
    if (-not (Test-Path $path)) {
        throw "Required BlackLake file missing: $path"
    }
}

if (-not (Test-Path $mapsRoot)) {
    throw "BlackLake maps not found in ModDev install: $mapsRoot"
}

if (Test-Path $packageRoot) {
    Remove-Item -LiteralPath $packageRoot -Recurse -Force
}

$sharedDir = Join-Path $packageRoot "01_shared"
$layoutDir = Join-Path $packageRoot "02_layout"
$gmtDir = Join-Path $packageRoot "03_gmt"
$mapsDir = Join-Path $packageRoot "04_maps"
$docsDir = Join-Path $packageRoot "docs"

foreach ($dir in @($sharedDir, $layoutDir, $gmtDir, $mapsDir, $docsDir)) {
    New-Item -ItemType Directory -Path $dir -Force | Out-Null
}

Copy-Item (Join-Path $sourceRoot "BlackLake.tdf") $sharedDir
Copy-Item (Join-Path $layoutRoot "$layoutName.gdb") $layoutDir
Copy-Item (Join-Path $layoutRoot "$layoutName.scn") $layoutDir
Copy-Item (Join-Path $layoutRoot "$layoutName.AIW") $layoutDir
Copy-Item (Join-Path $layoutRoot "$layoutName.wet") $layoutDir
Copy-Item (Join-Path $gmtRoot "BlackLake_Surface.gmt") $gmtDir
Copy-Item (Join-Path $gmtRoot "BlackLake_Markings.gmt") $gmtDir

$mapFiles = @(
    "DIFFUSE01.DDS",
    "STRIPES.DDS",
    "Asphalt_NORM.dds",
    "Asphalt_SPEC.dds"
)

foreach ($file in $mapFiles) {
    $source = Join-Path $mapsRoot $file
    if (Test-Path $source) {
        Copy-Item $source $mapsDir
    }
}

$instructions = @"
BlackLake packaging staging for stage $Stage

Component target:
  Name:    $componentName
  Version: $componentVersion
  Type:    Location

Prepared folders:
  01_shared  -> BlackLake_shared.mas
  02_layout  -> BlackLake_$Stage.mas
  03_gmt     -> BlackLake_GMT.mas
  04_maps    -> BlackLake_MAPS.mas

MAS2 workflow:
1. Open MAS2.exe from:
   $Rf2Root\Support\Tools\MAS2.exe
2. Create four MAS files from the four folders above with exactly these names:
   BlackLake_shared.mas
   BlackLake_$Stage.mas
   BlackLake_GMT.mas
   BlackLake_MAPS.mas
3. In MAS2 choose package creation and create a single component package:
   Component Name = $componentName
   Version        = $componentVersion
   Type           = Location
4. Add the four MAS files to the component.
5. Package to:
   $Rf2Root\Packages
6. Install the resulting .rfcmp with the rFactor 2 launcher or ModMgr.

Why this is needed:
The normal single-player track menu only lists installed components under
Installed\Locations. Loose ModDev content under ModDev\Locations does not show
up there.
"@

Set-Content -Path (Join-Path $docsDir "README.txt") -Value $instructions -Encoding ASCII

Write-Host "Prepared BlackLake package staging:"
Write-Host "  Stage:   $Stage"
Write-Host "  Root:    $packageRoot"
Write-Host "  Shared:  $sharedDir"
Write-Host "  Layout:  $layoutDir"
Write-Host "  GMT:     $gmtDir"
Write-Host "  Maps:    $mapsDir"
Write-Host "  Guide:   $(Join-Path $docsDir 'README.txt')"
