# RMOD-K open source status

- Source: VDI report PDF hosted by inlibra, "Fahrzeug- und ...", URL:
  https://www.inlibra.com/10.51202/9783181022962.pdf
  Retrieved: 2026-05-25.
  Used for: Statement that RMOD-K 7.0 is a re-development available as open
  source code under https://www.rmod-k.com.
- Source: Ingenieurgesellschaft fuer Automobiltechnik mbH, "tire modeling",
  URL: https://www.iatmbh.com/en/calculation/chassis-tire-calculation/tire-modeling/
  Retrieved: 2026-05-25.
  Used for: Context that IAT and IAT Dynamics provide services around the
  RMOD-K tire model.
- Source: rmod-k.com, "Formula", URL: https://www.rmod-k.com/formula
  Retrieved: 2026-05-25.
  Used for: Statement that RMOD-K Formula is an open source collection of two
  simple tire models plus optimisation tools and simulation interfaces; page
  links to PDF documentation and Windows downloads containing executables,
  source files, and Visual Studio 2013/2017 projects.
  Local copy: `references/rmod-k/RMOD-K-Formula-Documentation.pdf`
  SHA256: `39718B669A307D7EE81B9C7126DC71EE005D5A79FA15E6EAF0D0CA1C1BB89828`

## License inspection

Retrieved and inspected on 2026-05-25:

- https://www.rmod-k.com/images/stories/media/downloads/Formula/RMOD-K-Formula-Documentation.pdf
- https://www.rmod-k.com/images/stories/media/downloads/Formula/Formula-C++VS2013.7z
- https://www.rmod-k.com/images/stories/media/downloads/Formula/Formula-C++VS2017.7z

Findings:

- The Formula web page and PDF describe the package as open source, but do not
  name a license such as GPL, LGPL, MIT, BSD, or Apache.
- No `LICENSE`, `LICENCE`, `COPYING`, `NOTICE`, or `COPYRIGHT` file was found
  in either VS2013 or VS2017 archive.
- Text search in the extracted source packages found copyright notices for
  IAT Dynamics / Ch. Oertel / J. Hempel, but no redistribution, warranty, or
  permission terms.
- The archives include third-party-looking build/tool artifacts such as
  `AStyle.exe` and `glut32.lib`; no bundled license text for these was found in
  the inspected package.

Working conclusion: treat RMOD-K Formula as source-available/open-source in the
plain-language sense claimed by the author, but not as safely reusable under a
standard open-source license until a concrete license grant is obtained or found.

## Model family scope

Retrieved and inspected on 2026-05-25:

- Source: rmod-k.com, "Overview", URL: https://www.rmod-k.com/
  Used for: RMOD-K 7 model family split between RB and FB. The overview states
  that RMOD-K 7 RB targets low/medium-frequency vehicle and road inputs up to
  about 100 Hz, while RMOD-K 7 FB should be used for cleats and other short
  wavelength road disturbances. It also says FB node count represents structure
  mesh density and can be chosen for ride, load-case, or misuse simulations.
- Source: rmod-k.com, "Flexible Belt (FB)", URL:
  https://www.rmod-k.com/flexible-belt-fb
  Used for: FB is described as a C++ reimplementation from version 7.10x,
  using finite-element formulation with adjustable topology, element choices,
  meshing operations, sidewall nodes, preload, belt kinematics, and sidewall
  structure.
- Source: rmod-k.com, "Rigid Belt (RB)", URL:
  https://www.rmod-k.com/rigid-belt-rb
  Used for: RB is described as simplifying the tyre belt into a rigid belt body
  with radius and belt width, including contact between tyre and ground model;
  RMOD-M is mentioned as a small stand-alone MBS system for steady-state and
  sweep-slip tyre behaviour.
- Source: rmod-k.com, "FB Misuse", URL: https://www.rmod-k.com/fb-misuse
  Used for: FB misuse extension includes inner contact between tyre and rim,
  nonlinear unilateral stiffness elements, gap data from cross-section
  information, and large-displacement cleat/pothole cases.
- Source: rmod-k.com, "Measurements", URL: https://www.rmod-k.com/measurements
  Used for: Parameterization data requirements: general dimensions/mass,
  topology/cross-section/belt angle, force and moments, static stiffness, cleat
  measurements, and modal system data.
- Source: rmod-k.com, "Tyre Property Lab - TPL", URL:
  https://www.rmod-k.com/tyre-property-lab
  Used for: The lab page says model parameterization uses FE-model-oriented
  static/dynamic tyre property measurements, including contact pressure
  distribution and a 3D system for determining cross-sectional shape.

Working conclusion: the current project tools cover rFactor 2 TGM/TBC
authoring, parsing, 2D cross-section/layer plotting, tTool preparation, and
tTool result visualization. They do not currently implement RMOD-K Formula,
RMOD-K 7 RB, RMOD-K 7 FB, FB misuse inner-contact logic, RMOD-M, or a true
3D/FE tyre model. The existing "3D" data in TGM node geometry is a 2D
cross-section plus local thickness, not a full spatial mesh.
