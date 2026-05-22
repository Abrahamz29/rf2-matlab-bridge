[CmdletBinding()]
param(
    [string]$OdsPath = "tools/downloads/studio397/TGM Gen V0.33 - GY F1 1975 Front.ods",
    [string]$OutDir = "tmp/tgm_gen_acceptance_test",
    [ValidateSet("recursive", "cached")]
    [string]$Mode = "recursive",
    [string]$ReportPath = "tmp/tgm_gen_acceptance_test_report.json",
    [string]$PythonExe = "",
    [switch]$PrepareTTool,
    [string]$PToolDir = (Join-Path ${env:ProgramFiles(x86)} "Steam/steamapps/common/rFactor 2/pTool"),
    [string]$OutputBaseName = "generated_from_matlab"
)

$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
Push-Location $repoRoot
try {
    if ($PythonExe -eq "") {
        $platformIoPython = Join-Path $env:USERPROFILE ".platformio/penv/Scripts/python.exe"
        if (Test-Path -LiteralPath $platformIoPython) {
            $PythonExe = $platformIoPython
        } else {
            $PythonExe = "python"
        }
    }

    $reportParent = Split-Path -Parent $ReportPath
    if ($reportParent -and -not (Test-Path -LiteralPath $reportParent)) {
        New-Item -ItemType Directory -Force -Path $reportParent | Out-Null
    }

    $output = & $PythonExe "tools/test_tgm_gen_ods_acceptance.py" `
        --ods $OdsPath `
        --out-dir $OutDir `
        --mode $Mode `
        --json

    $output | Set-Content -LiteralPath $ReportPath -Encoding UTF8
    $report = $output | ConvertFrom-Json

    Write-Host ("TGM equal without Lookup/Patch: {0}" -f $report.tgm.equal)
    Write-Host ("TBC equal: {0}" -f $report.tbc.equal)
    Write-Host ("Formulas: {0}/{1}, errors={2}, fallback={3}" -f $report.evaluated_count, $report.formula_count, $report.error_count, $report.fallback_count)
    Write-Host ("Project roundtrip: {0}" -f $report.project_roundtrip.passed)
    Write-Host ("Charts: {0}/{1}, numeric points={2}" -f $report.charts.evaluated_series_count, $report.charts.series_count, $report.charts.numeric_point_count)
    Write-Host ("Materials: {0}, points={1}" -f $report.material_library.material_count, $report.material_library.point_count)
    Write-Host ("Report: {0}" -f (Resolve-Path $ReportPath))

    if (-not $report.passed) {
        throw "TGM Generator acceptance failed."
    }

    if ($PrepareTTool) {
        $copyScript = Join-Path $PSScriptRoot "Copy-TgmGenToPTool.ps1"
        & $copyScript `
            -GeneratedDir $OutDir `
            -PToolDir $PToolDir `
            -OutputBaseName $OutputBaseName
    }
}
finally {
    Pop-Location
}
