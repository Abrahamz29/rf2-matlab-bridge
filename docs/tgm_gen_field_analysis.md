# TGM Gen Field Analysis

Dieses Werkzeug analysiert die offizielle Studio-397-TGM-Gen-ODS auf Felder,
die das finale Reifenmodell beeinflussen. Standard ist die `.tgm`-Ausgabe als
finales Reifenmodell. Ziel ist eine Referenzkopie, in der Feldnutzung farblich
sichtbar wird:

- unveraendert: beeinflusst die finale `.tgm`
- hellblau: wird nur fuer die `.tbc` benoetigt
- rot: beeinflusst weder `.tgm` noch `.tbc`

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
tmp\tgm_gen_field_analysis\TGM Gen V0.33 - GY F1 1975 Front - field-usage-red-blue-tgm.ods
tmp\tgm_gen_field_analysis\field_analysis_report_tgm.json
tmp\tgm_gen_field_analysis\field_usage_tgm.csv
```

Wenn das ausgewaehlte Output-Dependency-Set `.tgm` und `.tbc` zusammen sein
soll:

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

Hellblau markiert werden nur nicht-formula Eingabe-/Projektfelder auf den
Haupt-Input-Sheets, die im `.tgm`-Dependency-Set fehlen, aber im kombinierten
`.tgm`+`.tbc`-Dependency-Set enthalten sind. Rot markiert werden nur
nicht-formula Eingabe-/Projektfelder, die weder `.tgm` noch `.tbc`
beeinflussen. Formelzellen werden nicht farbig markiert, weil sie interne
Rechenlogik sind.

## Aktueller Stand

Beim letzten TGM-only-Lauf wurden `129` input-artige Felder hellblau markiert,
weil sie nur die `.tbc` beeinflussen. Weitere `3415` input-artige Felder wurden
rot markiert, weil sie weder `.tgm` noch `.tbc` beeinflussen.

Die hellblauen Felder liegen aktuell in:

- `TBC`: `105`
- `Compound`: `12`
- `General`: `5`
- `LoadSens`: `4`
- `ContactProps`: `3`

Die markierte Kopie ist ZIP/XML-valide und erzeugt dieselben Exporttexte wie
das Original:

- `.tgm`: textgleich ohne `LookupV2`/`PatchV1`
- `.tbc`: textgleich

LibreOffice war auf dem PATH nicht verfuegbar; die Validierung laeuft daher
ueber ODS-ZIP/XML-Pruefung und Exporttextvergleich.
