param(
  [string]$PluginDll = "",
  [string]$RFactor2Root = "C:\Program Files (x86)\Steam\steamapps\common\rFactor 2",
  [switch]$Download
)

$ErrorActionPreference = "Stop"

$downloadPageUrl = "https://www.mediafire.com/file/s6ojcr9zrs6q9ls/rf2_sm_tools_3.7.15.1.zip/file"
$downloadRoot = Join-Path (Split-Path -Parent $PSScriptRoot) "downloads"
$zipPath = Join-Path $downloadRoot "rf2_sm_tools_3.7.15.1.zip"
$extractRoot = Join-Path $downloadRoot "rf2_sm_tools_3.7.15.1"

function Get-RF2SharedMemoryPluginFromDownload {
  New-Item -ItemType Directory -Force -Path $downloadRoot | Out-Null

  if (-not (Test-Path -LiteralPath $zipPath)) {
    Write-Host "Downloading rF2 Shared Memory Tools..."
    $page = Invoke-WebRequest -Uri $downloadPageUrl -UseBasicParsing
    $downloadUrl = ($page.Links |
      Where-Object { $_.href -match "/s6ojcr9zrs6q9ls/rf2_sm_tools_3\.7\.15\.1\.zip$" } |
      Select-Object -First 1).href

    if (-not $downloadUrl) {
      throw "Could not find the MediaFire direct download URL."
    }

    Invoke-WebRequest -Uri $downloadUrl -OutFile $zipPath
  }

  if (Test-Path -LiteralPath $extractRoot) {
    Remove-Item -LiteralPath $extractRoot -Recurse -Force
  }
  Expand-Archive -LiteralPath $zipPath -DestinationPath $extractRoot

  $downloadedDll = Get-ChildItem -LiteralPath $extractRoot -Recurse -Filter "rFactor2SharedMemoryMapPlugin64.dll" |
    Select-Object -First 1

  if (-not $downloadedDll) {
    throw "Downloaded archive did not contain rFactor2SharedMemoryMapPlugin64.dll."
  }

  return $downloadedDll.FullName
}

if (-not $PluginDll) {
  $searchRoots = @(
    "$PSScriptRoot\..\..",
    "$env:USERPROFILE\Downloads",
    "$env:ProgramFiles",
    "${env:ProgramFiles(x86)}",
    "$env:LOCALAPPDATA"
  ) | Where-Object { $_ -and (Test-Path $_) }

  $candidate = $null
  foreach ($root in $searchRoots) {
    $candidate = Get-ChildItem -LiteralPath $root -Recurse -Filter "rFactor2SharedMemoryMapPlugin64.dll" -ErrorAction SilentlyContinue |
      Select-Object -First 1
    if ($candidate) {
      $PluginDll = $candidate.FullName
      break
    }
  }
}

if (($Download -or -not $PluginDll) -and -not (Test-Path -LiteralPath $PluginDll -ErrorAction SilentlyContinue)) {
  $PluginDll = Get-RF2SharedMemoryPluginFromDownload
}

if (-not $PluginDll -or -not (Test-Path -LiteralPath $PluginDll)) {
  throw @"
rFactor2SharedMemoryMapPlugin64.dll was not found.
Download the rF2 Shared Memory Tools from:
  https://github.com/TheIronWolfModding/rF2SharedMemoryMapPlugin#download
Then rerun this script with:
  .\bridge\tools\Install-RF2SharedMemoryPlugin.ps1 -PluginDll C:\path\to\rFactor2SharedMemoryMapPlugin64.dll
"@
}

if (-not (Test-Path -LiteralPath $RFactor2Root)) {
  throw "rFactor 2 root not found: $RFactor2Root"
}

$pluginDir = Join-Path $RFactor2Root "Bin64\Plugins"
New-Item -ItemType Directory -Force -Path $pluginDir | Out-Null

$destination = Join-Path $pluginDir "rFactor2SharedMemoryMapPlugin64.dll"
Copy-Item -LiteralPath $PluginDll -Destination $destination -Force
Unblock-File -LiteralPath $destination -ErrorAction SilentlyContinue

Write-Host "Installed $destination"
Get-FileHash -Algorithm SHA256 -LiteralPath $destination | Format-List
Write-Host "Start rFactor 2, enable rFactor2SharedMemoryMapPlugin64.dll in Settings > Gameplay > Plugins, then restart rFactor 2."
