# Prospective analysis plan

Status: freeze before enrollment with the matching protocol version.

## Frozen predictors and outcomes

The predictors are the released, full-precision `perception-rank-v1` values
for each matched `test_id`:

- Weight Index: fleet percentile of collapse force.
- Tactility Index: fleet percentile of force drop.

The primary outcomes are each participant's integer 1–10 Weight and Tactility-
sharpness ratings. Average the two valid scored sessions within each
participant and dome before the primary rank analysis. Do not use the practice
pass.

## Primary hypotheses

1. Within participants, Weight Index has a positive Spearman rank association
   with perceived-weight ratings.
2. Within participants, Tactility Index has a positive Spearman rank
   association with perceived tactility-sharpness ratings.

These are two distinct primary hypotheses. Report both effect estimates,
two-sided 95% confidence intervals, and exact participant counts. Control the
two primary tests with Holm's procedure at familywise alpha 0.05.

## Primary estimands and inference

For each completed participant, calculate Spearman's rho across the 25 domes
for the relevant index and averaged rating. Summarize the participant-level
rho values by their median and mean Fisher-z transform. Obtain the primary 95%
confidence interval by bootstrapping participants, not individual rating rows,
with a frozen random seed and at least 10,000 resamples.

Also report every participant-level rho in a deidentified supplement. Ties are
expected on the 1–10 rating scale and must use the analysis library's standard
midrank treatment.

## Secondary analyses

- Session-repeatability: Spearman correlation and weighted agreement between
  sessions within participant for each outcome.
- Rater agreement: rank-based intraclass or ordinal agreement summary with its
  definition stated before calculation.
- Mixed-effects ordinal regression with rating as outcome, frozen index as a
  fixed effect, and participant and dome random intercepts where estimable.
- Direct mechanical comparison: collapse force versus Weight ratings, and
  force drop versus Tactility ratings. This checks the transparent basis of
  each percentile without treating the percentile as interval-scaled.
- Order/fatigue check using trial order and session as prespecified covariates.
- Sensitivity analyses including partial participants and excluding documented
  invalid trials under the protocol rules.

Secondary results are supportive and clearly labeled. Avoid interpreting
correlated curve descriptors as isolated causal contributions.

## Missing data and exclusions

Apply only the prospective protocol's declared invalidity rules. Report a flow
table from recruited through analyzed participants and a reason for every
excluded trial or participant. Never convert missing ratings to zero and never
drop a statistically inconvenient score as an outlier.

## Blinded analysis sequence

1. Lock the raw ratings file and calculate its SHA-256 digest.
2. Validate ranges, uniqueness, schedules, and declared exclusions while
   specimen identities remain opaque.
3. Run the frozen analysis code against a blinded predictor table or shuffled
   mock mapping to verify output structure.
4. Lock the code and analysis choices.
5. Release the code key, join to exact `test_id` values, and run once.
6. Preserve raw input, code, environment, logs, tables, figures, and hashes.

## Interpretation rules

- At least 20 protocol-complete participants are required for confirmatory
  language under this plan.
- A positive association supports criterion-related validity within this
  panel and assembly. It does not create universal perceptual units.
- A weak or heterogeneous association is a result, not a reason to redefine
  an endpoint after unblinding.
- Any revised predictor is exploratory and receives a new model name,
  reference population, formula, and provenance record.
