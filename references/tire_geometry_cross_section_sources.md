# Tire Geometry Cross-Section Sources

Retrieved: 2026-05-26

Purpose: sources for defining a scalar tire cross-section generator that can
produce TGM node coordinates and construction-layer positions.

## Sources

- Alan N. Gent, ed., *The Pneumatic Tire*, DOT HS 810 561, NHTSA, 2006.
  URL: https://www.nhtsa.gov/sites/nhtsa.gov/files/pneumatictire_hs-810-561.pdf
  Used for tire component vocabulary and construction variables: belt width,
  belt crown angle, cap strips/full cap plies, bead filler height/volume, and
  body-ply turn-up height.

- Wikimedia/PICRYL extract from NHTSA *The Pneumatic Tire*,
  "Tire construction variables".
  URL: https://picryl.com/media/tire-construction-variables-nhtsa-the-pneumatic-tire-d146c5
  Used as a compact diagram reference for construction variables affecting
  stiffness and cross-section layout.

- ASTM F1502-05(2016), *Standard Test Method for Static Measurements on Tires
  for Passenger Cars*.
  URL: https://standards.iteh.ai/catalog/standards/astm/1576e0f9-f1ef-482b-b520-11a918e6db3d/astm-f1502-05-2016
  Used for measurement vocabulary: outside diameter, overall width, section
  width, tread radius, single-radius tread contour, dual/drop-shoulder tread
  contour, center-low and center-high oxbow tread profiles.

- Steve L. Walter, *The Effects of Five Basic Design and Construction
  Parameters on Radial Tire Rolling Resistance and Cornering Force*, SAE
  Technical Paper 830160, 1983.
  URL: https://saemobilus.sae.org/papers/effects-five-basic-design-construction-parameters-radial-tire-rolling-resistance-cornering-force-830160
  Used for a professional scalar-parameter set: mold tread radius, tread arc
  width to section width ratio, aspect ratio, belt width to tread arc width
  ratio, and crown angle.

- Yukio Nakajima, *Mechanics of Tire Shape*, Nippon Gomu Kyokaishi, 2019.
  DOI: https://doi.org/10.2324/gomu.92.390
  URL: https://www.jstage.jst.go.jp/article/gomu/92/10/92_390/_article/-char/en
  Used for the high-level split between sidewall shape and crown shape, plus
  sidewall theories: natural equilibrium, non-natural equilibrium, optimized.

- Takashi Akasaka, Kazuyuki Kabe, Hideki Togawa, *Cross-section shape of
  radial tire*, Journal of the Japan Society for Composite Materials, 1977.
  DOI: https://doi.org/10.6089/jscm.3.149
  URL: https://www.jstage.jst.go.jp/article/jscm1975/3/4/3_4_149/_article/-char/ja/
  Used for the concept that radial tire cross-section shape can be derived from
  equilibrium of inextensible radial cords, inflation pressure, breaker/belt
  contact pressure, and constant tread-radius assumptions.

- Youshan Wang et al., *An improved method of using equilibrium profile to
  design radial tires*, Journal of Advanced Mechanical Design, Systems, and
  Manufacturing, 2015.
  DOI: https://doi.org/10.1299/jamdsm.2015jamdsm0018
  URL: https://www.jstage.jst.go.jp/article/jamdsm/9/2/9_2015jamdsm0018/_article/-char/en
  Used for equilibrium-profile design variables and the practical concept of
  using restricted standard dimensions, maximum-width point, belt/carcass
  demarcation point, flat vs curved belt, and belt radius effects.

- Costco Tire Glossary, "Crown radius", "Section width", "Free radius",
  "Flat tread profile".
  URL: https://tires.costco.ca/TireGlossary?lang=en-ca
  Used only as plain-language terminology support.

## Design Implication For Our Generator

The generator should start from standard visible dimensions, then add
construction controls:

- global dimensions: overall diameter, rim diameter, section width, section
  height/aspect ratio, rim width, bead-seat width;
- crown/tread controls: tread arc width, tread chord width, crown/tread radius,
  shoulder radius or dual-radius shoulder drop, crown angle;
- sidewall controls: maximum-section-width position, sidewall bulge amount,
  upper/lower sidewall radius or equilibrium-profile blend;
- bead controls: bead-seat radius, bead toe/heel offsets, bead core diameter,
  bead filler/apex height and width;
- reinforcement controls: belt width, belt radius/curvature, belt edge drop,
  ply turn-up height, chafer extent, cap-strip/full-cap width.

