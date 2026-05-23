param(
    [string]$DestinationDirectory = ".\tyres\downloads\studio397",
    [switch]$Open
)

$ErrorActionPreference = "Stop"

$odsUrl = "https://docs.studio-397.com/download/attachments/7897103/Realtime%20tTool%20Batch%20Tester%20V0.20%20-%20Brabham%20BT44B%20Rears.ods?version=1&modificationDate=1525577514000&api=v2"
$fileName = "Realtime tTool Batch Tester V0.20 - Brabham BT44B Rears.ods"

$destination = $ExecutionContext.SessionState.Path.GetUnresolvedProviderPathFromPSPath($DestinationDirectory)
New-Item -ItemType Directory -Path $destination -Force | Out-Null

$odsPath = Join-Path $destination $fileName

if (-not (Test-Path -LiteralPath $odsPath)) {
    Write-Host "Downloading official Studio-397 realtime batch tester ODS..."
    Invoke-WebRequest -Uri $odsUrl -OutFile $odsPath
}
else {
    Write-Host "Using existing ODS: $odsPath"
}

if ($Open) {
    $officeCandidates = @(
        "soffice.exe",
        "libreoffice.exe",
        "C:\Program Files\LibreOffice\program\soffice.exe",
        "C:\Program Files (x86)\LibreOffice\program\soffice.exe"
    )

    $officeExe = $null
    foreach ($candidate in $officeCandidates) {
        $command = Get-Command $candidate -ErrorAction SilentlyContinue
        if ($command) {
            $officeExe = $command.Source
            break
        }
        if (Test-Path -LiteralPath $candidate) {
            $officeExe = $candidate
            break
        }
    }

    if ($officeExe) {
        Start-Process -FilePath $officeExe -ArgumentList @($odsPath)
    }
    else {
        Write-Warning "LibreOffice was not found in PATH or common install locations; opening with the default ODS handler."
        Invoke-Item -LiteralPath $odsPath
    }
}

[pscustomobject]@{
    OdsPath = $odsPath
    Source = "Studio-397 tTool Realtime Batch Tests documentation attachment"
    Url = $odsUrl
}

