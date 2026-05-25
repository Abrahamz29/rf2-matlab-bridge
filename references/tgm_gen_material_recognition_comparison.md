# TGM Gen Material Recognition Comparison

Source: `input/TGM Gen V0.33 - GY F1 1975 Front.ods`  
Generated reference: ODS `Export` sheet reconstructed with `tyres/tools/tgm_gen_ods.py`.

Purpose: compare the materials explicitly selected in the example spreadsheet
with the materials recognized from the generated TGM node material rows.

## Materials Selected In The Excel/ODS

| Role | TGM kind | Selected material | E multiplier | Density multiplier |
| --- | --- | --- | ---: | ---: |
| Tread | TreadMaterial | Race - G - FI 1975 Tread | 1 | 1 |
| Tread Sidewall | TreadMaterial | Race - G - FI 1975 Tread Sidewall | 1 | 1 |
| Bulk Bead/Filler | BulkMaterial | Race - G - FI 1975 Filler | 0.95 | 1.018 |
| Bulk Sidewall | BulkMaterial | Race - G - FI 1975 Sidewall | 0.9 | 1.012 |
| Bulk Belt | BulkMaterial | Race - G - FI 1975 Sidewall | 1 | 1.01 |
| Inner Liner | BulkMaterial | Butyl | 1 | 1 |
| Bead | PlyMaterial | Steel - 0.8% Carbon Steel | 0.2 | 1 |
| Ply1 | PlyMaterial | Nylon - 70s | 0.875 | 1.01 |
| Ply2 | PlyMaterial | Nylon - 70s | 0.875 | 1.01 |
| Ply3 | PlyMaterial | Nylon - 70s | 0.875 | 1.01 |
| Ply4 | PlyMaterial | Nylon - 70s | 0.875 | 1.01 |
| Bead ply | PlyMaterial | Nylon - 70s | 0.875 | 1.01 |

## Recognized From Generated TGM

| TGM kind | Recognized material | Groups | Node range | Layer/index | E multiplier fit | Density multiplier fit |
| --- | --- | ---: | --- | --- | --- | --- |
| TreadMaterial | Race - G - FI 1975 Tread | 47 | 15-61 | 1 | 1.000-1.000 | 1.000 |
| TreadMaterial | Race - G - FI 1975 Tread Sidewall | 28 | 1-75 | 1 | 0.999-1.000 | 1.000 |
| BulkMaterial | Race - G - FI 1975 Sidewall | 63 | 7-69 | 1 | 0.900-1.000 | 1.023-1.043 |
| BulkMaterial | Race - Y - Formula Filler | 4 | 4-72 | 1 | 0.958-1.064 | 0.894-0.902 |
| BulkMaterial | Race - Kart - Filler | 2 | 1-75 | 1 | 0.961 | 0.970 |
| BulkMaterial | Stock Car 1970's Bulk | 2 | 2-74 | 1 | 0.977 | 0.980 |
| BulkMaterial | Race - M - GT - Filler | 2 | 3-73 | 1 | 0.923 | 0.888 |
| BulkMaterial | T280 Belt | 2 | 6-70 | 1 | 0.954 | 1.034 |
| PlyMaterial | Nylon - 70s | 346 | 1-75 | 1-7 | 0.861-0.874 | 1.000-1.010 |
| PlyMaterial | Nylon - Soft | 56 | 17-59 | 5-6 | 0.815-1.138 | 0.961 |
| PlyMaterial | Steel - Soft | 4 | 1-75 | 1 | 0.251 | 1.000 |

## Differences

| TGM kind | Expected from Excel | Recognized | Difference |
| --- | --- | --- | --- |
| TreadMaterial | Race - G - FI 1975 Tread; Race - G - FI 1975 Tread Sidewall | Same two materials | Good match. The generator blends tread and tread-sidewall by node, but recognition still resolves to the two selected materials. |
| BulkMaterial | Race - G - FI 1975 Filler; Race - G - FI 1975 Sidewall; Butyl | Mostly Race - G - FI 1975 Sidewall plus several unrelated filler/bulk candidates | Weak area. Bulk rows are node-wise mixtures of filler, sidewall, belt, inner-liner/tread influence and multipliers. The current recognizer assigns each mixed result to the closest single library material, so it invents extra materials. |
| PlyMaterial | Nylon - 70s; Steel - 0.8% Carbon Steel | Nylon - 70s; Nylon - Soft; Steel - Soft | Partial match. Most plies resolve correctly to Nylon - 70s. Some layer-5/6 points look closer to Nylon - Soft after scaling. Bead steel is selected as Steel - 0.8% Carbon Steel with E multiplier 0.2, but the recognizer prefers Steel - Soft because it fits with a smaller scale penalty. |

## Interpretation

The Excel file is a good reference because it exposes the intended source
materials. It also shows why pure property matching is not enough:

- Tread recognition is reliable for this example.
- Bulk recognition should be treated as mixed-material reconstruction, not
  single-material classification.
- Ply recognition needs to preserve known quick multipliers. Otherwise
  intentionally scaled materials can be mistaken for a softer unscaled material.

Recommended next improvement: add an ODS-aware comparison mode that carries the
selected Excel material names and quick multipliers into the designer. Use
property matching only as fallback for imported TGMs without source workbook.
