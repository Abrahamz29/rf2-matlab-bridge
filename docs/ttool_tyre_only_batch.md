# TTool Reifen-Einzeltest

Dieser Workflow ist fuer reine Reifenpruefstand-Tests mit dem rFactor-2-TTool.
Er ist kein Fahrzeug- oder Streckensimulationslauf. Die Testkonfiguration kommt
aus dem offiziellen Studio-397-Realtime-Batch-Tester-ODS; wir erfinden keine
eigenen TTool-Parameter.

## Offizielles Werkzeug

Studio-397 stellt fuer Realtime-Batch-Tests eine ODS-Arbeitsmappe bereit:
`Realtime tTool Batch Tester V0.20 - Brabham BT44B Rears.ods`.

Lokal herunterladen:

```powershell
.\tools\Get-TToolRealtimeBatchTester.ps1
```

Herunterladen und direkt oeffnen:

```powershell
.\tools\Get-TToolRealtimeBatchTester.ps1 -Open
```

Die ODS wird unter `tools\downloads\studio397\` abgelegt. Dieser Ordner ist
absichtlich nicht versioniert.

Einen kompletten INI-Block aus der ODS extrahieren:

```powershell
& "C:\Users\Victor\.platformio\penv\Scripts\python.exe" .\tools\extract_ttool_realtime_ini_from_ods.py `
  --suite 0_Initial-Tests `
  --output .\scenarios\tyre\ttool\custom_realtime_0_initial_tests.ini
```

Verfuegbare ODS-Testgruppen anzeigen:

```powershell
& "C:\Users\Victor\.platformio\penv\Scripts\python.exe" .\tools\extract_ttool_realtime_ini_from_ods.py `
  --output .\tmp\unused.ini `
  --list
```

## TTool starten

```powershell
& "C:\Program Files (x86)\Steam\steamapps\common\rFactor 2\Bin64\rFactor2 Mod Mode.exe" +tTool +multiple +trace=2
```

Alternativ den Desktop-Shortcut `rFactor 2 TGM Tyre Tool` verwenden.

## Batch-Test ausfuehren

TTool erwartet die Batch-Datei im rFactor-2-Ordner:

```text
C:\Program Files (x86)\Steam\steamapps\common\rFactor 2\pTool\custom_realtime.ini
```

Offizieller Ablauf:

1. ODS in LibreOffice oeffnen.
2. Im Sheet `General` die Basisdaten fuer den Reifen/Test eintragen.
3. Zuerst `0 InitialTests` exportieren oder den Copy-Block manuell in
   `custom_realtime.ini` einfuegen.
4. TTool starten, `.TGM` laden, bei `Custom Test File (Realtime)` den Namen
   `custom_realtime.ini` setzen.
5. `Run Custom Tests (Realtime)` ausfuehren.
6. Die erzeugte `CustomRealtimeTable.csv` aus dem TTool-Ausgabeordner in das
   passende `Res`-Sheet der ODS kopieren.
7. Danach die weiteren ODS-Sheets in der vorgesehenen Reihenfolge nutzen:
   `1 Deflection`, `2 RollingResistance`, `3 Sweep`, `4 LateralPeaks`,
   `5 Longitudinal`, `7 CombinedCurves`.

## Schraeglaufwinkel-Sweep

Fuer unseren geplanten Sweep bei 5000 N wird nicht direkt ein frei erfundener
Kraftbefehl in TTool geschrieben. Der offizielle Weg ist:

1. Mit `1 Deflection` die vertikale Reifencharakteristik bestimmen.
2. Aus dem ODS-Ergebnis die passende Bedingung fuer die Ziel-Last ableiten.
3. Den Sweep ueber `3 Sweep` konfigurieren, weil dieses Sheet laut Studio-397
   fuer inkrementelle Slip-Angle-Tests gedacht ist.
4. Erst die von der ODS exportierte `custom_realtime.ini` in TTool ausfuehren.
5. Ergebnis-CSV danach in der ODS analysieren und optional in MATLAB plotten.

Unser CSV-Testplan unter `scenarios\tyre\` bleibt eine dokumentierte
Versuchsabsicht. Der TTool-Lauf selbst wird aus der offiziellen ODS exportiert.

## Quellen

- https://docs.studio-397.com/display/DG/tTool%2BRealtime%2BBatch%2BTests
- https://www.studio-397.com/2018/05/realtime-tyre-analysis-improvements-build-1110/
