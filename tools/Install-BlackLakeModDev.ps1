param(
    [ValidateSet("250m", "500m", "1000m", "2000m", "5000m", "12000m")]
    [string]$Stage = "250m",

    [ValidateSet("Scaffold", "JoesvilleBaseline")]
    [string]$Mode = "Scaffold",

    [string]$ProjectRoot = "C:\Users\Victor\Documents\PYTHON\RFactor2",

    [string]$ModDevRoot = "C:\Program Files (x86)\Steam\steamapps\common\rFactor 2\ModDev",

    [switch]$RegisterSceneViewer
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Write-InstallSummary {
    param(
        [string]$TargetRoot,
        [string]$LayoutFolder,
        [string]$ModeName
    )

    Write-Host "Installed BlackLake ModDev content:"
    Write-Host "  Mode:   $ModeName"
    Write-Host "  Stage:  $Stage"
    Write-Host "  Target: $TargetRoot"
    Write-Host "  Layout: $LayoutFolder"
}

function Register-SceneViewer {
    param(
        [string]$ModDevRoot,
        [string]$Stage
    )

    $setupPath = Join-Path $ModDevRoot "setup2_DX11.ini"
    if (-not (Test-Path $setupPath)) {
        Write-Warning "Scene Viewer config not found: $setupPath"
        return
    }

    $sceneDir = "SceneDir=Locations\BlackLake\BlackLake_$Stage"
    $sceneFile = "SceneFile=BlackLake_$Stage.scn"
    $content = Get-Content $setupPath
    $updated = @()
    $sceneDirFound = $false

    foreach ($line in $content) {
        if ($line -like "SceneDir=*") {
            if (-not $sceneDirFound) {
                $updated += $sceneDir
                $sceneDirFound = $true
            }
            continue
        }
        if ($line -like "SceneFile=*") {
            $updated += $sceneFile
            continue
        }
        $updated += $line
    }

    if (-not $sceneDirFound) {
        $updated += $sceneDir
    }

    Set-Content -Path $setupPath -Value $updated -Encoding ASCII
    Write-Host "Scene Viewer configured for BlackLake_$Stage"
}

function Install-Scaffold {
    param(
        [string]$ProjectRoot,
        [string]$ModDevRoot,
        [string]$Stage
    )

    $sourceRoot = Join-Path $ProjectRoot "tracks\blacklake\source\$Stage\moddev\BlackLake"
    if (-not (Test-Path $sourceRoot)) {
        throw "Source scaffold not found: $sourceRoot"
    }

    $targetRoot = Join-Path $ModDevRoot "Locations\BlackLake"
    if (-not (Test-Path $targetRoot)) {
        New-Item -ItemType Directory -Path $targetRoot | Out-Null
    }

    Copy-Item -Path (Join-Path $sourceRoot "*") -Destination $targetRoot -Recurse -Force
    Install-BlackLakeDefaultMaps -ModDevRoot $ModDevRoot -TargetRoot $targetRoot

    $staleVenueGdb = Join-Path $targetRoot "BlackLake.gdb"
    if (Test-Path $staleVenueGdb) {
        Remove-Item -LiteralPath $staleVenueGdb -Force
    }

    $layoutFolder = Join-Path $targetRoot ("BlackLake_" + $Stage)
    $gmtFiles = @(
        "BlackLake_Surface.gmt",
        "BlackLake_Markings.gmt",
        "BlackLake_Reference.gmt",
        "xfinish.gmt",
        "xsector1.gmt",
        "xsector2.gmt",
        "xpitin.gmt",
        "xpitout.gmt"
    )
    $missingGmts = @()
    foreach ($file in $gmtFiles) {
        $path = Join-Path $layoutFolder $file
        if (-not (Test-Path $path)) {
            $missingGmts += $path
        }
    }

    Write-InstallSummary -TargetRoot $targetRoot -LayoutFolder $layoutFolder -ModeName "Scaffold"

    if ($missingGmts.Count -gt 0) {
        Write-Host ""
        Write-Host "Next required step:"
        Write-Host "  Export the generated source geometry to GMT and place it in:"
        Write-Host "  $layoutFolder"
        Write-Host ""
        Write-Host "Expected GMT files:"
        foreach ($path in $missingGmts) {
            Write-Host "  $path"
        }
        Write-Warning "The scaffold is installed, but the GMT meshes are still missing. rFactor 2 cannot load this track yet."
    } else {
        Write-Host ""
        Write-Host "GMT meshes found:"
        foreach ($file in $gmtFiles) {
            Write-Host "  $(Join-Path $layoutFolder $file)"
        }
    }
}

function Install-BlackLakeDefaultMaps {
    param(
        [string]$ModDevRoot,
        [string]$TargetRoot
    )

    $sourceMaps = Join-Path $ModDevRoot "Locations\Joesville\Assets\Maps"
    $targetMaps = Join-Path $TargetRoot "Assets\Maps"
    if (-not (Test-Path $targetMaps)) {
        New-Item -ItemType Directory -Path $targetMaps | Out-Null
    }

    $textureMap = @(
        @{ Source = "Track_Main.dds"; Target = "DIFFUSE01.DDS" },
        @{ Source = "Track_Main.dds"; Target = "DIFFUSE01.dds" },
        @{ Source = "Stripes.dds"; Target = "STRIPES.DDS" },
        @{ Source = "Asphalt_NORM.dds"; Target = "Asphalt_NORM.dds" },
        @{ Source = "Asphalt_SPEC.dds"; Target = "Asphalt_SPEC.dds" }
    )

    foreach ($entry in $textureMap) {
        $source = Join-Path $sourceMaps $entry.Source
        if (Test-Path $source) {
            Copy-Item -Path $source -Destination (Join-Path $targetMaps $entry.Target) -Force
        }
    }
}

function Install-JoesvilleBaseline {
    param(
        [string]$ProjectRoot,
        [string]$ModDevRoot,
        [string]$Stage
    )

    $sourceRoot = Join-Path $ProjectRoot "tracks\blacklake\source\$Stage\moddev\BlackLake"
    if (-not (Test-Path $sourceRoot)) {
        throw "Source scaffold not found: $sourceRoot"
    }

    $modDevLocations = Join-Path $ModDevRoot "Locations"
    $targetRoot = Join-Path $modDevLocations "BlackLake"
    $layoutName = "BlackLake_$Stage"
    $layoutFolder = Join-Path $targetRoot $layoutName
    $joesvilleRoot = Join-Path $modDevLocations "Joesville"
    $joesvilleLayout = Join-Path $joesvilleRoot "JoesVille_Speedway"
    $joesvilleTdf = Join-Path $joesvilleRoot "Joesville_Speedway.tdf"

    if (-not (Test-Path $joesvilleLayout)) {
        throw "Joesville ModDev layout not found: $joesvilleLayout"
    }
    if (-not (Test-Path $joesvilleTdf)) {
        throw "Joesville TDF not found: $joesvilleTdf"
    }

    if (-not (Test-Path $targetRoot)) {
        New-Item -ItemType Directory -Path $targetRoot | Out-Null
    }

    Copy-Item -Path (Join-Path $sourceRoot "*") -Destination $targetRoot -Recurse -Force
    Copy-Item -Path $joesvilleTdf -Destination (Join-Path $targetRoot "BlackLake.tdf") -Force

    $copiedFiles = @{
        "Joesville_Speedway.AIW"         = "$layoutName.AIW"
        "Joesville_Speedway.cam"         = "$layoutName.cam"
        "Joesville_Speedway.wet"         = "$layoutName.wet"
        "Joesville_Speedwayicon.tga"     = "$layoutName" + "icon.tga"
        "Joesville_SpeedwaySMicon.dds"   = "$layoutName" + "SMicon.dds"
        "Joesville_SpeedwayThmb.tga"     = "$layoutName" + "Thmb.tga"
        "Joesville_Speedway_loading.jpg" = "$layoutName" + "_loading.jpg"
        "swheel_trackmap.dds"            = "swheel_trackmap.dds"
        "TestTeam_Heavy.rrbin"           = "TestTeam_Heavy.rrbin"
        "TestTeam_Light.rrbin"           = "TestTeam_Light.rrbin"
        "TestTeam_Medium.rrbin"          = "TestTeam_Medium.rrbin"
        "TestTeam_Saturated.rrbin"       = "TestTeam_Saturated.rrbin"
    }

    foreach ($entry in $copiedFiles.GetEnumerator()) {
        $source = Join-Path $joesvilleLayout $entry.Key
        if (Test-Path $source) {
            Copy-Item -Path $source -Destination (Join-Path $layoutFolder $entry.Value) -Force
        }
    }

    $gdbPath = Join-Path $targetRoot "BlackLake.gdb"
    $gdb = @"
$layoutName
{
  Filter Properties = rFRS TMOD NSCRS
  Attrition = 0
  TrackName = BlackLake $Stage Baseline
  EventName = BlackLake Baseline
  VenueName = BlackLake
  VenueIcon = BlackLake\$layoutName\$layoutName`SMicon.dds
  Location = Synthetic Test Facility
  Length = 0.656 KM / 0.41 Miles
  TrackType = Test Track
  FormationAndStart=0
  TerrainDataFile=..\BlackLake.tdf
  HeadlightsRequired = false
  Max Vehicles = 20
  PitlaneBoundary = 1
  RacePitKPH = 48.2802
  NormalPitKPH = 48.2802
  FormationSpeedKPH = 56.3269
  TestDayStart = 12:00
  RaceLaps = 10
  RaceTime = 30
  NumStartingLights = 2
  Latitude = 0.0
  Longitude = 0.0
  Altitude = 0.0
  RaceDate = June 1, 2026
  TimezoneRelativeGMT = 0.0
  SettingsFolder = BlackLake
  SettingsCopy = BlackLake.svm
  SettingsAI = BlackLake.svm
}
"@
    Set-Content -Path $gdbPath -Value $gdb -Encoding ASCII

    $scnPath = Join-Path $layoutFolder "$layoutName.scn"
    $scn = @"
CUBEASF

SearchPath=.
SearchPath=BLACKLAKE
SearchPath=BLACKLAKE\$($layoutName.ToUpper())
SearchPath=JOESVILLE\ASSETS\ANIMS
SearchPath=JOESVILLE\ASSETS\GMT
SearchPath=JOESVILLE\ASSETS\MAPS
SearchPath=JOESVILLE\ASSETS\SPONSORMAPS

MASFile=COMMONMAPS.MAS

View=mainview
{
  Clear=False
  Color=(0, 0, 0)
  Size=(1.00, 1.00) Center=(0.5, 0.5)
  FOV=(77.75, 31.25)
  ClipPlanes=(0.50, 1000.00)
  View=rearview
  {
    Clear=False
    Color=(0, 0, 0)
    Size=(0.200, 0.100) Center=(0.50, 0.01)
    FOV=(62.5, 62.5)
    ClipPlanes=(0.50, 150.00)
  }
}

GroupMethod=Dynamic
MaxShadowRange=(450.00)
AmbientColor=(126, 126, 126)
ReflectPlane=(0.000, 1.000, 0.000, 0.550)
FogMode=LINEAR FogIn=(50.00) FogOut=(5000.00) FogDensity=(0.00015) FogColor=(205, 215, 235)

Light=Direct00
{
 Type=Directional Color=(220, 220, 220) Dir=(0.5, -0.9, 0.5)
}
Light=NightLight01
{
 Type=Omni Pos=(0.455906, 8.781423, -12.216267) Range=(0.000000, 36.000000) Active=True Intensity=(1.500000) Color=(255, 255, 224)
}

Instance=NightLight01Glow
{
  VisGroups=(32) ReflectPlane=(0.000, 1.000, 0.000, 0.550)
  MeshFile=NightLight01Glow.gmt CollTarget=False HATTarget=False
}

Instance=RaceSurface_01
{
  MeshFile=RaceSurface_01.gmt Deformable=True CollTarget=True HATTarget=True
}
Instance=Infield
{
  MeshFile=Infield.gmt CollTarget=True HATTarget=True
}
Instance=Outfield
{
  MeshFile=Outfield.gmt CollTarget=False HATTarget=False
}
Instance=RoadLines
{
  VisGroups=(32)
  MeshFile=RoadLines.gmt CollTarget=True HATTarget=True
}
Instance=Grassverges
{
  VisGroups=(32)
  MeshFile=Grassverges.gmt CollTarget=False HATTarget=False
}
Instance=Walls_Inside
{
  ReflectPlane=(0.000, 1.000, 0.000, 0.550)
  MeshFile=Walls_Inside.gmt CollTarget=True HATTarget=False ShadowCaster=(Static, Solid) Reflect=True ShadowGroups=(15)
}
Instance=Walls_Outside
{
  ReflectPlane=(0.000, 1.000, 0.000, -1.685)
  MeshFile=Walls_Outside.gmt CollTarget=True HATTarget=False ShadowCaster=(Static, Solid) Reflect=True ShadowGroups=(15)
}
Instance=Armcos
{
  ReflectPlane=(0.000, 1.000, 0.000, -1.685)
  MeshFile=Armcos.gmt CollTarget=False HATTarget=False ShadowCaster=(Static, Solid) Reflect=True ShadowGroups=(15)
}
Instance=BarrierA_01
{
  VisGroups=(32)
  MeshFile=BarrierA_01.gmt CollTarget=True HATTarget=False ShadowCaster=(Static, Solid) ShadowGroups=(12)
}
Instance=SafetyFences
{
  ReflectPlane=(0.000, 1.000, 0.000, -1.685)
  MeshFile=SafetyFences.gmt CollTarget=True HATTarget=False ShadowCaster=(Static, Texture) Reflect=True ShadowGroups=(14)
}
Instance=SFencePosts
{
  ReflectPlane=(0.000, 1.000, 0.000, -1.685)
  MeshFile=SFencePosts.gmt CollTarget=False HATTarget=False ShadowCaster=(Static, Solid) Reflect=True ShadowGroups=(12)
}
Instance=Fence_ChainLink
{
  MeshFile=Fence_ChainLink.gmt CollTarget=True HATTarget=False ShadowCaster=(Static, Texture) ShadowGroups=(12)
}
Instance=Structures
{
  VisGroups=(38)
  MeshFile=Structures.gmt CollTarget=False HATTarget=False ShadowCaster=(Static, Solid) ShadowGroups=(12)
}
Instance=Track_Outer
{
  VisGroups=(38)
  MeshFile=Track_Outer.gmt CollTarget=False HATTarget=False ShadowCaster=(Static, Solid) ShadowGroups=(12)
}
Instance=SkyBoxi
{
  Planes=(4) ReflectPlane=(0.000, 1.000, 0.000, 0.550)
  MeshFile=SkyBoxi.gmt CollTarget=False HATTarget=False Reflect=True
}
Instance=ShadowBox
{
  MeshFile=ShadowBox.gmt CollTarget=False HATTarget=False ShadowObject=(Static, Solid) ShadowGroups=(15) LODOut=(1000)
}
Instance=XFinish
{
  MeshFile=xfinish.gmt CollTarget=False HATTarget=False
}
Instance=XPitIn
{
  MeshFile=xpitin.gmt CollTarget=False HATTarget=False
}
Instance=XPitOut
{
  MeshFile=xpitout.gmt CollTarget=False HATTarget=False
}
Instance=XSector1
{
  MeshFile=xsector1.gmt CollTarget=False HATTarget=False
}
Instance=XSector2
{
  MeshFile=xsector2.gmt CollTarget=False HATTarget=False
}

ReflectionMapper=REFLECTEDENV
{
  Type=Planar
  TextureSize=(1024)
  UpdateRate=(100.000)
  StaticSwitch=(150.000)
  TrackingIns=NULL
  IncludeIns=Walls_Inside
  IncludeIns=Walls_Outside
  IncludeIns=Armcos
  IncludeIns=SafetyFences
  IncludeIns=SFencePosts
  IncludeIns=NightLight01Glow
}

ReflectionMapper=STATIC01
{
  Type=Cubic
  TextureSize=(512)
  UpdateRate=(0.100)
  StaticSwitch=(100.000)
  Pos=(-40.777466,0.000000,-46.012000)
  IncludeIns=RaceSurface_01
  IncludeIns=Infield
  IncludeIns=Outfield
  IncludeIns=Walls_Inside
  IncludeIns=Walls_Outside
}

ReflectionMapper=REFMAP0
{
  Type=Cubic
  TextureSize=(1024)
  UpdateRate=(100.000)
  StaticSwitch=(100.000)
  TrackingIns=True
  IncludeIns=NightLight01Glow
  IncludeIns=RaceSurface_01
  IncludeIns=Infield
  IncludeIns=Outfield
  IncludeIns=RoadLines
  IncludeIns=Walls_Inside
  IncludeIns=Walls_Outside
  IncludeIns=Armcos
  IncludeIns=BarrierA_01
  IncludeIns=SafetyFences
  IncludeIns=SFencePosts
  IncludeIns=Fence_ChainLink
  IncludeIns=Structures
  IncludeIns=Track_Outer
  IncludeIns=SkyBoxi
}
"@
    Set-Content -Path $scnPath -Value $scn -Encoding ASCII

    Write-InstallSummary -TargetRoot $targetRoot -LayoutFolder $layoutFolder -ModeName "JoesvilleBaseline"
    Write-Host ""
    Write-Host "This baseline reuses Joesville ModDev assets so that BlackLake can load now."
    Write-Host "It is intended for controller, telemetry, and session plumbing before the custom GMT meshes exist."
}

$targetRoot = Join-Path $ModDevRoot "Locations\BlackLake"
switch ($Mode) {
    "Scaffold" {
        Install-Scaffold -ProjectRoot $ProjectRoot -ModDevRoot $ModDevRoot -Stage $Stage
    }
    "JoesvilleBaseline" {
        Install-JoesvilleBaseline -ProjectRoot $ProjectRoot -ModDevRoot $ModDevRoot -Stage $Stage
    }
}

if ($RegisterSceneViewer) {
    Register-SceneViewer -ModDevRoot $ModDevRoot -Stage $Stage
}
