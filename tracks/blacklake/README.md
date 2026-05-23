# BlackLake

Custom proving-ground authoring workspace for rFactor 2.

Generated stages:
- `250m`: half extent 125 m, lane length 220 m
- `500m`: half extent 250 m, lane length 440 m
- `1000m`: half extent 500 m, lane length 900 m
- `2000m`: half extent 1000 m, lane length 1800 m
- `5000m`: half extent 2500 m, lane length 4600 m
- `12000m`: half extent 6000 m, lane length 11000 m

Build source scaffolding:

```powershell
& "C:\Users\Victor\.platformio\penv\Scripts\python.exe" .\tracks\blacklake\tools\blacklake_builder.py --all
```

The generator creates geometry source and ModDev text scaffolding.
Export GMT for a stage with:

```powershell
.\tracks\blacklake\tools\Export-BlackLakeGmt.ps1 -Stage 250m -InstallModDev
```



