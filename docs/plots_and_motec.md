# Plots und MoTeC

## Sinnvolle MATLAB-Plots

Direkt nutzbar:

```matlab
cd("C:\Users\Victor\Documents\PYTHON\RFactor2")
setup_rf2_matlab()

run = rf2CollectTelemetry(120, 20);
rf2PlotTelemetry(run);
```

Kurzform:

```matlab
run = rf2PlotLatest(120, 20);
```

Die Uebersicht zeigt:

- Speed und RPM
- Throttle, Brake, Steering
- Longitudinal-G, Lateral-G, Yaw Rate
- Tire Load pro Rad
- Tire Surface/Carcass Temperature pro Rad
- Tire Pressure und Grip Fraction pro Rad

Weitere interessante Plots aus denselben Arrays:

- `run.longSlipProxy`: LongitudinalPatchVel minus LongitudinalGroundVel
- `run.latSlipProxy`: LateralPatchVel minus LateralGroundVel
- `run.lateralForce` vs. `run.longitudinalForce`: Reifenkraft-Scatter
- `run.pressure` vs. `run.surfaceTempC`: Druck/Temperatur-Verlauf
- `run.rideHeight` zusammen mit Aero-Daten aus `data.convenience.playerTelemetry`

## MoTeC

MoTeC i2 Pro ist fuer rFactor 2 weiterhin sinnvoll, aber fuer einen anderen
Workflow:

- MoTeC/DAMPlugin: sehr gut fuer Offline-Lap-Analyse, Overlays mehrerer Runden,
  Workbooks, Math-Channels, Setup-Vergleiche.
- MATLAB/Shared-Memory-Bridge: besser fuer Live-Analyse, eigene Modelle,
  Regler/Observer, automatisches Logging und schnelle numerische Auswertung.

Der uebliche rF2-MoTeC-Weg ist:

1. MoTeC i2 Pro installieren.
2. DAMPlugin fuer rF2 installieren.
3. Mit `DAMPlugin.INI` Kanallisten und Samplingraten setzen.
4. In rF2 fahren, DAMPlugin schreibt MoTeC-Logs.
5. Logs in i2 Pro oeffnen.

Bekannte Einschraenkung: Nicht jedes Fahrzeug gibt alle Reifen- und Aero-Kanaele
vollstaendig aus. Manche offiziellen Fahrzeuge liefern weniger Reifenkanaldaten.

Quellen:

- https://forum.studio-397.com/index.php?threads/damplugin-for-rf2.49363/
- https://orion-miller.github.io/rfactor2-motec-workspace/
- https://www.motec.com.au/i2/i2downloads/
