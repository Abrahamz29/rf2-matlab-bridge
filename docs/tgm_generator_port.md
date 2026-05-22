# TGM Generator Port

Ziel ist ein MATLAB-basierter Nachbau des offiziellen Studio-397
`TGM Gen V0.33` mit moderner `uihtml`-Oberflaeche. `LookupV2` und `PatchV1`
werden bewusst nicht berechnet; diese Abschnitte bleiben Aufgabe von tTool.

## Referenz erzeugen

Die ODS liegt lokal unter:

```text
tools\downloads\studio397\TGM Gen V0.33 - GY F1 1975 Front.ods
```

Referenzdateien aus den gespeicherten ODS-Exportzellen rekonstruieren:

```powershell
& "C:\Users\Victor\.platformio\penv\Scripts\python.exe" .\tools\tgm_gen_ods.py `
  --ods ".\tools\downloads\studio397\TGM Gen V0.33 - GY F1 1975 Front.ods" `
  export-reference --out-dir .\tmp\tgm_gen_port --json
```

Erzeugt:

- `tmp\tgm_gen_port\reference_from_ods.tgm`
- `tmp\tgm_gen_port\reference_from_ods.tbc`
- `tmp\tgm_gen_port\tgm_gen_ods_report.json`

Generierte Dateien aus dem aktuellen Formel-Harness schreiben:

```powershell
& "C:\Users\Victor\.platformio\penv\Scripts\python.exe" .\tools\tgm_gen_ods.py `
  --ods ".\tools\downloads\studio397\TGM Gen V0.33 - GY F1 1975 Front.ods" `
  generate --out-dir .\tmp\tgm_gen_port --mode recursive --json
```

Erzeugt:

- `tmp\tgm_gen_port\generated.tgm`
- `tmp\tgm_gen_port\generated.tbc`

## MATLAB UI starten

```matlab
addpath("matlab")
rf2TgmGeneratorApp("tools/cache/tyres/tgm/BFGoodrich_g-ForceR1_225-50-R16x7__c2bfff1f1528.tgm")
```

Die erste UI-Version zeigt TGM-Zusammenfassung, Querschnitt, Materialpunkte und
Materialtabelle. Zusaetzlich kann die UI das ODS-Input-Modell laden, Werte in
den Projektzellen tabweise bearbeiten und einen rekursiven
`Generate From Inputs`-Lauf starten. Der dateigleiche Acceptance-Test bleibt als
eigener Button vorhanden.

## Akzeptanztest

Der finale Port ist erst fertig, wenn MATLAB aus denselben ODS-Eingaben dieselbe
`.tgm`- und `.tbc`-Ausgabe erzeugt:

- `.tbc`: textgleich nach normalisierten Zeilenenden und trailing whitespace.
- `.tgm`: textgleich nach normalisierten Zeilenenden und ohne `LookupV2` /
  `PatchV1`.

Der aktuelle Harness kann diesen Vergleich bereits ausfuehren:

```powershell
& "C:\Users\Victor\.platformio\penv\Scripts\python.exe" .\tools\tgm_gen_ods.py `
  compare .\tmp\tgm_gen_port\reference_from_ods.tgm .\tmp\tgm_gen_port\generated.tgm `
  --strip-lookup --json
```

Aktueller harter Dateistand fuer die offizielle Beispiel-ODS:

- `generated.tbc` ist textgleich zur ODS-Referenz.
- `generated.tgm` ist textgleich zur ODS-Referenz, wenn nur `LookupV2` und
  `PatchV1` ausgeschlossen werden.

Aus MATLAB:

```matlab
addpath("matlab")
report = rf2TgmGenGenerate;
assert(report.equal)
```

Als reproduzierbarer Regressionstest:

```powershell
& "C:\Users\Victor\.platformio\penv\Scripts\python.exe" .\tools\test_tgm_gen_ods_acceptance.py --json
```

Der Test erzeugt Referenz und Kandidat neu, prueft `.tgm`/`.tbc` und laesst
den rekursiven Full-Sheet-Formelreport ohne Fallback laufen.

tTool-Vorbereitung aus MATLAB:

```matlab
addpath("matlab")
prep = rf2TgmPrepareTTool;
disp(prep.targetTgm)
```

Das erzeugt die geprueften Dateien neu und kopiert `generated_from_matlab.tgm`
und `generated_from_matlab.tbc` in den rFactor-2-`pTool`-Ordner. `LookupV2` und
`PatchV1` werden danach weiterhin in tTool erzeugt.

ODS-Eingabezellen als Projektmodell extrahieren:

```powershell
& "C:\Users\Victor\.platformio\penv\Scripts\python.exe" .\tools\tgm_gen_ods.py `
  --ods ".\tools\downloads\studio397\TGM Gen V0.33 - GY F1 1975 Front.ods" `
  extract-inputs --out .\tmp\tgm_gen_port\inputs.json --json
```

Aus MATLAB:

```matlab
inputs = rf2TgmGenExtractInputs;
```

Eine bearbeitete Projektdatei kann im rekursiven Modus wieder eingespeist
werden:

```powershell
& "C:\Users\Victor\.platformio\penv\Scripts\python.exe" .\tools\tgm_gen_ods.py `
  --ods ".\tools\downloads\studio397\TGM Gen V0.33 - GY F1 1975 Front.ods" `
  generate --out-dir .\tmp\tgm_gen_port_edit `
  --mode recursive `
  --project .\tmp\tgm_gen_port\inputs.json --json
```

## Formel-Harness

Der aktuelle Port kann die ODS-Formeln inventarisieren, Zellabhaengigkeiten
extrahieren und die relevanten Formeln rekursiv gegen gespeicherte ODS-Werte
auswerten. `cached` bleibt als Diagnosemodus vorhanden, der Standardpfad ist
aber der freie rekursive Zellgraph ohne Fallback.

```powershell
& "C:\Users\Victor\.platformio\penv\Scripts\python.exe" .\tools\tgm_gen_ods.py `
  --ods ".\tools\downloads\studio397\TGM Gen V0.33 - GY F1 1975 Front.ods" `
  formula-report --sheets General Realtime Materials --mode recursive --json
```

Aus MATLAB:

```matlab
addpath("matlab")
report = rf2TgmGenFormulaReport("Sheets", ["General", "Realtime", "Materials"]);
```

Der Report enthaelt pro Sheet:

- Anzahl der Formeln.
- erkannte Abhaengigkeitskanten.
- implementierte und noch fehlende Funktionsnamen.
- ausgewertete Formeln, Matches, Abweichungen und Fehlerbeispiele.

Aktueller Full-Sheet-Stand fuer die relevanten Sheets `About`, `General`,
`Geometry`, `Construction`, `TGM`, `Compound`, `Realtime`, `WLF`,
`ContactProps`, `LoadSens`, `Export`, `TBC`, `Materials`:

- 80.882 Formeln erkannt.
- 80.882 Formeln mit implementierten Funktionsnamen.
- 80.882 Formeln ausfuehrbar.
- 0 harte Evaluator-Fehler.
- 4.091 Zellwert-Abweichungen bleiben im cached Zellwerttest, vor allem Anzeigeformatierung,
  gerundete Displaywerte, LookupData-Ausschluss und ODS-iterative
  Selbstreferenzen.

Der alte cached Diagnosemodus kann bei Bedarf explizit genutzt werden:

```powershell
& "C:\Users\Victor\.platformio\penv\Scripts\python.exe" .\tools\tgm_gen_ods.py `
  --ods ".\tools\downloads\studio397\TGM Gen V0.33 - GY F1 1975 Front.ods" `
  formula-report --sheets General Realtime Materials --mode cached --json
```

Der rekursive Modus berechnet referenzierte Formelzellen neu und kann
uebergangsweise einzelne unresolved dependency edges auf gespeicherte ODS-Werte
zurueckfallen lassen. Fuer die offizielle Beispiel-ODS ist dieser Fallback nicht
mehr noetig: der rekursive Modus laeuft ohne Fallback und ohne harte
Formel-Fehler.

Rekursiver Full-Sheet-Stand:

- 80.882 Formeln erkannt.
- 80.882 Formeln rekursiv ausfuehrbar.
- 0 harte Evaluator-Fehler.
- 0 Fallback-Kanten.
- 4.842 Zellwert-Abweichungen bleiben gegen gespeicherte ODS-Displays.

Aktueller rekursiver Exportstand:

- `.tbc` ist rekursiv ohne Fallback textgleich zur ODS-Referenz.
- `.tgm` ist rekursiv ohne Fallback textgleich zur ODS-Referenz, wenn nur
  `LookupV2` und `PatchV1` ausgeschlossen werden.

Projektdateien aus `extract-inputs` wirken im rekursiven Modus als
Zell-Overrides. Damit ist der Pfad fuer editierbare Eingaben vorhanden; der
freie rekursive Export bleibt der Standardpfad.

## Status

Implementiert:

- ODS-Inventar und Formula-Coverage-Report.
- Formel-Harness fuer Zellreferenzen, benannte Bereiche, Array-Arithmetik,
  Lazy-`IF`/`IFERROR`, `INDIRECT`/`ADDRESS`, Lookup-Funktionen, Kriterienfunktionen
  und rekursive dependency evaluation.
- Evaluierter Generatorpfad fuer `generated.tgm` und `generated.tbc`.
- MATLAB-Wrapper `rf2TgmGenGenerate` fuer den finalen Datei-Akzeptanztest.
- Rekursiver Formelmodus ohne Fallback fuer die offizielle Beispiel-ODS.
- Port der originalen `Basic/Standard/CubSpline.xml`-Makrologik fuer
  `CUBSPLINE` inklusive Numerical-Recipes-Spline und monotonem `SplineX3`.
- ODS-Merge-/Span-Parser fuer korrekte Koordinaten von zusammengefuehrten
  Eingabezellen.
- Rekursive `.tgm`-/`.tbc`-Dateigleichheit ohne Fallback; `.tgm` ignoriert
  nur die bewusst ausgeschlossenen `LookupV2`-/`PatchV1`-Bloecke.
- ODS-Input-Projektmodell via `extract-inputs` und MATLAB-Wrapper
  `rf2TgmGenExtractInputs`.
- Projekt-Override-Pfad fuer rekursive Generatorlaeufe (`--project`).
- Rekonstruktion der gespeicherten ODS-`.tgm`- und `.tbc`-Exporttexte.
- TGM-Parser, Roundtrip-Writer ohne generated Lookup/Patch.
- Plotdaten fuer Nodes, Materialien, TreadDepth und PlyParams.
- Behaviour-Plotdaten aus dem neuesten tTool `CustomRealtimeTable.csv`.
- Moderne MATLAB-`uihtml`-App-Shell mit ersten Plots und Acceptance-Test-Button.
- UI-Tabelle fuer extrahierte ODS-Eingabezellen mit `Generate From Inputs`.
- UI-Behaviour-Plots fuer `Fy` ueber Schraeglaufwinkel, `Fx` ueber Slip Ratio
  und Kraftverlauf ueber Realtime-Testindex.
- tTool-Vorbereitung aus MATLAB und UI: gepruefte `.tgm`/`.tbc` nach `pTool`
  kopieren.

Noch offen:

- Zellwert-Golden-Tests gegen dynamisch neu berechnete ODS-Werte nach
  Eingabeaenderungen.
- Vollstaendige Plotdatenabdeckung aller ODS-Charts.
- Vollstaendige Editier- und Exportoberflaeche.
