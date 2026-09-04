# Force Curve Bench fc-3.5 — release notes

Publication date: 2026-09-04

Canonical viewer: <https://buddyog.github.io/topre-force-curves/>

Release tag: `fc-3.5`

## Summary

`fc-3.5` is a presentation and interaction release for Force Curve Bench. It
does not change the frozen raw measurements, retained-run membership,
full-precision mechanical results, 68-dome reference fleet, percentile
algorithm, or `perception-rank-v1` index values.

The release is aligned with *Beyond Snap Ratio* Preprint 2.1. That paper
revision clarifies—without changing any calculation—that Weight Index is the
fleet percentile of full-precision cohort Collapse force and Tactility Index is
the fleet percentile of full-precision cohort force Drop. Correlation
coefficients and the other displayed descriptors are supporting evidence, not
formula weights.

## Consumer changes

- Centers the tool at a stable maximum width in the Domes, Parts, and Tests
  workspaces.
- Keeps all comparison tabs visible. Opening a profile, Force-wall onset, or
  Weight-vs-tactility tab with no selection loads the complete compatible
  fleet; **Clear selection** and **Load all** controls are provided there.
- Gives Domes, Parts, and Tests one collapsed name-and-value filter model and a
  separate collapsible **Tests** list. Active search/filter matches are shown
  as a flat, left-aligned list rather than nested under brand headings.
- Preserves horizontal table position when a Tests column is sorted.
- Gives comparison charts a fixed height independent of fleet size.
- Adds the **Force-wall onset** comparison, including individual specimens,
  assembly-family group context, and the measured Topre production reference.
  It does not substitute recorded turnaround or claim nominal/physical travel.
- Keeps **Weight profile**, **Tactility profile**, and **Weight vs tactility**
  focused on comparison data; their single-selection views do not repeat the
  force-curve measurement strip.

## Force-curve presentation

- Makes **Simplified** the default. It retains Weight Index, Tactility Index,
  detected force-wall onset, Collapse force, and Drop force while removing the
  duplicate lower measurement strip.
- Provides **Detailed** as the complete measurement overlay, with Ramp,
  Pre-collapse work, Snap %, Steepest drop, Drop rate, and recorded turnaround
  restored.
- Provides independent toggles for measurement labels and measurement visuals.
- Keeps the force-curve stroke visually dominant and assigns separate,
  consistent colors to weight-family, tactility-family, and travel-related
  measurements.
- Uses drafting-style construction geometry: a dashed Ramp reference,
  cross-hatched low-opacity Pre-collapse work, a full-thickness Steepest-drop
  segment, orthogonal leaders, and outside arrowheads with visible leader tails
  when a Drop dimension is too tight for internal arrows.
- Moves the measurement details below the graph in Detailed mode and supports
  linked hover emphasis between descriptions and their chart geometry.
- Uses **Steepest drop** as the consumer label for the fixed 0.10 mm-window
  metric, and **Drop force** in the lower details while retaining **DROP** on
  the graph.
- Presents the single-dome Weight Index, Tactility Index, and detected
  force-wall onset in a dedicated header above the plotting area.

## PNG export

PNG export uses the same mode, Simplified/Detailed setting, annotation
visibility, geometry, null handling, and 4.5 mm displacement scale as the
screen. Every export also includes:

- the `UNREAL KEYBOARDS` watermark behind the chart;
- export date and time;
- bench build and frozen data identities; and
- the selected dataset identity in the filename/metadata presentation.

## Scientific and product continuity

The following remain unchanged from the preceding site release:

- frozen raw-source commit
  `6e86ac1955a0c566c7aae521705e51371992ba8a`;
- all 184 raw CSV paths and bytes;
- canonical evidence identity
  `7aa8588b50856816b7fce90dd6e743c26c6f16926071123291cb054352b6cd4a`;
- 76 semantic records, 75 independent measurement cohorts, 184 semantic run
  bindings, and 180 unique acquisitions;
- `metrics-v4.2`, `intake-qc-v1.4`, importer parity to `test-imp 1.1.4`, and
  `perception-rank-v1`; and
- EC Parts Builder `lib-6.1`, including its published root endpoint and
  generated picker bytes.

### Documentation-only pilot correction

The pilot documentation now accurately records that the fixed 5×5 grid held
25 separate, nominally matched OEM Topre assemblies—not one shared housing,
slider, and spring—and describes `observations.csv` as 75 session-by-dome rows
containing 150 numeric ratings. The pilot directory checksum inventory is
resealed for those two prose corrections. No observation, grid mapping,
summary, analysis result, workbook identity, curve metric, or index value
changed.

`SITE_RELEASE_MANIFEST.json` and `SHA256SUMS` are the active combined-site
authority. `FORCE_CURVE_BENCH_RELEASE_MANIFEST_fc-3.5.json` records the
viewer-specific component boundary. `FORCE_CURVE_BENCH_RELEASE_MANIFEST.json`
remains the immutable historical manifest for `fc-3.4`; it is not rewritten to
impersonate the new publication.

## Paper relation

The matching research citation is:

Gebo, Brian. *Beyond Snap Ratio: Reproducible Force–Travel Measurement and
Exploratory Perceptual Correlates of Weight and Collapse Sharpness in
Electrocapacitive Domes*. Version 2.1, 4 September 2026. Zenodo.
<https://doi.org/10.5281/zenodo.22295223>.

Preprint 2.1 is an editorial clarification. It changes no force measurements,
subjective observations, statistical results, figures, index inputs, reference
fleet members, percentile algorithm, or consumer index values.
