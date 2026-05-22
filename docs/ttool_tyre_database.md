# TTool Reifendatenbank

Die lokale Reifendatenbank sammelt rFactor-2-Reifen in zwei Ebenen:

- **Inventar**: gefundene `.tgm`-Dateien, Quellen, Hashes und auslesbare
  TGM-Parameter.
- **Verhalten**: importierte TTool-Ergebnisdateien `CustomRealtimeTable.csv`
  mit Samples und einfachen Kennwerten pro `Realtime Test Index`.

Aufbauen:

```powershell
& "C:\Users\Victor\.platformio\penv\Scripts\python.exe" .\tools\build_tyre_database.py
```

Ergebnis:

```text
scenarios\tyre\database\rf2_tyre_database.sqlite
```

Kopierte `.tgm`-Arbeitskopien liegen lokal unter `tools\cache\tyres\tgm`.
Dieser Ordner ist absichtlich ignoriert, weil er installierte rFactor-2-Inhalte
enthaelt. Die SQLite-Datenbank speichert Metadaten, Parameter und TTool-CSV-
Messwerte, aber keine TGM-Dateiinhalte.

Wichtige Tabellen:

- `tyres`: eindeutige Reifen nach SHA-256.
- `tyre_sources`: alle lokalen Fundorte pro Reifen.
- `tyre_parameters`: aus `.tgm` extrahierte Abschnitte wie
  `QuasiStaticAnalysis`, `Realtime`, `LookupData` und `Node`.
- `archive_candidates`: `.mas`/`.rfcmp`-Archive mit TGM-Dateinamen-Hinweisen.
- `ttool_runs`, `ttool_samples`, `behaviour_summaries`: importierte
  TTool-Verhaltensdaten.

Hinweis: Verschluesselte MAS-Archive werden nur als Kandidaten indexiert. Fuer
die erste Datenbank werden automatisch nur offen liegende `.tgm`-Dateien
kopiert und geparst.

Workshop-`rfcmp`-Pakete koennen optional mitgescannt werden, das dauert je nach
Installation deutlich laenger:

```powershell
& "C:\Users\Victor\.platformio\penv\Scripts\python.exe" .\tools\build_tyre_database.py --include-workshop-packages
```

## MATLAB-Smoke fuer alle bekannten Reifen

Alle lokal bekannten Arbeitskopien unter `tools\cache\tyres\tgm` koennen gegen
den MATLAB-TGM-Parser, die Plotdaten-Erzeugung, Gurtlagen-/Querschnittsdaten
und den verlustfreien Writer-Roundtrip geprueft werden:

```powershell
.\tools\Test-TgmAllKnownTyres.ps1
```

Der Test schreibt:

```text
tmp\tgm_all_known_tyres_smoke_report.json
```

Dieser Smoke ist kein ODS-Formelvergleich pro Reifen. Dafuer waeren die
jeweiligen TGM-Gen-ODS-Projektmappen noetig. Er stellt aber sicher, dass alle
bekannten `.tgm`-Reifen vom MATLAB-Tool gelesen, geplottet und ohne
Textverlust wieder geschrieben werden koennen.
