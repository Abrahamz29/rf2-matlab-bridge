# Automation Harness

## Ziel

Dieses Setup fuehrt Open-Loop-Manoever in rFactor 2 automatisiert aus und loggt
gleichzeitig Shared-Memory-Telemetrie fuer MATLAB.

Erste Version:

- Input-Kanal: Windows-Tastatur-Events per `SendInput`
- Telemetrie: `rFactor2SharedMemoryMapPlugin64.dll`
- Output: CSV je Szenario

Wichtig: Das ist funktional fuer Sweeps und Reproduzierbarkeit, aber nicht die
Endstufe fuer hochqualitative Analoganregungen. Fuer feinere Lenkprofile ist
spaeter ein virtueller Analog-Controller wie `vJoy` sinnvoll.

## Voraussetzungen in rF2

- Session geladen
- Fahrzeug auf der Strecke
- AI-Control aus
- Fensterfokus auf rFactor 2

Die Konfiguration ist bereits angepasst:

- `No AI Control = 0`
- `Pause If Focus Lost = false`
- `WindowedMode = 1`

## Starten

PowerShell:

```powershell
cd C:\Users\Victor\Documents\PYTHON\RFactor2
& "C:\Users\Victor\.platformio\penv\Scripts\python.exe" .\python\rf2_automation.py .\scenarios\blacklake_step_steer_batch.json
```

Oder aus MATLAB:

```matlab
cd("C:\Users\Victor\Documents\PYTHON\RFactor2")
setup_rf2_matlab()
rf2RunAutomation("scenarios\blacklake_step_steer_batch.json")
```

Die Logs landen unter:

```text
logs\<batch_name>\<timestamp>_<scenario_name>\telemetry.csv
```

## Beispiel-Batches

- `scenarios\blacklake_step_steer_batch.json`
- `scenarios\blacklake_sine_steer_batch.json`
- `scenarios\tigermoth_250m_step_steer.json`
- `scenarios\tigermoth_scaleout_open_loop.json`
- `scenarios\tigermoth_ai_monitor.json`

## Track-Preflight

Der Runner kennt jetzt installierte rF2-Locations und kann beim Start
validieren, ob ein Szenario zum aktuell geladenen Track passt.

Installierte Tracks als JSON ausgeben:

```powershell
& "C:\Users\Victor\.platformio\penv\Scripts\python.exe" .\python\rf2_automation.py --list-tracks
```

Oder in MATLAB:

```matlab
tracks = rf2ListInstalledTracks();
```

## AI-driver-Monitoring

Fuer Session-Mitschnitte mit lokalem AI-Fahrer:

```matlab
rf2RunAIDriverMonitor(60)
```

Das setzt lokal AI-Control, loggt Telemetrie und stellt danach wieder auf
Player-Control zurueck.

## MATLAB closed-loop controller

Wenn fuer eine Strecke kein AI-Fahrer gewuenscht ist, kann MATLAB selbst als
Regler laufen:

```matlab
setup_rf2_matlab()
run = rf2RunMatlabController(@rf2BlackLakeExampleController, 30, 20);
```

Dabei:

- liest `RF2Client` live Shared-Memory-Telemetrie
- setzt `RF2Actuator` Gas, Bremse und Lenkung
- berechnet die Funktion `rf2BlackLakeExampleController` den naechsten Befehl

Fuer BlackLake ist das der richtige Pfad, sobald die Strecke installiert ist.

## CSV in MATLAB laden

```matlab
T = readtable("logs\blacklake_step_steer\...\telemetry.csv");
plot(T.elapsed_s, T.speed_kph)
```

Nuetzliche Kanaele:

- `command_throttle`, `command_brake`, `command_steer`
- `driver_throttle`, `driver_brake`, `driver_steer`
- `speed_kph`, `rpm`, `lat_g`, `long_g`
- `fl_load_n`, `fr_load_n`, `rl_load_n`, `rr_load_n`
- `fl_pressure_kpa` usw.

## Naechster Ausbauschritt

Wenn du wirklich viele Varianten mit sauberer Analoglenkung fahren willst, ist
der richtige naechste Schritt ein zweiter Aktuator-Backend:

- `keyboard` fuer sofortige Open-Loop-Tests
- `vJoy` oder `ViGEm` fuer echte analoge Lenk-, Gas- und Bremsprofile

Siehe auch: `docs/proving_ground_scale.md`
