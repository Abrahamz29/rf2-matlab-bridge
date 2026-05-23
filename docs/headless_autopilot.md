# Headless, Autopilot und Plot-Entwicklung

## Kurzfassung

Echtes Headless mit Player-Reifen- und Fahrdynamikdaten ist in rFactor 2 nicht
der richtige Weg. Der Dedicated Server kann mit `+oneclick`/`+nowindow` ohne UI
laufen, liefert aber nicht die lokale Player-Physik wie eine fahrende Session.

Praktischer Workflow:

1. Plots ohne rF2 entwickeln: Mock-Datenquelle.
2. Echte Daten testen: rF2 im Fenster starten, Session laden, AI-Control mit `I`
   toggeln.

## Mock-Modus in MATLAB

Rolling-Live-Plot mit synthetischen Daten:

```matlab
cd("C:\Users\Victor\Documents\PYTHON\RFactor2")
setup_rf2_matlab()
rf2RollingLivePlot(15, 20, "mock")
```

Capture plus Uebersichtsplot:

```matlab
run = rf2PlotLatest(60, 20, "mock");
```

Das nutzt `RF2MockClient`, der dieselbe Schnittstelle wie `RF2Client` anbietet.
Damit koennen Plot-Layouts, Achsen, Legends und Signalberechnungen entwickelt
werden, ohne dass rF2 eine Strecke geladen hat.

## Echte rF2-Daten mit AI-Control

Die Config ist vorbereitet:

- `No AI Control = 0`
- `Pause If Focus Lost = false`
- `Control - Toggle AI Control` liegt auf Taste `I`

Ablauf:

1. rF2 starten.
2. Strecke/Auto laden.
3. Auf die Strecke gehen.
4. Taste `I` druecken, damit AI das Auto faehrt.
5. MATLAB starten:

```matlab
setup_rf2_matlab()
rf2RollingLivePlot(15, 20)
```

## Warum kein echter Headless-Player?

Die rF2-CLI dokumentiert `+oneclick` und `+nowindow` fuer Dedicated Server. Das
ist serverseitig und nicht gleichbedeutend mit einer lokalen Spieler-Session,
die Reifen-, Aero-, Input- und Fahrdynamikdaten fuer ein Player-Fahrzeug liefert.
Fuer unsere MATLAB-Plots sind die Shared-Memory-Telemetry-Buffer aus einer
laufenden Single-Player/Multiplayer-Client-Session der relevante Pfad.

