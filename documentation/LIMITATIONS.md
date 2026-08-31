# Force Curve Bench limitations and interpretation boundaries

Force Curve Bench provides reproducible mechanical comparisons within one
versioned test system. Its results are useful when read inside that scope. This
document states what the released measurements and pilot-derived indices do
not establish.

## Read the values as comparative bench measurements

The displayed values describe the tested specimen or assembly under the frozen
acquisition and calculation method. They do not establish:

- a manufacturer's nominal rating;
- a universal property that is independent of housing, slider, spring,
  precompression, mounting, condition, age, temperature, or other assembly
  details;
- performance in every keyboard or under a person's natural keypress speed;
- product quality, durability, comfort, preference, or suitability; or
- an electrical actuation point or electrical switching behavior.

Differences between records are measurements from this bench and protocol.
They should not be generalized beyond that setting without additional testing.

## No published instrument-uncertainty claim

The intake policy checks acquisition integrity and consistency, but its
thresholds are not a measurement-uncertainty budget. This release does not
claim that `1 gf`, `2%`, `0.05 mm`, a displayed decimal place, or any other
intake threshold represents the instrument's accuracy or confidence interval.

The release also does not provide a multi-bench, multi-operator, environmental,
or calibration-traceability study. Display precision therefore must not be read
as a guarantee of physical accuracy to the last shown digit.

## Operational landmarks are method-defined

Collapse, Valley, RAMP, and detected force-wall onset are deterministic
features identified by the published algorithms. They make records comparable
under one method, but they are not direct observations of microscopic material
events.

In particular, detected force-wall onset is a sustained force-rise feature of
the complete measured assembly. Physical contact is not observed. The value is
not nominal dome height, physical or full switch travel, key actuation travel,
or a universal bottom-out coordinate. A shorter or longer force-wall value is
not inherently better or worse.

Recorded turnaround is only the maximum displacement captured by the test. It
does not become force-wall onset when no wall is detected and must never be
presented as physical travel.

## Intake thresholds are engineering guardrails

The hard speed, cadence, integrity, mixed-population, and replicate-agreement
rules are provisional engineering rules for admitting comparable data. They
are not manufacturer specifications, perceptual just-noticeable differences,
or proof that two specimens inside a tolerance are physically identical.

Conversely, an excluded run is not proof that the physical dome is defective.
It means the acquisition or replicate set did not satisfy this release's data
policy. A whole cohort can be withheld when fewer than two runs agree or when
the conservative split detector finds evidence compatible with two supported
populations.

The RAMP repeatability notice has a narrower meaning: it is a nonfatal prompt
to inspect a retained run that differs by more than 10% from a qualifying
retained-run median. It neither rejects the run nor alters a value. Absence of
that notice is not a statistical guarantee of RAMP repeatability.

## Small replicate counts limit statistical claims

A released cohort retains at least two matching runs, but replicate counts are
not uniform and are often small. Arithmetic means summarize retained runs;
they do not by themselves supply confidence intervals, population variance,
between-specimen variance, or long-term repeatability.

Repeated runs from one specimen or assembly are not independent samples of all
domes sold under the same name. The viewer therefore describes the tested
record, not an entire production population.

## Metrics are related, not isolated causal contributions

Several displayed descriptors share the same Collapse and Valley landmarks
and are mathematically or physically correlated. For example, Drop, Drop rate,
normalized drop rate, Snap, and steepest 0.10 mm drop all describe the same
post-Collapse region in different ways. Collapse force, RAMP, and pre-collapse
work also overlap in their description of the force buildup.

The subjective pilot's rank associations do not isolate how much each variable
causes perceived weight or tactility. They do not prove that changing one
descriptor while holding every other property fixed would change perception by
a corresponding amount.

## The perception pilot is exploratory

`subjective-pilot-v1` has important limits:

- one rater;
- 25 selected domes;
- three sessions in the same fixed order;
- 75 session-by-dome observation rows, each containing one weight and one
  tactility score (150 numeric scores total);
- one standardized Topre housing, slider, and conical spring;
- relative 1–10 anchors defined by that 25-dome panel;
- no independent validation panel; and
- no tactility score of 1, so the pilot contains no observed linear/off case.

The fixed sequence can carry order, learning, memory, or fatigue effects. One
rater cannot establish agreement among users. The standardized assembly helps
hold that pilot setup constant, but it does not test other housings, sliders,
springs, precompression states, or complete keyboards.

The reported Spearman correlations are exploratory associations within this
panel. They are not causal estimates, population parameters, or evidence that
the mechanical variables predict every person's perception.

## Weight and Tactility-sharpness Indices are fleet percentiles

The two indices rank objective values within a frozen reference population of
68 release-eligible dome-baseline measurement cohorts:

- Weight Index is the Collapse-force percentile compared with the other domes
  tested.
- Tactility-sharpness Index is the force-Drop percentile compared with the
  other domes tested.

They are not converted versions of the pilot's 1–10 ratings. The full
calculation and interpretation are specified in
[`METHOD.md`](METHOD.md#pilot-derived-perception-indices).

Zero and 100 are the lightest/heaviest or least/most-sharp endpoints in this
tested fleet, not universal physical endpoints. The 68 cohorts are not claimed
to be a statistically representative sample of all electrocapacitive domes.
Results outside their range clamp to the fleet endpoints rather than extending
the scale.

A low Tactility-sharpness Index does not mean linear or tactile-event absent;
the pilot did not observe a linear/off rating. Part-assembly experiments are
outside the index's calibrated population and correctly display **Not
calibrated**.

The reference arrays and formulas are frozen as `perception-rank-v1`. A future
expanded fleet must receive a new version and provenance rather than silently
moving the present scores.

## Missing values are not zeros

The pipeline fails closed for unavailable events and mathematical domains. A
null can mean that an event was not detected by the declared rule, that the
acquisition grid does not support a calculation, that a required interval is
too short, or that an index is outside its calibrated population.

Accordingly:

- **Not detected** does not prove that an assembly has no physical bottom-out;
  it means no force wall met this method's detection rule.
- **Not available** is not zero and must not be included as zero in a mean.
- **Not calibrated** is not a low score; it means the index does not apply.

If any retained run is null for a metric, the canonical cohort aggregate is
also null. The system does not silently average only the convenient runs or
replace a missing event with the last recorded sample.

## The drawn average curve is illustrative

Scalar values and markers are calculated per run and then averaged. The line
drawn in the viewer is separately averaged in 0.005 mm buckets for visual
comparison. It is not re-analyzed. A mean marker therefore may not sit exactly
on the corresponding-looking feature of the mean line, especially when event
positions differ across retained runs.

Curve packs are rounded, lossy display derivatives. They should not be used to
reconstruct or audit full-precision scalar results when
`bench_tests.staged.json`, `per_run_full_precision.json`, and the retained raw
files are available.

## Evidence counts require care

The frozen epoch has 76 semantic records, 75 independent measurement cohorts,
184 raw paths, and 180 unique acquisitions. The difference is intentional:
four physical acquisitions support two semantic interpretations, Topre HHKB
Pro2 and Topre black slider. Those aliases must not be counted as independent
physical evidence in a statistical analysis.

The metadata workbook is authoritative for 65 included records. Eleven other
records retain explicit predecessor lineage, and excluded workbook rows remain
part of the evidence history rather than receiving invented values.

## Version boundary

These limitations travel with the method and evidence identities printed by
the viewer. GUI changes may improve presentation without changing the data.
Changes to raw acquisitions, retained membership, metric formulas, thresholds,
aggregation, the 68-member reference arrays, or the pilot-derived model require
an explicit new version, regenerated artifacts, and new provenance checks.

Beyond Snap Ratio Preprint 2.0 adds context and exploratory analysis but does
not override these boundaries. It cites the released identities and does not
silently redefine the values documented here. The planned prospective study is
specified in [`prospective-study/`](prospective-study/README.md); until that
study is completed, no confirmatory multi-rater perception claim exists.
