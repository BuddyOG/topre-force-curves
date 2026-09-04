# Force Curve Bench measurement and calculation method

This document describes how the Force Curve Bench fc-3.5 release acquires,
checks, calculates, and presents its force-curve results. The fc-3.5 viewer
update does not change the frozen method, evidence, or index calculations
established for fc-3.4. It is a public method
reference, not a research-paper abstract. The method and evidence needed to
interpret or reproduce the released values are intended to stand on their own.

## Method identity

The results documented here are bound to the following frozen authorities:

- Objective repository commit:
  `6e86ac1955a0c566c7aae521705e51371992ba8a`
- Objective Git tree: `e43d25a3fed8c5177467bba96a5abbdd5a3442b0`
- Canonical evidence identity:
  `7aa8588b50856816b7fce90dd6e743c26c6f16926071123291cb054352b6cd4a`
- Metrics method: `metrics-v4.2`
- Intake policy: `intake-qc-v1.4`
- Importer parity target: `test-imp 1.1.4`
- Perception-index method: `perception-rank-v1`

The frozen evidence contains 76 semantic records representing 75 independent
measurement cohorts. It closes over 184 retained raw paths and 180 unique
acquisitions. Four acquisitions are deliberately represented twice: the Topre
HHKB Pro2 and black-slider records are two interpretations of the same physical
tests, not eight independent acquisitions.

The machine-readable `method_config.json`, `intake_policy.json`, retained-run
decision manifest, and full-precision evidence artifacts are authoritative. If
short explanatory prose and those versioned artifacts ever disagree, the
release must be corrected rather than silently choosing one interpretation.

## Plain-language overview

For each run, the bench records a complete press-and-return cycle in 0.005 mm
displacement steps. The intake policy first checks the file, motion, timing,
signal, test speed, and completeness of the cycle. It then checks whether a set
of nominally repeated tests may contain more than one population and whether
the acceptable repeats agree closely enough in collapse force and collapse
position. A released cohort must retain at least two matching runs.

Each retained run is analyzed independently at full precision. When every
retained run has a numeric value for a metric, the released cohort value is the
arithmetic mean of those per-run results. If any retained run is null for that
metric, the canonical cohort value is null rather than a valid-only mean. The
smooth average curve drawn by the viewer is produced separately for
visualization; it is not re-analyzed to obtain released scalar values or event
markers.

## Acquisition record

Every raw CSV is expected to have exactly these five columns, in this order:

```text
Millis,Steps,Travel (mm),Scale raw,Scale (grams)
```

The historical `Scale (grams)` header contains the calibrated force channel.
Published force values use gram-force (`gf`). The acquisition is a complete
out-and-back test:

1. The first occurrence of maximum recorded displacement ends the press.
2. That same sample is included as the first sample of the return branch.
3. The raw logger records one consecutive duplicate of the maximum-displacement
   row at the direction change. This is the only allowed duplicate motion row.

The recorded turnaround is an acquisition boundary. It is not a detected
force-wall position and is not a statement of physical or nominal switch
travel.

## Intake and retained-run selection

`intake-qc-v1.4` is a deterministic engineering intake policy bound to the
accepted `test-imp 1.1.4` implementation by recorded SHA-256 identities. Its
thresholds are data-quality and comparability guardrails. They are not an
instrument-uncertainty budget, a manufacturer tolerance, or a perceptual
threshold.

The frozen operator procedure is published in
[`testing-sop/`](testing-sop/README.md). The accepted Windows executable is
SHA-256
`351607fffe30eb6da8c7612e3e1bdfad0e3a737804e8f109bbd89c8d1a64854e`;
its immutable release ZIP is
`canonical-evidence/authority/test-imp-1.1.4-windows-x64.zip`, SHA-256
`b1ccdaba5c4ec76b7a8516c4e8c8109c26f2cb58b0f60f49a5c5fcf9a031b284`.
Operators must pass the current repository through the executable's supported
`--github-root` option instead of relying on a machine-specific default. The
importer copies retained raw files only. Metadata, evidence-epoch creation,
index versioning, viewer generation, and Git publication are separate
controlled operations.

### 1. File and trajectory integrity

A run must satisfy all of the following:

- the exact five-column header and at least 50 numeric rows;
- no malformed, wrong-width, empty, or non-finite numeric row;
- strictly increasing timestamps;
- press steps of `+0.005 mm` and `+8` motor steps, followed by return steps of
  `-0.005 mm` and `-8` motor steps;
- displacement tolerance of `0.000001 mm`, motor-step tolerance of `0.5`, and
  a consistent ratio of 1,600 motor steps per millimetre;
- no press or return reversal;
- exactly the documented duplicate maximum-displacement row at turnaround;
- a start within `0.15 mm` of the origin, at least `3.5 mm` of press span, at
  least `3.5 mm` of return span, at least 95% return completion, and an ending
  position within `0.15 mm` of the origin.

Ten or more sample intervals longer than three times the run's median interval
are excluding. One through nine such gaps are recorded as advisories.

### 2. Signal integrity

The policy rejects a run for any of these conditions:

- a raw ADC value below `-100000` or calibrated force below `-50 gf`;
- a negative raw ADC or calibrated-force reading outside the unloaded
  return-endpoint zone, or calibrated force below `-2 gf` even in that zone;
- a repeated maximum of at least `500 gf` for five or more samples, treated as
  load-cell saturation;
- at least 12 unchanged adjacent force steps on the press;
- within the mechanical force-shape region, an adjacent press-step change
  strictly greater than `5 gf`; or
- in either press or return, a sample whose local residual from the mean of its
  two neighbors is strictly greater than `5 gf`.

Equality at the `5 gf` discontinuity boundary passes. A small negative zero
offset confined to the unloaded return endpoint is advisory rather than
excluding.

For these discontinuity checks, the mechanical force-shape region begins at
`0.10 mm` and ends at the smaller of `3.4 mm` or detected force-wall onset. If
there is no numeric force-wall onset, the endpoint is `3.4 mm`. The
adjacent-step check is applied to the press branch; the local-residual check is
applied to both press and return. The unloaded return-endpoint zone is on the
post-turnaround return branch at displacement no greater than `0.15 mm`, and it
only excuses a negative reading when calibrated force is at least `-2 gf`.

### 3. Speed and cadence

The policy separates preferred ranges from hard acceptance ranges:

| Check | Preferred | Hard acceptance |
| --- | ---: | ---: |
| Effective full-cycle speed | 0.1445–0.1500 mm/s | 0.1400–0.1530 mm/s |
| Median speed within ±0.10 mm of Collapse | 0.1445–0.1520 mm/s | 0.1400–0.1550 mm/s |
| Median sample interval | 33–35 ms | See cadence tests below |

The effective full-cycle speed is
`2 × (maximum displacement − minimum displacement) / total elapsed time`.
A preferred-range miss is visible as an advisory but does not, by itself,
exclude the run. A speed outside a hard range is excluding.

The following cadence conditions are also hard requirements:

- no sequence of 20 or more consecutive press steps outside
  `0.135–0.160 mm/s`;
- at least 95% of all press intervals within `32–36 ms`;
- at least 98% of intervals in the `0.25 mm` approach to Collapse within
  `32–36 ms`;
- at least 95% of Collapse-to-Valley intervals within `32–36 ms`; and
- no interval in the `0.25 mm` Collapse approach longer than twice the run's
  median interval.

An unavailable required speed or cadence observation also fails closed.

### 4. Landmark and metric validity

An incomplete press, missing Collapse, or missing Valley is a terminal run
failure. A fallback Collapse that did not find the required tactile event is
flagged and is not admitted as a canonical dome Collapse.

Some conditions are deliberately metric-local. For example, a run may be
otherwise acceptable when no force wall is detected, when its
Collapse-to-Valley span is too short for the 0.10 mm steepest-drop metric, or
when RAMP cannot be calculated. Those fields remain null with a named reason;
the missing value is never fabricated.

### 5. Mixed-population stop

Before ordinary replicate filtering, the policy asks whether nominal repeats
contain two supported groups rather than one noisy group. With more than two
eligible runs, each proposed group must contain at least two runs; a singleton
is treated as an outlier, not evidence of a second dome. With exactly two
eligible runs, a sufficiently large one-versus-one split may stop intake.

A supported split triggers a whole-cohort stop when any one of these tests is
met:

- **Collapse force:** the between-group gap is at least
  `max(4 gf, 6% of the overall conventional median)`, and each group's full
  range is no more than `max(2.5 gf, 4% of that group's median)`;
- **Collapse position:** the between-group gap is at least `0.15 mm`, and each
  group's full position range is no more than `0.08 mm`; or
- **Collapse shape:** the Snap difference is at least 10 percentage points and
  the two groups' median normalized drop rates differ by at least 15%.

This is intentionally conservative. It prevents a median filter from merging
two replicate-supported populations and presenting their average as one dome.

### 6. Replicate agreement and minimum count

After individual run acceptance and any explicit path-bound owner decision,
the remaining candidates are centered on their conventional medians. A run
matches the cohort only when both equations are true:

```text
abs(Fc_run - median(Fc)) <= max(1.0 gf, 0.02 * abs(median(Fc)))
abs(xc_run - median(xc)) <= 0.05 mm
```

Here `Fc` is Collapse force and `xc` is Collapse position. Equality passes.
At least two matching runs are required. If fewer than two remain, the entire
cohort is marked for retest and omitted; an acceptable singleton is not
released by itself. A failed cohort does not block unrelated accepted cohorts.

### 7. Advisory RAMP review

RAMP repeatability is reviewed only after all hard gates and retained-run
selection. For a non-mixed cohort with at least three retained finite numeric
RAMP values and a positive finite conventional median, a retained run receives
an advisory when its absolute RAMP deviation is strictly greater than 10% of
that median. Equality passes, with a `1e-12` numerical equality guard.

This warning never changes retention, cohort status, or any metric. Null RAMP
values do not count toward the three-value minimum and do not themselves
receive the warning. A mixed-population stop suppresses this downstream review.

## Force processing and event detection

### Analysis force versus work force

Two force representations have distinct jobs:

- **Analysis force** is a centered seven-sample arithmetic moving mean. At the
  first and last three samples, the window shrinks rather than padding the
  trace. Analysis force supplies Collapse, Valley, RAMP, the Drop family, the
  steepest-drop metric, and force-wall detection.
- **Raw calibrated force** is not smoothed for mechanical-work integration.
  Work uses trapezoidal integration with piecewise-linear endpoint
  interpolation.

Smoothing landmarks but integrating raw force avoids allowing a display or
analysis smoother to redefine the measured work.

### Collapse (`Fc`, `xc`)

Collapse is the selected mechanical collapse peak on the press branch. Within
the first 75% of press samples, the detector searches away from the first and
last seven samples. For candidate index `i`, the clipped local-maximum slice is
`[i - 40, i + 40)`, and the following minimum is searched over `[i, i + 200)`,
with both upper bounds clipped to the 75% search limit. A candidate must be a
maximum of that neighborhood and exceed the following minimum by strictly more
than `2 gf`. The highest qualifying peak is selected; exact ties choose the
earliest sample.

If no qualifying tactile event is found, the detector can identify the first
75%-stroke global maximum only as a flagged fallback. That fallback is not
accepted silently as a canonical dome collapse.

### Valley (`Fv`, `xv`)

Valley is the earliest minimum analysis-force sample after Collapse. The
`valley-v2` calculation begins in a 1.6 mm post-Collapse seed window. It then
detects a possible force wall, re-evaluates the Valley between Collapse and
that wall (or the end of the press if no wall is found), and iterates this pair
for at most four passes. Non-convergence is flagged.

### Detected force-wall onset

Detected force-wall onset is an operational feature of the measured assembly,
not observed physical contact. Starting strictly after Valley, the detector
chooses the earliest analysis-force sample that:

1. is at least `10 gf`; and
2. begins three consecutive 0.005 mm steps on which the force increase is
   strictly greater than 1% of the force at the start of each step.

The calculation requires a conforming 0.005 mm acquisition grid. If the grid
is nonconforming or no sample meets the rule, force-wall onset is null and the
viewer displays **Not detected**. The final press sample is never substituted.

This measurement is an assembly-dependent bottom-out proxy. It is not nominal
dome height, physical switch travel, key actuation travel, or a universal
contact position. The released value is the measured detected onset only.

The canonical JSON field retains the historical name `travel_mm`; its public
meaning in this method is **detected force-wall onset**, not physical travel.

### Recorded turnaround range

For every retained run, the recorded turnaround is its maximum press
displacement. The viewer reports the minimum and maximum of those values for
the cohort, or one value when they are identical. This describes how far the
test was recorded. It remains separate from force-wall onset even when their
coordinates happen to be close.

## Released mechanical descriptors

All formulas below are evaluated per retained run before cohort averaging.
The canonical evidence retains this broader metric set for audit. The
perception-focused viewer's headline card intentionally emphasizes Collapse
force, RAMP, Pre-collapse work, Drop, Steepest 0.10 mm drop, Drop rate, Snap %,
and detected force-wall onset. Supporting fields such as Collapse/Valley
positions, Valley force, Drop travel, and NDR remain available in the evidence
without being promoted as index inputs.

| Descriptor | Exact definition | Unit |
| --- | --- | ---: |
| Collapse force | `Fc`, the analysis force at detected Collapse | gf |
| Collapse position | `xc`, the recorded press coordinate at Collapse | mm |
| Valley force | `Fv`, the analysis force at detected Valley | gf |
| Valley position | `xv`, the recorded press coordinate at Valley | mm |
| Drop | `Fc - Fv` | gf |
| Drop travel | `xv - xc` | mm |
| Drop rate | `(Fc - Fv) / (xv - xc)` | gf/mm |
| Normalized drop rate (NDR) | `(Fc - Fv) / (Fc × (xv - xc))`, equivalently Drop rate divided by `Fc` | 1/mm |
| Snap | `100 × (Fc - Fv) / Fc` | % |
| Pre-collapse work | raw-force integral from the recorded press start to interpolated `xc` | gf·mm |
| Press work to force-wall | raw-force integral from the recorded press start to detected force-wall onset | gf·mm |
| RAMP | baseline-relative 10–90% pre-Collapse rise divided by its interpolated travel span | gf/mm |
| Steepest 0.10 mm drop | maximum force-loss rate over any 0.10 mm interval within `[xc, xv]` | gf/mm |
| Detected force-wall onset | earliest post-Valley coordinate satisfying the sustained 1%-per-step rule | mm |

Drop rate and NDR are defined only when Drop, Drop travel, and Collapse force
are all positive. Snap is defined only for positive Collapse force. Undefined
domains produce nulls with named reasons.

### RAMP technical definition

RAMP excludes the initial seating transient. Let `Fb` be the conventional
median analysis force of samples in the inclusive `0.05–0.15 mm` reference
band. The recorded trace must span that complete band and supply at least three
samples. Collapse must occur after the band, and `Fc` must exceed `Fb` by more
than `1 gf`.

Define the baseline-relative thresholds:

```text
F10 = Fb + 0.10 × (Fc - Fb)
F90 = Fb + 0.90 × (Fc - Fb)
```

Upward crossings are located by piecewise-linear interpolation from `0.05 mm`
through Collapse. The last eligible crossing of each threshold is used. The
crossings must occur in order and be separated by at least `0.02 mm`:

```text
RAMP = 0.80 × (Fc - Fb) / (x90 - x10)
```

If the band, force rise, crossings, ordering, or minimum span is unavailable,
RAMP remains null with the matching named reason. That local null does not
change unrelated metrics.

### Steepest 0.10 mm drop technical definition

For every eligible interval start `q` from Collapse through
`xv - 0.10 mm`, piecewise-linear interpolation evaluates:

```text
rate(q) = [F_analysis(q) - F_analysis(q + 0.10 mm)] / 0.10 mm
```

The released scalar is the exact global maximum. If several audit intervals
are within `1e-12 gf/mm` of that maximum, the earliest interval is recorded for
audit. If Collapse-to-Valley travel is shorter than 0.10 mm, the metric is null;
the method does not shorten or rescale the window.

### Work calculation

Pre-collapse work is trapezoidal integration of raw calibrated force against
recorded press displacement, with piecewise-linear interpolation at Collapse.
The conversion to SI energy is:

```text
1 gf·mm = 9.80665 µJ
```

This is one-way mechanical work on the measured press trace. It is not an
electrical actuation-energy claim.

The canonical evidence also retains the legacy field
`full_stroke_press_work_gf_mm`, labelled **Press work to force-wall**: the
raw-force integral from the press start to the detected force-wall onset. It is
null whenever that wall is unavailable and is not displayed as a weight or
tactility descriptor in the perception-focused viewer. Despite the field's
historical name, it is not work to a known physical or nominal full-travel
position. It remains useful as a separate full-stroke-effort descriptor when a
detected wall exists, especially for questions about presses that continue
past collapse, but it is not an input to either perception index.

## Cohort aggregation, curves, and rounding

The canonical rule is **compute per run, then take the arithmetic mean**. Event
detection and nonlinear metrics are never calculated from an averaged curve.
If any retained run is null for a metric, the canonical cohort aggregate for
that metric is also null with a named flag. A mean of only the non-null runs may
exist as an explicitly labeled exploratory value, but it is not substituted for
the canonical aggregate.

The visualization curve is a separate, lossy display derivative. Samples use
the 0.005 mm bucket key `round(x × 200)` with ECMAScript half-up rounding,
values in each bucket are averaged, at least `ceil(retained runs / 2)`
contributors are required, and the curve is truncated at the smallest
retained-run maximum displacement. Because markers are means of per-run
detections, a scalar marker need not coincide exactly with a visible feature of
the averaged line.

Canonical calculations and index scores retain full precision. Rounding occurs
only when a viewer, table, or export formats a value for presentation. The
authoritative numeric artifacts are `bench_tests.staged.json` for cohort
aggregates and `per_run_full_precision.json` for per-run results; curve packs
are not substitutes for either.

## Pilot-derived perception indices

The indices are consumer-facing percentile rankings derived from objective
mechanical measurements. They do not average several curve metrics together.

### Why these two inputs were selected

The exploratory `subjective-pilot-v1` involved one rater, 25 domes, and three
fixed-order sessions. The fixed 5×5 grid held 25 separate, nominally matched
OEM Topre assemblies; each used an OEM Topre housing, black Topre slider, and
OEM Topre conical spring. Dome identity, fixed position, and unit-to-unit
assembly variation were therefore confounded, and continuity of each
individual housing, slider, and spring across sessions was not separately
recorded. Weight was scored from 1 (feather weight) to 10 (heaviest in the
panel); tactility sharpness was scored from 1 (linear/off) to 10 (sharpest in
the panel). Each dome's arithmetic mean across the three sessions was used.

Collapse force had the strongest observed Spearman rank association with mean
perceived-weight rank (`rho = 0.951744545758805`). Force Drop had the strongest
association with mean tactility-sharpness rank
(`rho = 0.930200072898408`). Spearman rank association supplied the primary
input-selection evidence; Pearson correlations were secondary descriptions.
Neither Spearman nor Pearson coefficients are weights in the index equations,
and neither analysis proves causation.

RAMP and pre-collapse work remain supporting weight descriptors. Steepest
0.10 mm drop, Drop rate, and Snap remain supporting tactility-sharpness
descriptors. Combining these correlated families produced weaker agreement
with the pilot, so they are not combined into the two indices.

The frozen analysis field `rho_weighted_family_composite_spearman_rho` records
a diagnostic association for that rejected candidate family composite. Its
legacy name does not describe either released index formula and it does not
affect any released index value.

Press work to force-wall had the sixth-largest observed Spearman association
with perceived weight among the fourteen screened metrics
(`rho = 0.817380609886974`; 95% BCa interval
`[0.648791394920568, 0.913590454630411]`). Its point estimate was only
`0.0007722` below fifth-ranked Drop rate, so the ordinal rank should not be
read as a practically resolved separation. It is nevertheless excluded from
the Weight Index because the index is the selected single-input collapse-force
percentile, not a weighted combination of the screen. Press work also depends
on an assembly-defined detected wall, is null if no wall is detected, and is
highly redundant in this pilot with collapse force (`rho = 0.900000`) and
pre-collapse work (`rho = 0.943077`). The pilot does not show an independent
contribution that would justify the extra endpoint dependency and model
complexity. The measurement is retained separately for full-stroke-effort
questions rather than discarded.

### Index equations

For dome `i`, let `Ci` be its full-precision cohort Collapse force and let
`Di = Ci - Vi` be its full-precision force Drop. Let `C_fleet` and `D_fleet` be
the corresponding sorted arrays for the 68 release-eligible dome-baseline
measurement cohorts in the frozen reference fleet:

```text
Weight Index_i              = P(Ci; C_fleet)
Tactility-sharpness Index_i = P(Di; D_fleet)
```

There is no correlation multiplier or fitted coefficient in either formula.
Every other mechanical descriptor, including RAMP, pre-collapse work, and
press work to force-wall, does not enter either equation.

`P(x; R)` is the fleet percentile function. For a unique reference value at
zero-based sorted position `k` in the 68-member fleet:

```text
P(x; R) = 100 × k / 67
```

Ties use the average occupied position. A value strictly between two distinct
reference values is linearly interpolated between their percentile positions.
Values below or above the frozen fleet clamp to 0 or 100. A missing or
non-finite input produces no index and is never imputed.

The viewer shortens the customer-facing label to **Tactility Index**. This
method specification retains **Tactility-sharpness Index** to name the measured
perceptual dimension precisely; both labels refer to the same unchanged
force-Drop percentile equation above.

In customer-facing terms:

- **Weight Index** is where the dome's Collapse force ranks among the 68 domes
  tested, from 0 (lightest fleet endpoint) to 100 (heaviest fleet endpoint).
- **Tactility Index** is where its force Drop ranks in the same
  tested fleet, from 0 (least-sharp fleet endpoint) to 100 (sharpest fleet
  endpoint).

These are percentile positions: **80 is not twice 40**. They are not predicted
1–10 ratings or universal perceptual units. A low Tactility Index does
not classify a dome as linear/off. Part-assembly records are outside the
calibrated index population and receive no score. Force-wall onset is separate
and never enters either equation.

## Nulls and unavailable values

Null is a deliberate result, not zero and not permission to substitute another
sample. The viewer uses context-specific language:

- **Not detected** for a force wall that does not meet the detection rule;
- **Not available** for a metric outside its mathematical or evidence domain;
- **Not calibrated** for a perception index outside the 68-dome-baseline
  calibration population.

The null contract applies everywhere the value appears, including cards,
tables, charts, markers, legends, comparisons, overlays, and exported images.
In particular, a recorded turnaround is never substituted for a missing
force-wall onset.

## Evidence and reproducibility

The sealed evidence package records every raw path, byte count, SHA-256, Git
blob OID, retained-run decision, exclusion/retest record, full-precision
per-run result, cohort aggregate, curve-pack provenance hash, and generator
identity. The accepted epoch reports no mixed-population stops, no RAMP-review
requirements, and no canonical membership warnings.

The package verifier uses the Python standard library and fails on missing,
extra, modified, unsafe, inconsistent, stale, or hand-edited evidence. The
viewer may change its layout without changing this frozen measurement method;
any change to calculations, intake thresholds, reference fleet, or source data
requires an explicit new version and regenerated provenance.
