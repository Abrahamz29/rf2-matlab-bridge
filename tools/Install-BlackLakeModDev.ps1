param(
    [ValidateSet("250m", "500m", "1000m", "2000m", "5000m", "12000m")]
    [string]$Stage = "250m",

    [string]$ProjectRoot = "C:\Users\Victor\Documents\PYTHON\RFactor2",

    [string]$ModDevLocations = "C:\Program Files (x86)\Steam\steamapps\common\rFactor 2\ModDev\Locations"
)

$sourceRoot = Join-Path $ProjectRoot "tracks\blacklake\source\$Stage\moddev\BlackLake"
if (-not (Test-Path $sourceRoot)) {
    throw "Source scaffold not found: $sourceRoot"
}

$targetRoot = Join-Path $ModDevLocations "BlackLake"
if (-not (Test-Path $targetRoot)) {
    New-Item -ItemType Directory -Path $targetRoot | Out-Null
}

Copy-Item -Path (Join-Path $sourceRoot "*") -Destination $targetRoot -Recurse -Force

$layoutFolder = Join-Path $targetRoot ("BlackLake_" + $Stage)
$surfaceGmt = Join-Path $layoutFolder "BlackLake_Surface.gmt"
$markingsGmt = Join-Path $layoutFolder "BlackLake_Markings.gmt"

Write-Host "Installed BlackLake ModDev scaffold for stage $Stage to:"
Write-Host "  $targetRoot"
Write-Host ""
Write-Host "Next required step:"
Write-Host "  Export the generated OBJ files to GMT and place them in:"
Write-Host "  $layoutFolder"
Write-Host ""
Write-Host "Expected GMT files:"
Write-Host "  $surfaceGmt"
Write-Host "  $markingsGmt"

if (-not (Test-Path $surfaceGmt) -or -not (Test-Path $markingsGmt)) {
    Write-Warning "The scaffold is installed, but the GMT meshes are still missing. rFactor 2 cannot load this track yet."
}
