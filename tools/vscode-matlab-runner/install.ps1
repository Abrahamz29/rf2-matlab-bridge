[CmdletBinding()]
param(
    [string]$VsixPath,
    [string]$ExtensionsRoot = (Join-Path $env:USERPROFILE ".vscode\extensions")
)

$ErrorActionPreference = "Stop"

$source = $PSScriptRoot
$manifest = Get-Content -Raw -LiteralPath (Join-Path $source "package.json") | ConvertFrom-Json
$packageName = "$($manifest.name)-$($manifest.version).vsix"
$extensionId = "$($manifest.publisher).$($manifest.name)"
$extensionFolderName = "$extensionId-$($manifest.version)"

if (-not $VsixPath) {
    $VsixPath = Join-Path $source $packageName
}

if (-not (Test-Path -LiteralPath $VsixPath)) {
    Push-Location $source
    try {
        npm install
        npm run package
    }
    finally {
        Pop-Location
    }
}

if (-not (Test-Path -LiteralPath $VsixPath)) {
    throw "Extension package not found: $VsixPath"
}

$codeCommand = Get-Command code -ErrorAction SilentlyContinue
if (-not $codeCommand) {
    throw "VS Code command line tool was not found on PATH: code"
}

$legacyPublisher = -join ([char[]](114, 102, 50))
$legacyExtensionId = "$legacyPublisher.matlab-run-selected"

try {
    & $codeCommand.Source --uninstall-extension $legacyExtensionId *> $null
}
catch {
    Write-Verbose "Legacy extension uninstall command did not complete: $($_.Exception.Message)"
}

if (Test-Path -LiteralPath $ExtensionsRoot) {
    Get-ChildItem -LiteralPath $ExtensionsRoot -Directory -Filter "$legacyExtensionId-*" |
        Remove-Item -Recurse -Force
    Get-ChildItem -LiteralPath $ExtensionsRoot -Directory -Filter "$extensionId-*" |
        Where-Object { $_.Name -ne $extensionFolderName } |
        Remove-Item -Recurse -Force
}

& $codeCommand.Source --install-extension $VsixPath --force | Out-Host

Write-Host "Installed VS Code extension package: $VsixPath"
Write-Host "Reload VS Code to activate: Developer: Reload Window"
