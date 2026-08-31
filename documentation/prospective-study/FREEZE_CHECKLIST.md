# Protocol freeze and study-readiness checklist

Protocol ID: `perception-validation-v1`  
Repository freeze date: 2026-08-31

The protocol can be frozen before the physical study is ready. **Do not enroll
participant 1 until every operator-readiness box in section B is complete.**

## A. Repository freeze

- [x] Protocol and analysis plan identify the same protocol version.
- [x] Operator SOP and participant script are included.
- [x] Outcomes, hypotheses, minimum completed-participant threshold, and
  exclusion rules are declared.
- [x] Data dictionary and collection templates are included.
- [x] Schedule generator separates the public order seed from the private code
  key.
- [x] Frozen-file hashes are recorded in `FROZEN_PROTOCOL_MANIFEST.json`.
- [x] Git tag is declared as `perception-validation-v1`.
- [x] No participant outcome was used to choose these rules.

## B. Operator readiness — complete before participant 1

- [ ] I physically located all 25 exact pilot specimens.
- [ ] I confirmed every specimen against the grid mapping and assigned its
  physical specimen ID in the private code key.
- [ ] I labeled the standard components `PV1-H1`, `PV1-S1`, `PV1-CS1`,
  `PV1-K1`, and `PV1-M1`, and recorded complete assembly `PV1-A1`.
- [ ] I confirmed that no precompression or alternate component is present.
- [ ] I generated the private code key outside the repository and backed it up
  separately from participant-facing records.
- [ ] I generated and checked all participant/session schedules.
- [ ] I prepared the lawful consent/privacy process for the intended
  participants and publication.
- [ ] I completed one full dry run with a non-study volunteer.
- [ ] The dry run used practice plus a scored-session simulation, all 25
  domes, the five-press limit, and breaks after trials 8 and 16.
- [ ] I can follow the participant script without adding product hints.
- [ ] I can record an invalid trial using the exception checklist without
  repeating it.
- [ ] My controlled study folder and backup location are ready and contain no
  participant names in analysis files.
- [ ] Any dry-run correction was documented as an amendment and, if it changed
  the protocol, frozen under a new version before enrollment.

Operator name or code: __________  Date completed: __________  
Signature or equivalent readiness acknowledgment: __________________________

## C. Start decision

- [ ] Every section B box is complete.
- [ ] No unresolved amendment exists.
- [ ] The current protocol tag and manifest match the printed SOP.

Only after section C is complete may recruitment or scored data collection
begin.
