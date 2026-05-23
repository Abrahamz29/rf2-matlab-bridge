param(
    [string]$WindowTitlePattern = "*TTool*"
)

$ErrorActionPreference = "Stop"

Add-Type @"
using System;
using System.Runtime.InteropServices;

public static class User32ClickProbe {
    [StructLayout(LayoutKind.Sequential)]
    public struct POINT {
        public int X;
        public int Y;
    }

    [StructLayout(LayoutKind.Sequential)]
    public struct RECT {
        public int Left;
        public int Top;
        public int Right;
        public int Bottom;
    }

    [DllImport("user32.dll")]
    public static extern short GetAsyncKeyState(int vKey);

    [DllImport("user32.dll")]
    public static extern bool GetCursorPos(out POINT point);

    [DllImport("user32.dll")]
    public static extern bool GetWindowRect(IntPtr hWnd, out RECT rect);
}
"@

$process = Get-Process |
    Where-Object { $_.MainWindowHandle -ne 0 -and $_.MainWindowTitle -like $WindowTitlePattern } |
    Sort-Object StartTime -Descending |
    Select-Object -First 1

if (-not $process) {
    throw "No window found matching title pattern '$WindowTitlePattern'. Start TTool first."
}

$rect = New-Object User32ClickProbe+RECT
[User32ClickProbe]::GetWindowRect($process.MainWindowHandle, [ref]$rect) | Out-Null

Write-Host "TTool window: $($process.MainWindowTitle)"
Write-Host "Window rect: left=$($rect.Left), top=$($rect.Top), right=$($rect.Right), bottom=$($rect.Bottom)"
Write-Host "Click the target in TTool now. Press Ctrl+C to cancel."

$wasDown = $false
while ($true) {
    $isDown = ([User32ClickProbe]::GetAsyncKeyState(0x01) -band 0x8000) -ne 0
    if ($isDown -and -not $wasDown) {
        $point = New-Object User32ClickProbe+POINT
        [User32ClickProbe]::GetCursorPos([ref]$point) | Out-Null

        [pscustomobject]@{
            ScreenX = $point.X
            ScreenY = $point.Y
            RelativeX = $point.X - $rect.Left
            RelativeY = $point.Y - $rect.Top
            WindowLeft = $rect.Left
            WindowTop = $rect.Top
            WindowWidth = $rect.Right - $rect.Left
            WindowHeight = $rect.Bottom - $rect.Top
            WindowTitle = $process.MainWindowTitle
        }
        break
    }

    $wasDown = $isDown
    Start-Sleep -Milliseconds 20
}
