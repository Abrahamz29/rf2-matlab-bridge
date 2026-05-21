param(
    [ValidateSet("250m", "500m", "1000m", "2000m", "5000m", "12000m")]
    [string]$Stage = "250m",

    [string]$ProjectRoot = "C:\Users\Victor\Documents\PYTHON\RFactor2",

    [string]$Rf2Root = "C:\Program Files (x86)\Steam\steamapps\common\rFactor 2",

    [string]$PythonExe = "C:\Users\Victor\.platformio\penv\Scripts\python.exe",

    [string]$ComponentName = "BlackLake_2026",

    [string]$ComponentVersion = "0.10",

    [switch]$SkipSourceBuild,

    [switch]$SkipGmtExport,

    [switch]$SkipPracticeConfig,

    [switch]$NoLooseRetailInstall,

    [switch]$UseJoesvilleAiwFallback,

    [switch]$OpenViewer,

    [switch]$OpenGame
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$BlackLakeGmtFiles = @(
    "BlackLake_Surface.gmt",
    "BlackLake_Markings.gmt",
    "BlackLake_Reference.gmt",
    "xfinish.gmt",
    "xsector1.gmt",
    "xsector2.gmt",
    "xpitin.gmt",
    "xpitout.gmt"
)

function Assert-PathInside {
    param(
        [string]$Candidate,
        [string]$Root
    )

    $resolvedCandidate = [System.IO.Path]::GetFullPath($Candidate)
    $resolvedRoot = [System.IO.Path]::GetFullPath($Root).TrimEnd('\') + '\'
    if (-not $resolvedCandidate.StartsWith($resolvedRoot, [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "Refusing to modify path outside expected root. Path: $resolvedCandidate Root: $resolvedRoot"
    }
}

function Copy-DirectoryContents {
    param(
        [string]$Source,
        [string]$Destination
    )

    if (-not (Test-Path $Source)) {
        throw "Source directory not found: $Source"
    }
    New-Item -ItemType Directory -Path $Destination -Force | Out-Null
    Copy-Item -Path (Join-Path $Source "*") -Destination $Destination -Recurse -Force
}

function Convert-ToLooseRetailScene {
    param(
        [string]$Path
    )

    $lines = Get-Content $Path
    $converted = @("SearchPath=.")
    foreach ($line in $lines) {
        if ($line -like "SearchPath=*") {
            continue
        }
        $converted += $line
    }
    Set-Content -Path $Path -Value $converted -Encoding ASCII
}

function Convert-ToLooseRetailGdb {
    param(
        [string]$Path
    )

    $text = Get-Content $Path -Raw
    $text = $text -replace "TerrainDataFile=\.\.\\BlackLake\.tdf", "TerrainDataFile=BlackLake.tdf"
    Set-Content -Path $Path -Value $text -Encoding ASCII
}

function Write-LooseRetailManifest {
    param(
        [string]$Path,
        [string]$Name,
        [string]$Version
    )

    $date = [DateTimeOffset]::UtcNow.ToUnixTimeSeconds()
    $manifest = @"
[Component]
Name=$Name
Version=$Version
Type=1
Author=Victor
Origin=0
Category=0
ID=BLACKLAKE2026
URL=
Desc=Loose BlackLake drive-test install generated from ModDev sources.
Date=$date
Flags=270536704
RefCount=1
Signature=loose-dev-install
"@
    Set-Content -Path $Path -Value $manifest -Encoding ASCII
}

function Clear-BlackLakeRuntimeCache {
    param(
        [string]$Stage,
        [string]$Rf2Root
    )

    $cacheRoot = Join-Path $Rf2Root "UserData\Log\CBash"
    if (-not (Test-Path $cacheRoot)) {
        return
    }

    $pattern = "BLACKLAKE_$($Stage.ToUpperInvariant()).*"
    Get-ChildItem -Path $cacheRoot -Filter $pattern -ErrorAction SilentlyContinue |
        Remove-Item -Force
}

function Get-JoesvilleAiwPath {
    param(
        [string]$Rf2Root
    )

    $joesvilleRoot = Join-Path $Rf2Root "ModDev\Locations\Joesville"
    if (-not (Test-Path $joesvilleRoot)) {
        throw "Joesville ModDev location not found: $joesvilleRoot"
    }

    $aiw = Get-ChildItem -Path $joesvilleRoot -Recurse -Filter "Joesville_Speedway.AIW" -ErrorAction Stop |
        Select-Object -First 1
    if ($null -eq $aiw) {
        throw "Joesville AIW fallback not found under: $joesvilleRoot"
    }

    return $aiw.FullName
}

function Get-JoesvilleTdfPath {
    param(
        [string]$Rf2Root
    )

    $candidate = Join-Path $Rf2Root "ModDev\Locations\Joesville\Joesville_Speedway.tdf"
    if (Test-Path $candidate) {
        return $candidate
    }

    throw "Joesville TDF fallback not found: $candidate"
}

function Install-JoesvilleAiwFallback {
    param(
        [string]$Stage,
        [string]$Rf2Root,
        [string]$ProjectRoot,
        [string]$PythonExe,
        [string[]]$Destinations,
        [int]$MaxStartingGrid = 20
    )

    $sourceAiw = Get-JoesvilleAiwPath -Rf2Root $Rf2Root
    $aiwPatcher = Join-Path $ProjectRoot "tools\patch_blacklake_drive_aiw.py"
    if (-not (Test-Path $aiwPatcher)) {
        throw "BlackLake AIW patcher not found: $aiwPatcher"
    }

    foreach ($destination in $Destinations) {
        $parent = Split-Path -Parent $destination
        if (-not (Test-Path $parent)) {
            throw "AIW fallback destination folder not found: $parent"
        }

        Copy-Item -Path $sourceAiw -Destination $destination -Force
        Limit-AiwStartingGrid -Path $destination -MaxStartingGrid $MaxStartingGrid
        & $PythonExe $aiwPatcher $destination --max-entries $MaxStartingGrid
        if ($LASTEXITCODE -ne 0) {
            throw "BlackLake AIW drive-test patch failed with exit code $LASTEXITCODE"
        }
        Write-Host "Installed Joesville AIW fallback:"
        Write-Host "  Stage:  $Stage"
        Write-Host "  Source: $sourceAiw"
        Write-Host "  Target: $destination"
        Write-Host "  Starting grid and teleports patched to BlackLake center"
        Write-Host "  Pit boxes kept on donor AIW coordinates to preserve accepted pitlane waypoints"
    }
}

function Install-JoesvilleTdfFallback {
    param(
        [string]$Stage,
        [string]$Rf2Root,
        [string[]]$Destinations
    )

    $sourceTdf = Get-JoesvilleTdfPath -Rf2Root $Rf2Root
    foreach ($destination in $Destinations) {
        $parent = Split-Path -Parent $destination
        if (-not (Test-Path $parent)) {
            throw "TDF fallback destination folder not found: $parent"
        }

        Copy-Item -Path $sourceTdf -Destination $destination -Force
        Write-Host "Installed Joesville TDF fallback:"
        Write-Host "  Stage:  $Stage"
        Write-Host "  Source: $sourceTdf"
        Write-Host "  Target: $destination"
    }
}

function Limit-AiwStartingGrid {
    param(
        [string]$Path,
        [int]$MaxStartingGrid
    )

    if ($MaxStartingGrid -lt 1) {
        throw "MaxStartingGrid must be at least 1."
    }

    $lines = Get-Content -LiteralPath $Path
    $limited = New-Object System.Collections.Generic.List[string]
    $inGridLikeSection = $false
    $keepGridEntry = $true

    foreach ($line in $lines) {
        if ($line -match "^startinggrid=") {
            $limited.Add("startinggrid=$MaxStartingGrid")
            continue
        }

        if ($line -match "^\[(ALT)?GRID\]") {
            $inGridLikeSection = $true
            $keepGridEntry = $true
            $limited.Add($line)
            continue
        }

        if ($inGridLikeSection -and $line -match "^\[" -and $line -notmatch "^\[(ALT)?GRID\]") {
            $inGridLikeSection = $false
            $keepGridEntry = $true
        }

        if ($inGridLikeSection -and $line -match "^GridIndex=(\d+)") {
            $keepGridEntry = ([int]$matches[1] -lt $MaxStartingGrid)
        }

        if ($inGridLikeSection -and -not $keepGridEntry) {
            continue
        }

        $limited.Add($line)
    }

    Set-Content -LiteralPath $Path -Value $limited -Encoding ASCII
}

function Set-JoesvilleAiwFallbackGdbLimits {
    param(
        [string[]]$GdbPaths
    )

    foreach ($path in $GdbPaths) {
        if (-not (Test-Path $path)) {
            throw "GDB fallback patch target not found: $path"
        }

        $text = Get-Content -LiteralPath $path -Raw
        $text = [regex]::Replace($text, "Max Vehicles\s*=\s*\d+", "Max Vehicles = 20")
        $text = [regex]::Replace($text, "PitlaneBoundary\s*=\s*\d+", "PitlaneBoundary = 1")
        Set-Content -LiteralPath $path -Value $text -Encoding ASCII
        Write-Host "Patched GDB for Joesville AIW fallback:"
        Write-Host "  Target: $path"
        Write-Host "  Max Vehicles = 20"
    }
}

function Install-LooseRetailLocation {
    param(
        [string]$Stage,
        [string]$ProjectRoot,
        [string]$Rf2Root,
        [string]$ComponentName,
        [string]$ComponentVersion
    )

    $layoutName = "BlackLake_$Stage"
    $packageRoot = Join-Path $ProjectRoot "build\blacklake_package\$Stage"
    $installedLocations = Join-Path $Rf2Root "Installed\Locations"
    $targetRoot = Join-Path $installedLocations $ComponentName
    $targetVersion = Join-Path $targetRoot $ComponentVersion

    Assert-PathInside -Candidate $targetVersion -Root $installedLocations

    if (-not (Test-Path $packageRoot)) {
        throw "Package staging is missing: $packageRoot"
    }

    if (Test-Path $targetVersion) {
        Remove-Item -LiteralPath $targetVersion -Recurse -Force
    }
    New-Item -ItemType Directory -Path $targetVersion -Force | Out-Null

    Copy-DirectoryContents -Source (Join-Path $packageRoot "01_shared") -Destination $targetVersion
    Copy-DirectoryContents -Source (Join-Path $packageRoot "02_layout") -Destination $targetVersion
    Copy-DirectoryContents -Source (Join-Path $packageRoot "03_gmt") -Destination $targetVersion
    Copy-DirectoryContents -Source (Join-Path $packageRoot "04_maps") -Destination $targetVersion

    Convert-ToLooseRetailScene -Path (Join-Path $targetVersion "$layoutName.scn")
    Convert-ToLooseRetailGdb -Path (Join-Path $targetVersion "$layoutName.gdb")
    Write-LooseRetailManifest -Path (Join-Path $targetVersion "$ComponentName.mft") -Name $ComponentName -Version $ComponentVersion

    $requiredFiles = @(
        (Join-Path $targetVersion "BlackLake.tdf"),
        (Join-Path $targetVersion "$layoutName.gdb"),
        (Join-Path $targetVersion "$layoutName.scn"),
        (Join-Path $targetVersion "$layoutName.AIW"),
        (Join-Path $targetVersion "$layoutName.wet"),
        (Join-Path $targetVersion "DIFFUSE01.DDS"),
        (Join-Path $targetVersion "$ComponentName.mft")
    )
    $requiredFiles += $BlackLakeGmtFiles | ForEach-Object { Join-Path $targetVersion $_ }

    foreach ($file in $requiredFiles) {
        if (-not (Test-Path $file)) {
            throw "Loose retail install verification failed. Missing: $file"
        }
    }

    $readme = @"
BlackLake loose retail drive-test install

This folder was generated by tools\Prepare-BlackLakeDriveTest.ps1.
It is intended only as a fast local test install before proper MAS2/rfcmp packaging.

Track search term:
  BlackLake

Generated from:
  Stage: $Stage
  Component: $ComponentName
  Version: $ComponentVersion
"@
    Set-Content -Path (Join-Path $targetVersion "README_BlackLake_LooseInstall.txt") -Value $readme -Encoding ASCII

    Write-Host "Loose retail drive-test install prepared:"
    Write-Host "  Target: $targetVersion"
    Write-Host "  Track:  BlackLake $Stage"
}

$builder = Join-Path $ProjectRoot "python\blacklake_builder.py"
$exportScript = Join-Path $ProjectRoot "tools\Export-BlackLakeGmt.ps1"
$installModDevScript = Join-Path $ProjectRoot "tools\Install-BlackLakeModDev.ps1"
$testModDevScript = Join-Path $ProjectRoot "tools\Test-BlackLakeModDevInstall.ps1"
$packageScript = Join-Path $ProjectRoot "tools\Prepare-BlackLakePackage.ps1"
$rfcmpScript = Join-Path $ProjectRoot "tools\Build-BlackLakeRfcmp.ps1"
$practiceConfigScript = Join-Path $ProjectRoot "tools\Set-RF2PracticeOnly.ps1"
$viewerScript = Join-Path $ProjectRoot "tools\Start-BlackLakeModDev.ps1"

if (-not (Test-Path $ProjectRoot)) {
    throw "Project root not found: $ProjectRoot"
}
if (-not (Test-Path $Rf2Root)) {
    throw "rFactor 2 root not found: $Rf2Root"
}

if (-not $SkipSourceBuild) {
    if (-not (Test-Path $PythonExe)) {
        throw "Python executable not found: $PythonExe"
    }
    & $PythonExe $builder --stage $Stage
    if ($LASTEXITCODE -ne 0) {
        throw "BlackLake source build failed with exit code $LASTEXITCODE"
    }
}

if (-not $SkipGmtExport) {
    & powershell -ExecutionPolicy Bypass -File $exportScript -Stage $Stage -InstallModDev
    if ($LASTEXITCODE -ne 0) {
        throw "BlackLake GMT export failed with exit code $LASTEXITCODE"
    }
}

& powershell -ExecutionPolicy Bypass -File $installModDevScript -Stage $Stage -Mode Scaffold -RegisterSceneViewer
if ($LASTEXITCODE -ne 0) {
    throw "BlackLake ModDev install failed with exit code $LASTEXITCODE"
}

if ($UseJoesvilleAiwFallback) {
    Install-JoesvilleTdfFallback -Stage $Stage -Rf2Root $Rf2Root -Destinations @(
        (Join-Path $Rf2Root "ModDev\Locations\BlackLake\BlackLake.tdf")
    )
    Install-JoesvilleAiwFallback -Stage $Stage -Rf2Root $Rf2Root -Destinations @(
        (Join-Path $Rf2Root "ModDev\Locations\BlackLake\BlackLake_$Stage\BlackLake_$Stage.AIW")
    ) -ProjectRoot $ProjectRoot -PythonExe $PythonExe
    Set-JoesvilleAiwFallbackGdbLimits -GdbPaths @(
        (Join-Path $Rf2Root "ModDev\Locations\BlackLake\BlackLake_$Stage\BlackLake_$Stage.gdb")
    )
}

& powershell -ExecutionPolicy Bypass -File $testModDevScript -Stage $Stage
if ($LASTEXITCODE -ne 0) {
    throw "BlackLake ModDev verification failed with exit code $LASTEXITCODE"
}

& powershell -ExecutionPolicy Bypass -File $packageScript -Stage $Stage -ProjectRoot $ProjectRoot -Rf2Root $Rf2Root
if ($LASTEXITCODE -ne 0) {
    throw "BlackLake package staging failed with exit code $LASTEXITCODE"
}

if ($UseJoesvilleAiwFallback) {
    Install-JoesvilleTdfFallback -Stage $Stage -Rf2Root $Rf2Root -Destinations @(
        (Join-Path $ProjectRoot "build\blacklake_package\$Stage\01_shared\BlackLake.tdf")
    )
    Install-JoesvilleAiwFallback -Stage $Stage -Rf2Root $Rf2Root -Destinations @(
        (Join-Path $ProjectRoot "build\blacklake_package\$Stage\02_layout\BlackLake_$Stage.AIW")
    ) -ProjectRoot $ProjectRoot -PythonExe $PythonExe
    Set-JoesvilleAiwFallbackGdbLimits -GdbPaths @(
        (Join-Path $ProjectRoot "build\blacklake_package\$Stage\02_layout\BlackLake_$Stage.gdb")
    )
}

if (-not $NoLooseRetailInstall) {
    if (Test-Path $rfcmpScript) {
        & powershell -ExecutionPolicy Bypass -File $rfcmpScript -Stage $Stage -ProjectRoot $ProjectRoot -Rf2Root $Rf2Root -PythonExe $PythonExe -ComponentName $ComponentName -ComponentVersion $ComponentVersion -Install
        if ($LASTEXITCODE -ne 0) {
            throw "BlackLake rfcmp install failed with exit code $LASTEXITCODE"
        }
    }
    else {
        Install-LooseRetailLocation -Stage $Stage -ProjectRoot $ProjectRoot -Rf2Root $Rf2Root -ComponentName $ComponentName -ComponentVersion $ComponentVersion
    }
}

if (-not $SkipPracticeConfig) {
    if (-not (Test-Path $practiceConfigScript)) {
        throw "Practice-only configuration script not found: $practiceConfigScript"
    }

    & powershell -ExecutionPolicy Bypass -File $practiceConfigScript -Rf2Root $Rf2Root -Opponents 0
    if ($LASTEXITCODE -ne 0) {
        throw "Practice-only configuration failed with exit code $LASTEXITCODE"
    }
}

Clear-BlackLakeRuntimeCache -Stage $Stage -Rf2Root $Rf2Root

if ($OpenViewer) {
    & powershell -ExecutionPolicy Bypass -File $viewerScript -Mode Viewer -Stage $Stage -Rf2Root $Rf2Root
}

if ($OpenGame) {
    $gameExe = Join-Path $Rf2Root "Bin64\rFactor2.exe"
    if (-not (Test-Path $gameExe)) {
        throw "rFactor 2 executable not found: $gameExe"
    }
    Start-Process -FilePath $gameExe -WorkingDirectory $Rf2Root -ArgumentList @("+trace=2")

    $steamConfirmScript = Join-Path $ProjectRoot "tools\Confirm-SteamLaunchDialog.ps1"
    if (Test-Path $steamConfirmScript) {
        try {
            & powershell -ExecutionPolicy Bypass -File $steamConfirmScript -TimeoutSeconds 20
        }
        catch {
            Write-Warning "Steam launch dialog auto-confirm did not complete: $($_.Exception.Message)"
        }
    }
}

Write-Host ""
Write-Host "BlackLake drive-test preparation complete."
Write-Host "Next checks:"
Write-Host "  1. In normal rFactor 2 track search, look for: BlackLake"
Write-Host "  2. If the normal menu does not list it, use the ModDev viewer for geometry validation and inspect the installed rfcmp package."
