# Dome Lab subjective pilot v1

This is a separate exploratory sidecar. It does not change any canonical Force
Curve Bench metric, curve, retained-run decision, or release eligibility.

## Protocol

- One rater scored 25 domes in three fixed-order sessions.
- The fixed 5×5 grid held 25 separate, nominally matched OEM Topre assemblies;
  each used an OEM Topre housing, black Topre slider, and OEM Topre conical
  spring. Dome identity, fixed position, and unit-to-unit assembly variation
  were confounded, and continuity of each assembly across sessions was not
  separately recorded.
- Weight: 1 = feather weight; 10 = the heaviest dome in this panel.
- Tactility: 1 = linear/off; 10 = the sharpest dome in this panel.
- Physical grid mapping is row-major: 1a–1e, then 2a–2e, through 5a–5e.
- Each dome's three-session arithmetic mean is the analysis value; effective n = 25.

## Interpretation

Perceived-weight ranks were associated most strongly with collapse force and the
ramp/work family. Tactility-sharpness ranks were associated most strongly with
the force-drop/Snap family. These are exploratory associations within the
selected panel. They are not causal contributions, calibrated units, population
norms, or predictions for untested domes.

No tactility score was 1, so this dataset cannot evaluate tactile-event presence
versus linear/off behavior.

## Provenance

- Pilot ID: `subjective-pilot-v1`
- Workbook SHA-256: `d4bbaad6831ccab1003bcc7e2974ef7100ee32e083fa88f27d468e64d7a323d0` (workbook intentionally not included)
- Objective commit: `6e86ac1955a0c566c7aae521705e51371992ba8a`
- Objective evidence identity: `7aa8588b50856816b7fce90dd6e743c26c6f16926071123291cb054352b6cd4a`

See `source_identity.json` for exact source hashes, `grid_mapping.json` for the
explicit orientation, `observations.csv` for all 75 session-by-dome rows (150
numeric ratings: one weight and one tactility score per row),
`dome_summary.csv` for full-precision means, and `analysis.json` for descriptive
statistics and correlations.
