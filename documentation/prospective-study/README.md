# Prospective multi-rater perception study

Status: protocol package prepared; recruitment and data collection not started.  
Protocol version: `perception-validation-v1-draft`  
Prepared: 2026-08-31

This package is the next research step after `subjective-pilot-v1`. It tests
whether the already frozen Weight Index and Tactility Index track ratings from
multiple blinded raters. It does not refit the indices and does not turn the
pilot into confirmatory evidence after the fact.

## Study in plain language

Each participant tests the same 25 domes used in the pilot, assembled in the
same Topre slider, housing, and conical spring. Dome identity and bench values
are hidden. The order changes for every participant and session. Participants
give exactly two ratings:

- **Weight:** 1 = feather-lightest in this panel; 10 = heaviest in this panel.
- **Tactility sharpness:** 1 = linear/off; 10 = sharpest in this panel.

There is one practice pass and two scored sessions. The planned target is 24
completed adult participants, with 20 as the minimum for confirmatory
interpretation. Below 20, the result is reported as exploratory.

## Before the first participant

1. Read and freeze [`PROTOCOL.md`](PROTOCOL.md) and
   [`ANALYSIS_PLAN.md`](ANALYSIS_PLAN.md). Replace `draft` in the version only
   after every choice is final.
2. Archive that frozen version with a date and immutable identifier before
   enrollment. A Git tag plus an external timestamped archive is preferred.
3. Assign opaque codes with [`blinded_code_key.csv.template`](blinded_code_key.csv.template).
   Keep the completed key away from participants and the person doing the
   blinded analysis.
4. Generate randomized orders with [`generate_schedules.py`](generate_schedules.py).
5. Pilot the instructions and physical workflow with a non-study volunteer.
   Fix operational ambiguity before enrollment, record the change, and freeze
   again. Do not tune the protocol after looking at study outcomes.
6. Use an appropriate consent and privacy process for the jurisdiction and
   intended publication. Do not commit names, email addresses, signatures, or
   other direct identifiers to this repository.

## Files

- [`PROTOCOL.md`](PROTOCOL.md) — exact participant and operator workflow.
- [`ANALYSIS_PLAN.md`](ANALYSIS_PLAN.md) — hypotheses, exclusions, and frozen
  primary/secondary analyses.
- [`DATA_DICTIONARY.md`](DATA_DICTIONARY.md) — every collected field.
- [`participant_ratings.csv.template`](participant_ratings.csv.template) —
  one row per scored trial.
- [`operator_schedule.csv.template`](operator_schedule.csv.template) —
  internal identity-bearing schedule format.
- [`blinded_code_key.csv.template`](blinded_code_key.csv.template) — private
  specimen-to-code key format.
- [`generate_schedules.py`](generate_schedules.py) — deterministic order
  generator for the same 25 pilot domes.

## Schedule-generation example

Run from the repository root:

```text
python documentation/prospective-study/generate_schedules.py \
  --participants 24 \
  --seed 20260831 \
  --code-key private-study-records/blinded_code_key.csv \
  --output study-schedules
```

If the code-key path does not exist, the script securely creates it once. Keep
that file outside the repository and reuse the same path for every generation.
The public seed reproduces presentation order but cannot reconstruct the
private specimen mapping. The output directory contains an internal operator
schedule and a participant schedule without specimen identities. The command
refuses to overwrite an existing output directory. Treat the completed code
key and unredacted operator file as controlled research records, not public
repo content.

## What completion means

This package is complete when its protocol is frozen and archived. The study
is complete only after enrollment, both scored sessions, declared quality
control, blinded analysis, code-key release, and a versioned result report.
Until then, public claims remain the exploratory claims in Preprint 2.0.
