# TGM Lookup Table Research

## Current public documentation

The official Studio-397 TGM Tyre Tool quick start describes the TGM as a brush
model with a 6-DOF rigid ring. It says `[QuasiStaticAnalysis]` defines the test
ranges and bounds for lookup generation, `[Node]` defines the tyre geometry and
materials, `[Realtime]` defines the real-time rubber/contact parameters, and
`[LookupData]` is tTool-generated test result data for carcass rigidities,
growth rates and similar tyre properties over the QSA condition range.

The public modding handbook lists `[LookupData]` fields as `Version`, `Bin` and
`Checksum`, but does not document the binary schema or semantic field names.

Studio-397 forum discussion is consistent with this: tTool calculates the tyre
construction response and writes lookup tables; slip, camber thrust and similar
behaviour is not supplied as a simple user-editable slip table in the TGM.

## Local reverse-engineering result

Two on-disk formats are present in our tyre files:

- Legacy `[LookupData]`: `Bin=` lines contain hexadecimal bytes.
- Current `[LookupV2]`: `P=` lines use a custom base85 alphabet from `*` to
  `~`. Five encoded characters decode to one big-endian 32-bit word.

`[PatchV1]` uses the same base85 encoding for `R=` and `D=` streams. It also
stores `DeflectionStepSize`.

For `tyres/input/tgm/G_9.2-20.0-13x10_Soft_Slick_1975.tgm`:

- Lookup format: `LookupV2`, version `1.104`.
- QSA grid: `5` pressures x `3` carcass temperatures x `4` rotation speeds =
  `60` condition points.
- Decoded lookup payload: `174720` bytes = `43680` 32-bit words.
- Words per QSA condition point: `728`.
- Decoded PatchV1 streams:
  - `R`: `1408` bytes = `352` 32-bit words.
  - `D`: `583440` bytes = `145860` 32-bit words.

## Practical status

We can now make the lookup payload usable as raw data:

```powershell
py .\tyres\tools\tgm_lookup_extract.py .\tyres\input\tgm\G_9.2-20.0-13x10_Soft_Slick_1975.tgm --include-patch
```

Output is written to:

```text
tyres\output\lookup\G_9.2-20.0-13x10_Soft_Slick_1975
```

Important files:

- `summary.json`: source hashes, QSA axes, format, byte counts and paths.
- `lookup_payload.bin`: decoded raw lookup bytes.
- `lookup_words.csv`: every 32-bit word as hex, uint32, int32, float32 BE and
  float32 LE, with QSA condition indices where the payload divides cleanly.
- `lookup_matrix_float32_be.csv`: one row per QSA condition point, one column
  per big-endian float32 interpretation.
- `patch_r_payload.bin`, `patch_d_payload.bin`: decoded PatchV1 streams.
- `patch_r_words.csv`, `patch_d_words.csv`: optional word views when
  `--include-patch` is used.

## Known limit

The extractor does not claim semantic names for the individual 32-bit words.
Those names are not publicly documented, and values show a mix of plausible
float32 values plus header/flag-like words. QSA record labels in the CSV use the
conservative axis order `GaugePressure -> CarcassTemperature -> RotationSquared`;
the raw `word_index` remains the authoritative position until tTool behaviour is
diffed against controlled changes. The next safe step is comparative reverse
engineering: generate controlled TGMs with one QSA axis or one node parameter
changed, export the lookup each time, then diff decoded word indices against
tTool's visible real-time outputs.


