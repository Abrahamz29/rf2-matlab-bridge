[CmdletBinding()]
param(
    [string]$ExtensionsRoot = (Join-Path $env:USERPROFILE ".vscode\extensions")
)

$ErrorActionPreference = "Stop"

$source = $PSScriptRoot
$manifest = Get-Content -Raw -LiteralPath (Join-Path $source "package.json") | ConvertFrom-Json
$targetName = "$($manifest.publisher).$($manifest.name)-$($manifest.version)"
$target = Join-Path $ExtensionsRoot $targetName

if (-not (Test-Path -LiteralPath $ExtensionsRoot)) {
    New-Item -ItemType Directory -Force -Path $ExtensionsRoot | Out-Null
}

if (Test-Path -LiteralPath $target) {
    Remove-Item -LiteralPath $target -Recurse -Force
}

New-Item -ItemType Directory -Force -Path $target | Out-Null
Copy-Item -LiteralPath (Join-Path $source "package.json") -Destination $target
Copy-Item -LiteralPath (Join-Path $source "extension.js") -Destination $target
Copy-Item -LiteralPath (Join-Path $source "README.md") -Destination $target

Write-Host "Installed VS Code extension to: $target"
Write-Host "Reload VS Code to activate: Developer: Reload Window"
