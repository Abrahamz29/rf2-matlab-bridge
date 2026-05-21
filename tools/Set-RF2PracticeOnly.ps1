param(
    [string]$Rf2Root = "C:\Program Files (x86)\Steam\steamapps\common\rFactor 2",

    [int]$Opponents = 0
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$playerJson = Join-Path $Rf2Root "UserData\player\player.JSON"
if (-not (Test-Path $playerJson)) {
    throw "rFactor 2 player.JSON not found: $playerJson"
}

if ($Opponents -lt 0) {
    throw "Opponents must be zero or greater."
}

$backup = "$playerJson.blacklake_practice_$(Get-Date -Format yyyyMMdd_HHmmss)"
Copy-Item -LiteralPath $playerJson -Destination $backup -Force

$text = Get-Content -LiteralPath $playerJson -Raw

foreach ($prefix in @("CURNT", "GPRIX", "CHAMP", "MULTI", "RPLAY")) {
    $pattern = '("' + [regex]::Escape($prefix) + ' Opponents"\s*:\s*)\d+'
    $text = [regex]::Replace($text, $pattern, "`${1}$Opponents")
}

$text = [regex]::Replace($text, '("Run Practice1"\s*:\s*)false', '${1}true')
$text = [regex]::Replace($text, '("Run Practice2"\s*:\s*)true', '${1}false')
$text = [regex]::Replace($text, '("Run Practice3"\s*:\s*)true', '${1}false')
$text = [regex]::Replace($text, '("Run Practice4"\s*:\s*)true', '${1}false')
$text = [regex]::Replace($text, '("Run Warmup"\s*:\s*)true', '${1}false')

Set-Content -LiteralPath $playerJson -Value $text -Encoding ASCII

Write-Host "rFactor 2 practice-only config prepared:"
Write-Host "  File:      $playerJson"
Write-Host "  Backup:    $backup"
Write-Host "  Opponents: $Opponents"
