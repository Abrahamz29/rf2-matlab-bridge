[CmdletBinding()]
param(
    [string]$GeneratedDir = "tmp/tgm_gen_acceptance_test",
    [string]$PToolDir = (Join-Path ${env:ProgramFiles(x86)} "Steam/steamapps/common/rFactor 2/pTool"),
    [string]$OutputBaseName = "generated_from_matlab"
)

$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
Push-Location $repoRoot
try {
    $sourceTgm = Join-Path $GeneratedDir "generated.tgm"
    $sourceTbc = Join-Path $GeneratedDir "generated.tbc"
    if (-not (Test-Path -LiteralPath $sourceTgm)) {
        throw "Generated TGM not found: $sourceTgm"
    }
    if (-not (Test-Path -LiteralPath $sourceTbc)) {
        throw "Generated TBC not found: $sourceTbc"
    }
    if (-not (Test-Path -LiteralPath $PToolDir)) {
        throw "pTool directory not found: $PToolDir"
    }

    $targetTgm = Join-Path $PToolDir ($OutputBaseName + ".tgm")
    $targetTbc = Join-Path $PToolDir ($OutputBaseName + ".tbc")
    Copy-Item -LiteralPath $sourceTgm -Destination $targetTgm -Force
    Copy-Item -LiteralPath $sourceTbc -Destination $targetTbc -Force

    $sourceTgmHash = (Get-FileHash -LiteralPath $sourceTgm -Algorithm SHA256).Hash
    $targetTgmHash = (Get-FileHash -LiteralPath $targetTgm -Algorithm SHA256).Hash
    $sourceTbcHash = (Get-FileHash -LiteralPath $sourceTbc -Algorithm SHA256).Hash
    $targetTbcHash = (Get-FileHash -LiteralPath $targetTbc -Algorithm SHA256).Hash

    if ($sourceTgmHash -ne $targetTgmHash) {
        throw "TGM copy hash mismatch."
    }
    if ($sourceTbcHash -ne $targetTbcHash) {
        throw "TBC copy hash mismatch."
    }

    $report = [ordered]@{
        generatedDir = (Resolve-Path $GeneratedDir).Path
        pToolDir = (Resolve-Path $PToolDir).Path
        sourceTgm = (Resolve-Path $sourceTgm).Path
        sourceTbc = (Resolve-Path $sourceTbc).Path
        targetTgm = (Resolve-Path $targetTgm).Path
        targetTbc = (Resolve-Path $targetTbc).Path
        tgmSha256 = $sourceTgmHash
        tbcSha256 = $sourceTbcHash
    }

    Write-Host ("TGM copied: {0}" -f $report.targetTgm)
    Write-Host ("TBC copied: {0}" -f $report.targetTbc)
    Write-Output ([pscustomobject]$report)
}
finally {
    Pop-Location
}
