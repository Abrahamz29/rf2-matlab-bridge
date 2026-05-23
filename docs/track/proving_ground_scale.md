# Proving Ground Scale Plan

## Ziel

Wir wollen rFactor 2 fuer automatisierte Fahrversuche auf einer moeglichst
grossen, flachen Testflaeche nutzen. Der Endzustand ist ein eigener
`Flat Proving Ground`, aber der erste lauffaehige Schritt muss kleiner und
pruefbar sein.

## Was jetzt sofort laeuft

Da auf dem aktuellen System kein kompletter GMT-Authoring-Workflow fuer neue
Track-Geometrie eingerichtet ist, nutzen wir fuer den ersten Ausbau das
vorhandene rF2-Testgelaende:

- `ISI_TigerMoth_2014`
- geladene Session: `TIGERMOTH_TESTTRACK`

Darauf sind jetzt Stufen-Szenarien vorbereitet:

- `scenarios\tigermoth_250m_step_steer.json`
- `scenarios\tigermoth_scaleout_open_loop.json`
- `scenarios\tigermoth_ai_monitor.json`

## Skalierungslogik

Der Ausbau ist bewusst gestuft:

1. `250 m`
2. `500 m`
3. `1000 m`
4. danach eigener Flat-Proving-Ground

Die ersten drei Stufen validieren:

- Shared-memory logging
- MATLAB-Auswertung
- Open-loop-Manoever
- AI-driver-Monitoring
- Track-Preflight und Session-Matching

Erst wenn diese Stufen sauber laufen, lohnt es sich, Zeit in eine eigene
Geometrie fuer mehrere Kilometer Testflaeche zu stecken.

## MATLAB-Start

Open-loop Stufe 250 m:

```matlab
cd("C:\Users\Victor\Documents\PYTHON\RFactor2")
setup_rf2_matlab()
rf2RunAutomation("scenarios\tigermoth_250m_step_steer.json")
```

Skalierungsstufen:

```matlab
rf2RunAutomation("scenarios\tigermoth_scaleout_open_loop.json")
```

AI-driver-Monitoring:

```matlab
rf2RunAIDriverMonitor(60)
```

## Nächster Schritt fuer echten Flat-Proving-Ground

Fuer eine eigene grosse Flaeche brauchen wir zusaetzlich:

- authorbare GMT-Geometrie
- saubere Track-Szene (`SCN`, `GDB`, `TDF`)
- AIW fuer Spawn/Fast Path/Testbereiche
- Packaging als `.rfcmp`

Das ist machbar, aber ein eigener Arbeitsschritt. Die TigerMoth-Stufen sind
der bewusst kleine, lauffaehige Vorbau davor.
