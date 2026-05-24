[CmdletBinding()]
param(
    [string]$TgmRoot = "tyres/cache/tgm",
    [string]$ReportPath = "tmp/tgm_all_known_tyres_smoke_report.json",
    [string]$RoundtripDir = "tmp/tgm_all_known_tyres_roundtrip",
    [string]$MatlabExe = ""
)

$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..\..")
Push-Location $repoRoot
try {
    if ($MatlabExe -eq "") {
        $matlabCommand = Get-Command matlab -ErrorAction SilentlyContinue
        if ($matlabCommand) {
            $MatlabExe = $matlabCommand.Source
        } else {
            $MatlabExe = Join-Path $env:ProgramFiles "MATLAB/R2025b/bin/matlab.exe"
        }
    }
    if (-not (Test-Path -LiteralPath $MatlabExe)) {
        throw "MATLAB executable not found: $MatlabExe"
    }

    $tgmRootEscaped = $TgmRoot.Replace("'", "''")
    $reportPathEscaped = $ReportPath.Replace("'", "''")
    $roundtripDirEscaped = $RoundtripDir.Replace("'", "''")
    $batch = "addpath('bridge/matlab'); addpath('tyres/matlab/functions'); addpath('tracks/blacklake/matlab'); report = rf2TgmAllKnownTyresSmoke('TgmRoot','$tgmRootEscaped','ReportPath','$reportPathEscaped','RoundtripDir','$roundtripDirEscaped'); assert(report.passed);"
    & $MatlabExe -batch $batch

    $report = Get-Content -LiteralPath $ReportPath -Raw | ConvertFrom-Json
    Write-Host ("Known tyres: {0}, passed: {1}" -f $report.count, $report.passed)
    foreach ($result in $report.results) {
        Write-Host ("  {0}: nodes={1}, plyRows={2}, layers={3}, roundtrip={4}" -f `
            $result.file, $result.nodeCount, $result.plyRows, $result.maxPlyLayers, $result.roundtripEqual)
    }
    Write-Host ("Report: {0}" -f (Resolve-Path $ReportPath))
}
finally {
    Pop-Location
}

