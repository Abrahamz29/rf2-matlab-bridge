# Shore A To Young Modulus Formula References

Retrieved: 2026-05-24

This note records the external references used for the interactive Shore A /
Young's modulus correlation plot:
`tyres/analysis/young_modulus_vs_shore_a.svg` and
`tyres/analysis/young_modulus_vs_shore_a.html`.

## Sources

- TGM Gen V0.33 spreadsheet formula, local file
  `input/TGM Gen V0.33 - GY F1 1975 Front.ods`, sheet `Materials`.
  The Shore A rows use the formula pattern
  `of:=IF([.B23];ROUND(100*ERF(0.0003186*[.B23]^0.5);3);"")`,
  where the referenced cell is the Young's modulus in Pa. Equivalent:
  `ShoreA = ROUND(100 * ERF(0.0003186 * sqrt(E_Pa)), 3)`.
  Inverted for plotting modulus over Shore A:
  `E_Pa = (ERFINV(ShoreA / 100) / 0.0003186)^2`.

- Gent, A. N., "On the relation between indentation hardness and Young's
  modulus", Transactions of the Institution of the Rubber Industry, 1958.
  Used for the classic Shore A to Young's modulus approximation.
  URL: https://cir.nii.ac.jp/crid/1360855571087985536

- Meththananda, I. M., Parker, S., Patel, M. P., and Braden, M.,
  "The relationship between Shore hardness of elastomeric dental materials
  and Young's modulus", Dental Materials, 2009.
  Used to cross-check the BS 903 / error-function equation with
  `k = 3.186e-4 Pa^-1/2`.
  URL: https://www.sciencedirect.com/science/article/pii/S0109564109001237

- Lodi Rizzini, D. et al., "A Bioinspired Cownose Ray Robot for Seabed
  Exploration", Biomimetics, 2023.
  Used as an open-access cross-check for the same empirical Shore A to
  Young's modulus error-function relation.
  URL: https://www.mdpi.com/2313-7673/8/1/30

- ScienceDirect article page for Shore hardness / Young's modulus conversion
  discussion and formula overview.
  Used as a cross-check for Gent, Rigbi, Battermann-Kohler, and related
  empirical approximations.
  URL: https://www.sciencedirect.com/science/article/pii/S0142941825003101

- Mix, A. W. and Giacomin, A. J., "Dimensionless Durometry",
  Polymer-Plastics Technology and Engineering, 2011.
  Used for the dimensionless-durometry / Mix-Giacomin style approximation.
  URL: https://www.tandfonline.com/doi/abs/10.1080/03602559.2010.531867

- Dow, "Durometer Hardness for Silicones".
  Used for the Dow silicone regression fits: DMA, RDA, secant, LSR secant,
  TPSiV secant, and TPSiV DMA.
  URL: https://www.dow.com/documents/11/11-3716-01-durometer-hardness-for-silicones.pdf?iframe=true

## Local Data Source

- `tyres/database/rf2_tyre_database.sqlite`
  Used for the TGM Gen material-temperature points plotted against the
  approximation curves.

- `tyres/tools/plot_shore_a_correlation.py`
  Reproducible generator for the SVG/HTML plot and formula overlays.
