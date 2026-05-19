# Recherche: rFactor 2 Telemetrie nach MATLAB

## Direkt relevant und eingebunden

- TheIronWolfModding/rF2SharedMemoryMapPlugin
  - De-facto-Standard fuer rFactor-2-Telemetrie ausserhalb des Spiels.
  - Liefert Shared-Memory-Buffer fuer Telemetry, Scoring, Rules, ForceFeedback,
    Graphics, PitInfo, Weather und Extended.
  - Lokal eingebunden unter `vendor/rF2SharedMemoryMapPlugin`.

- TonyWhitley/pyRfactor2SharedMemory
  - Python-ctypes-Mapping der rF2-Shared-Memory-Structs.
  - Dient als Struct-Quelle fuer `python/rf2_matlab_bridge.py`.
  - Lokal eingebunden unter `vendor/pyRfactor2SharedMemory`.

- Domaslau/rF2SharedMemoryNet
  - Moderne .NET-Referenzimplementierung fuer rFactor 2 und Le Mans Ultimate.
  - Eingebunden als Kontrollreferenz unter `vendor/rF2SharedMemoryNet`.

## Nuetzlich, aber nicht als MATLAB-Kern eingebunden

- TinyPedal/TinyPedal
  - Open-Source Overlay, nutzt ebenfalls den Shared-Memory-Plugin.
  - Nuetzlich als Referenz fuer abgeleitete Telemetrieanzeigen, aber keine
    MATLAB-Schnittstelle.

- CrewChiefV4
  - Bekannter Client, liefert oft eine aktuelle Plugin-DLL mit.
  - Fuer diese MATLAB-Bridge nicht als Abhaengigkeit noetig.

- SimHub und Second Monitor
  - Praktische Clients zur Validierung, ob rF2 Shared Memory funktioniert.
  - Nicht eingebunden, weil sie fertige Apps statt Programmbibliotheken sind.

- schlegp/rF2SharedMemoryMapPlugin_Wine
  - Wine/Linux-Fork. Fuer dieses Windows/MATLAB-Setup nicht erforderlich.

## Entscheidung

Die MATLAB-Verbindung nutzt Python statt .NET oder direkter MATLAB-`memmapfile`,
weil die rF2-Structs sehr gross und verschachtelt sind. Python/ctypes kann die
vendorten Structs direkt lesen; MATLAB bekommt sauberes JSON und kann daraus
normale Structs und Tabellen erstellen.
