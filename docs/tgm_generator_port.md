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

## MATLAB UI starten

```matlab
addpath("matlab")
rf2TgmGeneratorApp("tools/cache/tyres/tgm/BFGoodrich_g-ForceR1_225-50-R16x7__c2bfff1f1528.tgm")
```

Die erste UI-Version zeigt TGM-Zusammenfassung, Querschnitt, Materialpunkte und
Materialtabelle. Die Berechnung des kompletten ODS-Formelgraphen wird ueber den
Golden-Reference-Harness iterativ ergaenzt.

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

## Status

Implementiert:

- ODS-Inventar und Formula-Coverage-Report.
- Rekonstruktion der gespeicherten ODS-`.tgm`- und `.tbc`-Exporttexte.
- TGM-Parser, Roundtrip-Writer ohne generated Lookup/Patch.
- Plotdaten fuer Nodes, Materialien, TreadDepth und PlyParams.
- Moderne MATLAB-`uihtml`-App-Shell mit ersten Plots.

Noch offen:

- Vollstaendige Formel-Engine fuer alle ODS-Formeln.
- Zellwert-Golden-Tests gegen dynamisch neu berechnete ODS-Werte.
- Vollstaendige Plotdatenabdeckung aller ODS-Charts.
- Vollstaendige Editier- und Exportoberflaeche.
