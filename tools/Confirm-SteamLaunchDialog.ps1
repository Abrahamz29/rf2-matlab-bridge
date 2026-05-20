param(
    [int]$TimeoutSeconds = 20,

    [int]$PollIntervalMilliseconds = 500
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing

if (-not ("MouseNative" -as [type])) {
    Add-Type @"
using System;
using System.Runtime.InteropServices;

public static class MouseNative
{
    [DllImport("user32.dll")]
    public static extern bool SetCursorPos(int X, int Y);

    [DllImport("user32.dll")]
    public static extern void mouse_event(uint dwFlags, uint dx, uint dy, uint dwData, UIntPtr dwExtraInfo);

    public const uint LeftDown = 0x0002;
    public const uint LeftUp = 0x0004;
}
"@
}

function Get-SteamContinueButtonCenter {
    $bounds = [System.Windows.Forms.Screen]::PrimaryScreen.Bounds
    $bitmap = New-Object System.Drawing.Bitmap $bounds.Width, $bounds.Height
    $graphics = [System.Drawing.Graphics]::FromImage($bitmap)

    try {
        $graphics.CopyFromScreen($bounds.Location, [System.Drawing.Point]::Empty, $bounds.Size)

        $points = New-Object 'System.Collections.Generic.HashSet[string]'
        # Restrict to the lower part of the screen. The Steam dialog has a
        # thin blue border near its top; including it skews the computed
        # bounding box above the actual "Fortfahren" button.
        $startY = [Math]::Floor($bounds.Height * 0.60)

        for ($y = $startY; $y -lt $bounds.Height; $y += 2) {
            for ($x = 0; $x -lt $bounds.Width; $x += 2) {
                $pixel = $bitmap.GetPixel($x, $y)

                # Steam's "Fortfahren" button is the only large saturated blue
                # region in the lower half of the custom launch-arguments dialog.
                if ($pixel.R -ge 35 -and $pixel.R -le 95 -and
                    $pixel.G -ge 85 -and $pixel.G -le 150 -and
                    $pixel.B -ge 170 -and $pixel.B -le 245) {
                    [void]$points.Add("$x,$y")
                }
            }
        }

        if ($points.Count -lt 250) {
            return $null
        }

        $best = $null
        $visited = New-Object 'System.Collections.Generic.HashSet[string]'
        foreach ($point in $points) {
            if ($visited.Contains($point)) {
                continue
            }

            $queue = New-Object 'System.Collections.Generic.Queue[string]'
            $queue.Enqueue($point)
            [void]$visited.Add($point)
            $minX = $bounds.Width
            $minY = $bounds.Height
            $maxX = -1
            $maxY = -1
            $count = 0

            while ($queue.Count -gt 0) {
                $current = $queue.Dequeue()
                $parts = $current.Split(',')
                $x = [int]$parts[0]
                $y = [int]$parts[1]
                $count++
                if ($x -lt $minX) { $minX = $x }
                if ($x -gt $maxX) { $maxX = $x }
                if ($y -lt $minY) { $minY = $y }
                if ($y -gt $maxY) { $maxY = $y }

                foreach ($neighbor in @(
                    "$($x - 2),$y",
                    "$($x + 2),$y",
                    "$x,$($y - 2)",
                    "$x,$($y + 2)"
                )) {
                    if ($points.Contains($neighbor) -and -not $visited.Contains($neighbor)) {
                        [void]$visited.Add($neighbor)
                        $queue.Enqueue($neighbor)
                    }
                }
            }

            $width = $maxX - $minX
            $height = $maxY - $minY
            if ($count -ge 250 -and
                $width -ge 90 -and $width -le 260 -and
                $height -ge 25 -and $height -le 90) {
                if ($null -eq $best -or $count -gt $best.PixelCount) {
                    $best = [PSCustomObject]@{
                        X = $bounds.Left + [Math]::Floor(($minX + $maxX) / 2)
                        Y = $bounds.Top + [Math]::Floor(($minY + $maxY) / 2)
                        PixelCount = $count
                        Width = $width
                        Height = $height
                    }
                }
            }
        }

        return $best
    }
    finally {
        $graphics.Dispose()
        $bitmap.Dispose()
    }
}

$deadline = (Get-Date).AddSeconds($TimeoutSeconds)
do {
    $center = Get-SteamContinueButtonCenter
    if ($null -ne $center) {
        [MouseNative]::SetCursorPos($center.X, $center.Y) | Out-Null
        Start-Sleep -Milliseconds 100
        [MouseNative]::mouse_event([MouseNative]::LeftDown, 0, 0, 0, [UIntPtr]::Zero)
        Start-Sleep -Milliseconds 80
        [MouseNative]::mouse_event([MouseNative]::LeftUp, 0, 0, 0, [UIntPtr]::Zero)
        Write-Host "Confirmed Steam launch dialog at ($($center.X), $($center.Y))."
        exit 0
    }

    Start-Sleep -Milliseconds $PollIntervalMilliseconds
} while ((Get-Date) -lt $deadline)

throw "Steam launch confirmation dialog was not found within $TimeoutSeconds seconds."
