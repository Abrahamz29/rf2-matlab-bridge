# Tyres

Alles zum Reifenmodell liegt hier. Damit bleibt TGM/tTool-Arbeit getrennt von
Strecken-, Fahrzeug- und Telemetrie-Automation.

## Struktur

- `input/tgm/`: manuell importierte `.tgm`-Quelldateien.
- `input/ods/`: TGM-Generator- und tTool-Tabellen.
- `input/legacy/`: alte oder falsch benannte TGM-Arbeitsdateien, die nicht als
  kanonische Quelle verwendet werden sollten.
- `references/`: PDFs, Website-Notizen, Videos und externe Reifenmodell-Quellen.
- `database/`: SQLite-Datenbank fuer die MATLAB-UI und DB-gestuetzte Auswahl.
- `cache/tgm/`: lokale Arbeitskopien bekannter Reifen aus der DB. Dieser Ordner
  ist bewusst ignoriert, aber lokal nutzbar.
- `scenarios/`: Reifen- und tTool-Testplaene sowie Ergebnisvorlagen.
- `output/lookup/`: zerlegte Lookup-/Patch-Exports. Dieser Ordner ist
  generiert und ignoriert.

## Wichtige Einstiegspunkte

- Neuer Reifenplot: `tyres/matlab/apps/tyre_designer/`
- Reifen-DB: `tyres/database/rf2_tyre_database.sqlite`
- Reifen-DB neu bauen: `py .\tyres\tools\build_tyre_database.py`
- Lookup zerlegen:

```powershell
py .\tyres\tools\tgm_lookup_extract.py .\tyres\input\tgm\G_9.2-20.0-13x10_Soft_Slick_1975.tgm --include-patch
```

