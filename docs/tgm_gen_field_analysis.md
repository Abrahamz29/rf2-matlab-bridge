# TGM Gen Field Analysis

Dieses Werkzeug analysiert die offizielle Studio-397-TGM-Gen-ODS auf Felder,
die das finale Reifenmodell beeinflussen. Standard ist die `.tgm`-Ausgabe als
finales Reifenmodell. Ziel ist eine Referenzkopie, in der nicht benoetigte
Projekt-/Eingabefelder rot markiert sind.

Ausgangsdatei:

```text
tools\downloads\studio397\TGM Gen V0.33 - GY F1 1975 Front.ods
```

Analyse ausfuehren:

```powershell
& "C:\Users\Victor\.platformio\penv\Scripts\python.exe" .\tools\analyze_tgm_gen_fields.py --json
```

Erzeugt:

```text
tmp\tgm_gen_field_analysis\TGM Gen V0.33 - GY F1 1975 Front - unused-fields-red-tgm.ods
tmp\tgm_gen_field_analysis\field_analysis_report_tgm.json
tmp\tgm_gen_field_analysis\field_usage_tgm.csv
```

Wenn auch `.tbc`-only Felder als output-relevant gelten sollen:

```powershell
& "C:\Users\Victor\.platformio\penv\Scripts\python.exe" .\tools\analyze_tgm_gen_fields.py --target tgm-tbc --json
```

## Methode

- Zielzellen sind `Export!A:A` bis `About!D31 + 1` fuer die `.tgm`-Ausgabe
  (`--target tgm`). Mit `--target tgm-tbc` kommt `TBC!O:O` fuer die `.tbc`-
  Ausgabe hinzu.
- Die vorhandene rekursive Formula-Engine wird dynamisch getraced.
- Zusaetzlich laeuft ein statischer Dependency-Walk ueber alle Formelreferenzen,
  damit auch nicht aktuell aktive `IF`-Aeste sichtbar bleiben.
- ODS-Content-Validations werden geparst. Dropdown-Quellen bleiben erhalten.
- Material-Dropdowns werden besonders behandelt: komplette Materialdatenbloecke
  hinter `MaterialList*` bleiben als benoetigt markiert, weil eine andere
  Dropdown-Auswahl diese Daten zum Output machen kann.
- Basic/VBA-Makros werden gelesen. `SaveTGM` wird fuer Dateipfade und Export-
  Reichweite beruecksichtigt (`About!P28`, `About!P29`, `About!D31`,
  `General!I47`).

Rot markiert werden nur nicht-formula Eingabe-/Projektfelder auf den
Haupt-Input-Sheets, die nicht im Output-Dependency-Set liegen. Formelzellen
werden nicht rot markiert, weil sie interne Rechenlogik sind.

## Aktueller Stand

Beim letzten TGM-only-Lauf wurden `3544` unbenoetigte input-artige Felder rot
markiert. Beim kombinierten `.tgm`+`.tbc`-Lauf waren es `3415`.
Die markierte Kopie ist ZIP/XML-valide und erzeugt dieselben Exporttexte wie
das Original:

- `.tgm`: textgleich ohne `LookupV2`/`PatchV1`
- `.tbc`: textgleich

LibreOffice war auf dem PATH nicht verfuegbar; die Validierung laeuft daher
ueber ODS-ZIP/XML-Pruefung und Exporttextvergleich.
