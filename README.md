# rFactor 2 MATLAB Telemetry Bridge

Dieses Projekt verbindet MATLAB mit rFactor 2 ueber den offiziellen Community-Weg:
`rFactor2SharedMemoryMapPlugin64.dll` schreibt rFactor-2-Internals in Windows
Shared Memory, die Python-Bridge liest diese Buffer und MATLAB dekodiert sie als
Strukturen.

## Repository und Workflow

Das Projekt ist fuer Git/GitHub-Nutzung vorbereitet.

- Arbeitsregeln fuer Codex und Mitwirkende stehen in `AGENTS.md`.
- GitHub-Initialisierung und Remote-Setup stehen in `docs/github_bootstrap.md`.
- Vendor-Abhaengigkeiten sind als Git-Submodules eingebunden.
- Nach sinnvollen, verifizierten Aenderungen sollte ein lokaler Commit erzeugt
  werden.
- Nach stabilen Zwischenstaenden und vor groesseren Pausen sollte nach `origin`
  gepusht werden.

Frischer Clone mit Submodules:

```powershell
git clone --recurse-submodules <repo-url>
```

## Eingebundene Projekte

- `vendor/rF2SharedMemoryMapPlugin`:
  TheIronWolfModding/rF2SharedMemoryMapPlugin, Quelle der rFactor-2-Shared-Memory-Structs.
- `vendor/pyRfactor2SharedMemory`:
  TonyWhitley/pyRfactor2SharedMemory, Python-ctypes-Mapping der rF2-Structs.
- `vendor/rF2SharedMemoryNet`:
  Domaslau/rF2SharedMemoryNet, aktuelle .NET-Referenzimplementierung fuer alle Buffer.

Weitere nuetzliche Referenzen sind TinyPedal, CrewChief, SimHub und die Wine-Fork
des Shared-Memory-Plugins. Fuer MATLAB ist die direkte Python-Bridge in diesem
Repo der kuerzeste stabile Weg.

## rFactor 2 vorbereiten

Die DLL wurde in diesem Projekt bereits aus `rf2_sm_tools_3.7.15.1.zip`
geladen und nach rFactor 2 kopiert:

```text
C:\Program Files (x86)\Steam\steamapps\common\rFactor 2\Bin64\Plugins\rFactor2SharedMemoryMapPlugin64.dll
SHA256: 9D98D77B767812DCA5AFEB6663F486B3AD5BE090C3E10783F36BC73A470AB5E6
```

Die Plugin-Konfiguration wurde ebenfalls gesetzt:

```text
C:\Program Files (x86)\Steam\steamapps\common\rFactor 2\UserData\player\CustomPluginVariables.JSON
"rFactor2SharedMemoryMapPlugin64.dll" -> " Enabled": 1
"UnsubscribedBuffersMask": 0
```

Zum erneuten Installieren:

```powershell
.\tools\Install-RF2SharedMemoryPlugin.ps1 -Download
```

Manuelle Schritte:

1. Lade `rFactor2SharedMemoryMapPlugin64.dll` aus den rF2 Shared Memory Tools:
   https://github.com/TheIronWolfModding/rF2SharedMemoryMapPlugin#download
2. Kopiere die DLL nach:
   `C:\Program Files (x86)\Steam\steamapps\common\rFactor 2\Bin64\Plugins`
3. Starte rFactor 2, aktiviere in `Settings > Gameplay > Plugins`
   `rFactor2SharedMemoryMapPlugin64.dll`, danach rFactor 2 neu starten.
4. Fuer alle Output-Buffer sollte in
   `UserData\player\CustomPluginVariables.JSON` der Plugin-Wert
   `UnsubscribedBuffersMask` auf `0` stehen. Graphics und Weather sind im Plugin
   oft standardmaessig unsubscribed.

Hilfsscript, wenn die DLL bereits lokal vorhanden ist:

Falls rFactor 2 die Plugin-Konfiguration nicht erzeugt, installiere den VC12
Runtime aus `C:\Program Files (x86)\Steam\steamapps\common\rFactor 2\Support\Runtimes`
und starte rFactor 2 erneut.

## MATLAB benutzen

In MATLAB:

```matlab
cd("C:\Users\Victor\Documents\PYTHON\RFactor2")
status = setup_rf2_matlab()

client = RF2Client();
data = client.snapshot();
wheels = client.wheelTable(data)
dynamics = client.playerDynamics(data)
```

Vollstaendige Arrays inklusive aller 128 Fahrzeug-Slots:

```matlab
dataFull = client.snapshot("Full", true);
```

Live-Beispiel:

```matlab
rf2LivePlotExample(60, 20)
```

Setup-relevante Uebersichtsplots:

```matlab
run = rf2CollectTelemetry(120, 20);
rf2PlotTelemetry(run);
```

Kurzform:

```matlab
run = rf2PlotLatest(120, 20);
```

JSONL-Logging:

```matlab
client.logJsonl(120, 50)
```

CLI-Test ohne MATLAB, mit der Python-Umgebung, die MATLAB hier ebenfalls nutzt:

```powershell
& "C:\Users\Victor\.platformio\penv\Scripts\python.exe" .\python\rf2_matlab_bridge.py status --pretty
```

Erwarteter Status bei laufendem rFactor 2:

```text
connected: true
pluginVersion: 3.7.15.1
availableBuffers: telemetry, scoring, rules, forceFeedback, graphics, pitInfo, weather, extended
```

## Verfuegbare Shared-Memory-Buffer

- `telemetry` bei ca. 50 Hz: Fahrzeug-, Reifen-, Fahrdynamik- und Eingabedaten.
- `scoring` bei ca. 5 Hz: Session, Strecke, Position, Zeiten, Fahrer/Fahrzeuge.
- `rules` bei ca. 3 Hz: Full-course-yellow, Safety-Car, Regelstatus.
- `forceFeedback` bei ca. 400 Hz: aktueller FFB-Wert.
- `graphics` bei ca. 400 Hz: Kamera und Render-Umgebungsdaten.
- `pitInfo` bei ca. 100 Hz: aktuelles Pit-Menue.
- `weather` bei ca. 1 Hz: Regen, Wolken, Temperatur, Wind.
- `extended` bei ca. 5 Hz: Plugin-Version, Sessionstatus, Damage-Tracking,
  Direct-Memory-Reader-Status und Zusatzmeldungen.

Wichtige Reifenfelder liegen unter:

```matlab
data.convenience.playerTelemetry.mWheels
```

Die Reihenfolge ist:

```matlab
data.convenience.wheelOrder
```

Pro Rad werden unter anderem geliefert: Reifendruck, Temperaturen links/mitte/rechts,
Carcass- und Inner-Layer-Temperaturen, Verschleiss, Tire Load, Grip Fraction,
laterale/longitudinale Kraefte, Patch/Ground Velocities, Camber, Toe, Ride Height,
Suspension Deflection und Brake Temp/Pressure.

## Grenzen

Die Bridge liefert alle Daten, die der rFactor-2-Internals-API/Shared-Memory-Plugin
oeffentlich bereitstellt. Nicht enthalten sind proprietaere interne Solver-Zustaende
oder vollstaendige Reifenmodell-Parameter, die rF2 nicht in Shared Memory publiziert.
Solche statischen Mod-/TGM-Daten muessten separat aus installierten Fahrzeugdateien
extrahiert werden, soweit sie unverschluesselt vorliegen.

## MoTeC

MoTeC i2 Pro ist weiterhin sinnvoll fuer Offline-Lap-Analyse mit DAMPlugin-Logs.
Diese MATLAB-Bridge ist dagegen fuer Live-Daten, eigene Auswertungen und
automatisierte Versuche gedacht. Details stehen in `docs/plots_and_motec.md`.

## Headless und Autopilot

Fuer Plot-Entwicklung ohne laufende rF2-Session gibt es einen Mock-Modus:

```matlab
rf2RollingLivePlot(15, 20, "mock")
run = rf2PlotLatest(60, 20, "mock");
```

Fuer echte Daten muss rF2 als Client-Session laufen. Die Config ist vorbereitet:
AI-Control ist erlaubt, und rF2 pausiert nicht mehr bei Fokusverlust. In der
Session Taste `I` druecken, damit die AI das eigene Auto faehrt. Details:
`docs/headless_autopilot.md`.

## Automation

Es gibt jetzt einen Open-Loop-Manoever-Runner fuer rF2:

```powershell
& "C:\Users\Victor\.platformio\penv\Scripts\python.exe" .\python\rf2_automation.py .\scenarios\blacklake_step_steer_batch.json
```

Oder aus MATLAB:

```matlab
rf2RunAutomation("scenarios\blacklake_step_steer_batch.json")
```

Die erste Version nutzt Windows-Tastatur-Events als Aktuator und schreibt pro
Variante eine `telemetry.csv`. Details: `docs/automation.md`.

## Proving Ground Stufen

Fuer den ersten belastbaren Ausbau auf dem vorhandenen rF2-Testgelaende sind
jetzt TigerMoth-Szenarien hinterlegt:

```matlab
rf2RunAutomation("scenarios\tigermoth_250m_step_steer.json")
rf2RunAutomation("scenarios\tigermoth_scaleout_open_loop.json")
rf2RunAIDriverMonitor(60)
```

Die Skalierungslogik und der Weg zum spaeteren eigenen Flat-Proving-Ground
stehen in `docs/proving_ground_scale.md`.

## MATLAB-Regler

Fuer Strecken wie BlackLake kann rF2 auch direkt von MATLAB geregelt werden,
ohne AI-Fahrer:

```matlab
cd("C:\Users\Victor\Documents\PYTHON\RFactor2")
setup_rf2_matlab()
run = rf2RunBlackLakeController(30, 20);
```

Dabei liest MATLAB die Telemetrie ueber `RF2Client` und setzt Befehle ueber
`RF2Actuator`. `rf2RunBlackLakeController` prueft vor dem Start, ob wirklich
eine BlackLake-Session geladen ist.

## Custom BlackLake

Da auf diesem System kein installierter rF2-BlackLake-Content vorhanden ist,
liegt jetzt ein eigener BlackLake-Authoring-Workspace im Repo:

- `tracks/blacklake/`
- `python/blacklake_builder.py`
- `docs/blacklake_authoring.md`

Die Quelle fuer BlackLake wird damit selbst generiert: Flaechen-OBJ, Markings,
Layout-CSV und ModDev-Scaffolding fuer die Stufen `250m` bis `12000m`.
Das Scaffolding erzeugt inzwischen auch stage-lokale `.gdb`- und `.AIW`-Dateien,
damit rFactor 2 Startpositionen, Teleport, Pit- und Wegpunktdaten bekommt.

Der erste echte GMT-Exportpfad ist eingerichtet. Er nutzt eine lokale portable
Blender-2.83-Installation und Traveller's rFactor-2-Blender-Exporter aus
`tools/downloads/`:

```powershell
.\tools\Install-BlackLakeExportToolchain.ps1
.\tools\Export-BlackLakeGmt.ps1 -Stage 250m -InstallModDev
.\tools\Install-BlackLakeModDev.ps1 -Stage 250m -Mode Scaffold -RegisterSceneViewer
.\tools\Test-BlackLakeModDevInstall.ps1 -Stage 250m
```

Damit liegen fuer `250m` echte BlackLake-GMTs vor:

- `tracks/blacklake/source/250m/gmt/BlackLake_Surface.gmt`
- `tracks/blacklake/source/250m/gmt/BlackLake_Markings.gmt`

Der ModDev-Install fuer `250m` liegt danach unter:

```text
C:\Program Files (x86)\Steam\steamapps\common\rFactor 2\ModDev\Locations\BlackLake\BlackLake_250m
```

Wichtig fuer die Spiel-/ModDev-Auswahl sind dort:

- `BlackLake_250m.gdb`
- `BlackLake_250m.scn`
- `BlackLake_250m.AIW`

Wichtig: Diese lose `ModDev`-Strecke erscheint noch nicht im normalen
Singleplayer-Track-Menue des Hauptspiels. Fuer den direkten Fahrtest ist der
aktuelle Weg:

```powershell
.\tools\Start-BlackLakeModDev.ps1 -Mode Viewer -Stage 250m
```

Fuer das normale Track-Menue muss BlackLake als installierbare `Location`
paketiert werden. Die Staging-Struktur erzeugt:

```powershell
.\tools\Prepare-BlackLakePackage.ps1 -Stage 250m
```

Ein echtes `.rfcmp`-Paket inklusive MAS-Erzeugung und Installation in den
rFactor-2-Root wird automatisiert mit:

```powershell
.\tools\Build-BlackLakeRfcmp.ps1 -Stage 250m -Install
```

Fuer einen weitgehend automatischen Fahrtest-Vorbereitungslauf gibt es den
gebuendelten Befehl:

```powershell
.\tools\Prepare-BlackLakeDriveTest.ps1 -Stage 250m
```

Der Befehl baut die Quelle neu, exportiert die GMTs, installiert und prueft den
ModDev-Stand und erzeugt das MAS2-Staging. Fuer die Retail-Installation danach
`Build-BlackLakeRfcmp.ps1 -Install` ausfuehren und im normalen rFactor-2-Menue
nach `BlackLake` suchen.

Mit `-OpenGame` startet der Befehl nach der Vorbereitung direkt rFactor 2:

```powershell
.\tools\Prepare-BlackLakeDriveTest.ps1 -Stage 250m -OpenGame
```

Fuer den sofort nutzbaren Vergleichspfad gibt es weiterhin den
`JoesvilleBaseline`-Modus. Dieser nutzt vorhandene `Joesville`-Assets und ist
nur fuer Telemetrie, MATLAB-Regler und Session-Plumbing gedacht:

```powershell
.\tools\Install-BlackLakeModDev.ps1 -Stage 250m -Mode JoesvilleBaseline -RegisterSceneViewer
```
