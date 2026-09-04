# Prospective multi-rater perception study

Status: frozen pre-enrollment; recruitment and data collection not started.

Protocol version: `perception-validation-v1`

Frozen: 2026-08-31

Git tag: `perception-validation-v1`

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

## What to do before the first participant

1. Start with [`SOP.md`](SOP.md). It is the plain-language procedure to follow
   while running each participant.
2. Complete every unchecked operator-readiness item in
   [`FREEZE_CHECKLIST.md`](FREEZE_CHECKLIST.md). The repository is frozen, but
   the study must not start until that physical-readiness section is complete.
3. Assign opaque codes with [`blinded_code_key.csv.template`](blinded_code_key.csv.template).
   Keep the completed key away from participants and the person doing the
   blinded analysis.
4. Generate randomized orders with [`generate_schedules.py`](generate_schedules.py).
5. Pilot the instructions and physical workflow with a non-study volunteer.
   If the dry run requires a substantive change, record it in
   [`AMENDMENT_LOG.md`](AMENDMENT_LOG.md), create a new version, and freeze it
   before enrollment. Do not tune the protocol after looking at outcomes.
6. Use an appropriate consent and privacy process for the jurisdiction and
   intended publication. Do not commit names, email addresses, signatures, or
   other direct identifiers to this repository.

## Files

- [`SOP.md`](SOP.md) — the exact, plain-language operator procedure.
- [`PARTICIPANT_SCRIPT.md`](PARTICIPANT_SCRIPT.md) — words to read aloud
  without adding hints.
- [`SESSION_RECORDING_SHEET.md`](SESSION_RECORDING_SHEET.md) — simple paper
  fallback and verification sheet.
- [`EXCEPTION_CHECKLIST.md`](EXCEPTION_CHECKLIST.md) — what to do when
  something goes wrong and the only allowed invalidity codes.
- [`FREEZE_CHECKLIST.md`](FREEZE_CHECKLIST.md) — completed repository freeze
  plus the physical-readiness gate that must precede participant 1.
- [`AMENDMENT_LOG.md`](AMENDMENT_LOG.md) — change-control rules and amendment
  template.
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
- [`apparatus_record.csv.template`](apparatus_record.csv.template) — the six
  physical setup labels to complete once before the dry run.
- [`generate_schedules.py`](generate_schedules.py) — deterministic order
  generator for the same 25 pilot domes.
- [`FROZEN_PROTOCOL_MANIFEST.json`](FROZEN_PROTOCOL_MANIFEST.json) — exact
  hashes of the frozen protocol package and its external dependencies.

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
private specimen mapping. The output directory contains a separate practice
schedule, an internal scored-trial operator schedule, and a participant-facing
scored schedule without specimen identities. The command refuses to overwrite
an existing output directory. Treat the completed code key and unredacted
operator file as controlled research records, not public repo content.

## What completion means

The repository protocol is frozen and archived under tag
`perception-validation-v1`. The physical study is ready only after every
operator-readiness box is complete. The study itself is complete only after
enrollment, both scored sessions, declared quality control, blinded analysis,
code-key release, and a versioned result report. Until then, public claims
remain the exploratory claims in Preprint 2.1.
