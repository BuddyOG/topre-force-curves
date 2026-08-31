# Protocol: blinded multi-rater validation of dome perception indices

Protocol ID: `perception-validation-v1`

Status: frozen pre-enrollment

Design: prospective, repeated-measures, blinded, randomized-order study

The operator-facing implementation of this protocol is frozen in
[`SOP.md`](SOP.md), [`PARTICIPANT_SCRIPT.md`](PARTICIPANT_SCRIPT.md), and
[`EXCEPTION_CHECKLIST.md`](EXCEPTION_CHECKLIST.md). If concise and long-form
wording appears to conflict, stop and amend the package before enrollment.

## Objective

Test whether the frozen `perception-rank-v1` Weight Index and Tactility Index
are positively associated with how multiple people rank the perceived weight
and collapse sharpness of the same 25-dome panel used in
`subjective-pilot-v1`.

The study evaluates association and between-rater consistency. It does not
identify causal contributions of individual curve features, establish a
universal perceptual scale, or evaluate every housing, spring, keycap,
precompression state, or keyboard.

## Panel and apparatus

- Use the 25 physical specimens identified in
  [`../subjective-pilot/grid_mapping.json`](../subjective-pilot/grid_mapping.json).
- For every trial use the same designated Topre housing, Topre slider,
  conical spring, keycap, mounting fixture, and operator procedure.
- Do not introduce precompression or alternate assembly conditions.
- Assign one unique opaque code to each physical specimen. Codes must not
  reveal brand, nominal weight, position, test ID, force measurement, or index.
- Inspect the assembly before each session. Record substitutions, damage,
  seating problems, or other deviations.

If the exact physical pilot specimens no longer exist or cannot be identified,
stop and amend the protocol before enrollment. A replacement panel is a new
panel and must not be described as direct validation on the same specimens.

## Participants

- Target: 24 completed adult raters.
- Minimum for confirmatory interpretation: 20 completed raters.
- If fewer than 20 complete both scored sessions, label every result
  exploratory.
- Recruit without selecting people based on expected agreement with the pilot.
- Record experience only in broad, nonidentifying categories specified in the
  data dictionary.

No power claim is made solely from this pragmatic target. Any formal power
analysis added later must be simulated and frozen before enrollment.

## Blinding

Participants may not see specimen names, nominal weights, force curves,
mechanical metrics, prior ratings, indices, or the code key. The analyst should
receive a ratings table containing opaque specimen codes and the frozen
analysis script before receiving the key that maps codes to test IDs.

The operator should use neutral language and must not react to a rating or
suggest that a specimen is expected to be heavy, light, sharp, or smooth.

## Sessions

Each participant completes:

1. **Orientation and practice:** read the two scale definitions; test every
   dome once in a separately randomized order; scores may be entered for
   practice but are not analyzed.
2. **Scored session 1:** rate all 25 domes once in the generated order.
3. **Scored session 2:** rate all 25 domes once in a new generated order,
   preferably at least 24 hours after session 1.

If separation by 24 hours is impossible, record the exact interval. Do not
quietly merge both sessions into one sitting.

## Participant instructions

Read this text verbatim:

> You will compare 25 electrocapacitive keyboard domes. Use the whole panel as
> your reference. Weight is 1 for feather-lightest in this panel and 10 for
> heaviest in this panel. Tactility sharpness is 1 for linear or no distinct
> collapse and 10 for the sharpest collapse in this panel. These are separate
> judgments: a dome can be heavy without being sharp, or sharp without being
> heavy. Use whole numbers from 1 through 10. There are no right answers. Do
> not try to identify the product.

The participant may press each presented dome up to five times before rating.
They may not return to a prior dome after advancing. Offer a short neutral
break after trials 8 and 16; record any additional break.

## Operator workflow for every scored trial

1. Confirm participant ID, session number, trial order, and blinded code from
   the generated schedule.
2. Seat the coded specimen in the standardized assembly using the same
   documented method.
3. Present the assembly without identifying information.
4. Permit up to five presses.
5. Record one integer Weight rating and one integer Tactility-sharpness rating.
6. Record missingness or a protocol deviation immediately; never invent a
   score later.
7. Remove the specimen, inspect the assembly, and continue in schedule order.

An exposed scored trial is never repeated. More than five presses is invalid
with reason `press_limit_exceeded`; an out-of-order exposure is invalid with
reason `order_error`. Corrections made before participant exposure do not
constitute a trial.

## Environmental and procedural record

For each session record date/time, operator code, apparatus ID, approximate
room temperature, time since the prior scored session, interruptions, and any
equipment or assembly deviation. Use one procedure throughout the study.

## Allowed exclusions

A rating may be excluded only for a reason defined before unblinding:

- no rating was provided;
- the wrong coded specimen was presented;
- specimen identity or bench information was revealed before the rating;
- an equipment, seating, or assembly fault invalidated the trial; or
- the participant withdrew the observation.

A participant is confirmatory-complete only with both scored sessions and at
least 23 valid trials per session. Invalid trials are not replaced with means.
Sensitivity analyses may include otherwise usable partial data. Do not exclude
a person or score merely because it disagrees with the pilot, index, group, or
their own other session.

## Change control

After enrollment begins, record every departure as a dated amendment. Do not
change endpoints, exclusions, hypotheses, or primary statistics after viewing
outcomes. If an index is refit, report it as a new exploratory model version;
never silently replace `perception-rank-v1`.
