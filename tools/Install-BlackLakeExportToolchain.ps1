param(
    [string]$DownloadRoot = "C:\Users\Victor\Documents\PYTHON\RFactor2\tools\downloads\blacklake_export"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$blenderUrl = "https://download.blender.org/release/Blender2.83/blender-2.83.20-windows-x64.zip"
$exporterUrl = "https://drive.google.com/uc?export=download&id=1PGwEzs_Aun-h1xftriu0UWQNLKA32KrM"

$downloadRootPath = [System.IO.Path]::GetFullPath($DownloadRoot)
New-Item -ItemType Directory -Force -Path $downloadRootPath | Out-Null

$blenderZip = Join-Path $downloadRootPath "blender-2.83.20-windows-x64.zip"
$exporterZip = Join-Path $downloadRootPath "rf2_blender_exporter.zip"
$blenderDir = Join-Path $downloadRootPath "blender-2.83.20-windows-x64"
$exporterDir = Join-Path $downloadRootPath "rf2_blender_exporter"

if (-not (Test-Path $blenderZip)) {
    Write-Host "Downloading Blender 2.83.20..."
    Invoke-WebRequest -Uri $blenderUrl -OutFile $blenderZip
}

if (-not (Test-Path $exporterZip)) {
    Write-Host "Downloading rFactor 2 Blender exporter..."
    Invoke-WebRequest -Uri $exporterUrl -OutFile $exporterZip
}

if (-not (Test-Path $blenderDir)) {
    Write-Host "Extracting Blender..."
    Expand-Archive -Path $blenderZip -DestinationPath $downloadRootPath -Force
}

if (-not (Test-Path $exporterDir)) {
    Write-Host "Extracting rFactor 2 Blender exporter..."
    Expand-Archive -Path $exporterZip -DestinationPath $exporterDir -Force
}

$blenderExe = Join-Path $blenderDir "blender.exe"
$addonDir = Join-Path $exporterDir "io_rfactor2_gmt_WIP-64_bit"

if (-not (Test-Path $blenderExe)) {
    throw "Blender executable not found after extraction: $blenderExe"
}
if (-not (Test-Path $addonDir)) {
    throw "rFactor 2 Blender exporter not found after extraction: $addonDir"
}

Write-Host "BlackLake export toolchain is ready:"
Write-Host "  Blender:  $blenderExe"
Write-Host "  Exporter: $addonDir"
