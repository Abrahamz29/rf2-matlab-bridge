# GitHub Bootstrap

Dieses Projekt ist lokal als Git-Repository vorbereitet. Falls noch kein
GitHub-Remote existiert, lege ein neues leeres Repository auf GitHub an und
verbinde es dann lokal:

```powershell
git remote add origin https://github.com/<owner>/rf2-matlab-bridge.git
git push -u origin main
```

Alternativ mit SSH:

```powershell
git remote add origin git@github.com:<owner>/rf2-matlab-bridge.git
git push -u origin main
```

Empfohlener Ablauf fuer weitere Arbeit:

```powershell
git status
git add .
git commit -m "Kurzbeschreibung der Aenderung"
git push
```

Hinweise:

- Das Projekt ist fuer regelmaessige kleine Commits ausgelegt.
- Nach jedem verifizierten Arbeitspaket sollte ein Commit entstehen.
- Vor laengeren Pausen oder nach stabilen Zwischenstaenden sollte gepusht
  werden.
