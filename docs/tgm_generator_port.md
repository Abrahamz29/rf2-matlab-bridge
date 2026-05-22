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
  generate --out-dir .\tmp\tgm_gen_port --json
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
  --mode recursive --fallback-on-error `
  --project .\tmp\tgm_gen_port\inputs.json --json
```

## Formel-Harness

Der aktuelle Port kann die ODS-Formeln inventarisieren, Zellabhaengigkeiten
extrahieren und einen ersten Teil der Formeln gegen gespeicherte ODS-Werte
auswerten. Fuer den Zwischenstand nutzt der Evaluator gespeicherte ODS-Werte fuer
referenzierte Zellen; damit pruefen wir Parser, Referenzen und Funktionssemantik,
bevor der komplette 80k-Zellgraph rekursiv frei gerechnet wird.

```powershell
& "C:\Users\Victor\.platformio\penv\Scripts\python.exe" .\tools\tgm_gen_ods.py `
  --ods ".\tools\downloads\studio397\TGM Gen V0.33 - GY F1 1975 Front.ods" `
  formula-report --sheets General Realtime Materials --json
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
- 5.004 Zellwert-Abweichungen bleiben im cached Zellwerttest, vor allem Anzeigeformatierung,
  gerundete Displaywerte, LookupData-Ausschluss und ODS-iterative
  Selbstreferenzen.

Zusaetzlich gibt es einen rekursiven Rechenmodus:

```powershell
& "C:\Users\Victor\.platformio\penv\Scripts\python.exe" .\tools\tgm_gen_ods.py `
  --ods ".\tools\downloads\studio397\TGM Gen V0.33 - GY F1 1975 Front.ods" `
  formula-report --sheets General Realtime Materials --mode recursive `
  --fallback-on-error --json
```

Der rekursive Modus berechnet referenzierte Formelzellen neu und kann
uebergangsweise einzelne unresolved dependency edges auf gespeicherte ODS-Werte
zurueckfallen lassen. Fuer die offizielle Beispiel-ODS laeuft der rekursive
Modus inzwischen ohne Fallback und ohne harte Formel-Fehler.

Rekursiver Full-Sheet-Stand:

- 80.882 Formeln erkannt.
- 80.882 Formeln rekursiv ausfuehrbar.
- 0 harte Evaluator-Fehler.
- 0 Fallback-Kanten.
- 10.682 Zellwert-Abweichungen bleiben gegen gespeicherte ODS-Displays.

Aktueller rekursiver Exportstand:

- `.tbc` ist rekursiv ohne Fallback textgleich zur ODS-Referenz.
- `.tgm` hat nach `LookupV2`/`PatchV1`-Ausschluss dieselbe Zeilenzahl wie die
  Referenz, unterscheidet sich aber noch in numerischen
  QuasiStatic-/Massen-/Materialwerten.

Projektdateien aus `extract-inputs` wirken im rekursiven Modus als
Zell-Overrides. Damit ist der Pfad fuer editierbare Eingaben vorhanden; die
vollstaendige `.tgm`-Dateigleichheit nach beliebigen Edits haengt noch an den
verbleibenden numerischen QSA-/Massen-/Material-Abweichungen.

## Status

Implementiert:

- ODS-Inventar und Formula-Coverage-Report.
- Formel-Harness fuer Zellreferenzen, benannte Bereiche, Array-Arithmetik,
  Lazy-`IF`/`IFERROR`, `INDIRECT`/`ADDRESS`, Lookup-Funktionen, Kriterienfunktionen
  und cached dependency evaluation.
- Evaluierter Generatorpfad fuer `generated.tgm` und `generated.tbc`.
- MATLAB-Wrapper `rf2TgmGenGenerate` fuer den finalen Datei-Akzeptanztest.
- Rekursiver Formelmodus mit kontrolliertem Fallback fuer noch nicht freie
  Dependency-Kanten.
- Port der originalen `Basic/Standard/CubSpline.xml`-Makrologik fuer
  `CUBSPLINE` inklusive Numerical-Recipes-Spline und monotonem `SplineX3`.
- ODS-Merge-/Span-Parser fuer korrekte Koordinaten von zusammengefuehrten
  Eingabezellen.
- Rekursive `.tbc`-Dateigleichheit ohne Fallback.
- ODS-Input-Projektmodell via `extract-inputs` und MATLAB-Wrapper
  `rf2TgmGenExtractInputs`.
- Projekt-Override-Pfad fuer rekursive Generatorlaeufe (`--project`).
- Rekonstruktion der gespeicherten ODS-`.tgm`- und `.tbc`-Exporttexte.
- TGM-Parser, Roundtrip-Writer ohne generated Lookup/Patch.
- Plotdaten fuer Nodes, Materialien, TreadDepth und PlyParams.
- Moderne MATLAB-`uihtml`-App-Shell mit ersten Plots und Acceptance-Test-Button.
- UI-Tabelle fuer extrahierte ODS-Eingabezellen mit `Generate From Inputs`.

Noch offen:

- Rekursive `.tgm`-Dateigleichheit ohne gespeicherte Abhaengigkeitswerte.
  Aktuell verbleiben numerische QSA-/Massen-/Material-Abweichungen.
- Zellwert-Golden-Tests gegen dynamisch neu berechnete ODS-Werte nach
  Eingabeaenderungen.
- Vollstaendige Plotdatenabdeckung aller ODS-Charts.
- Vollstaendige Editier- und Exportoberflaeche.
