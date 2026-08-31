# New-dome checklist

Use one copy for each proposed dome cohort.

## Operator

- [ ] I used the same unchanged force-curve rig and procedure.
- [ ] I identified one physical dome/cohort and recorded its correct metadata.
- [ ] My source folder is outside Git and contains no other dome's CSVs.
- [ ] I kept every complete candidate run for importer review.
- [ ] `test-imp.exe --version` reports 1.1.4 / metrics-v4.2 / intake-qc-v1.4.
- [ ] The executable SHA-256 matches `IMPORTER_GUIDE.md`.
- [ ] I ran the importer with the current repository supplied through
  `--github-root`.
- [ ] The importer retained at least two matching runs.
- [ ] There is no unresolved mixed-population, hard failure, identity problem,
  or physical-test concern.
- [ ] I preserved every advisory, exclusion, and retest in the handoff record.
- [ ] The new repository destination exists and its copied files passed SHA-256
  verification.
- [ ] I kept the original acquisition folder unchanged.
- [ ] I completed `new_dome_change_record.csv.template` and stopped before
  changing generated data or publishing.

## Repository integrator

- [ ] The working tree and intended raw-data diff were reviewed.
- [ ] Raw paths, bytes, SHA-256 values, Git blob OIDs, and acquisition identity
  were recorded.
- [ ] Correct owner-supplied metadata was incorporated and reconciled.
- [ ] Exclusions, retests, replacements, and aliases were recorded explicitly.
- [ ] The raw source commit was frozen.
- [ ] Importer parity and retained membership were independently verified.
- [ ] A new canonical evidence epoch was built and sealed deterministically.
- [ ] Per-run, aggregate, curve-pack, and provenance artifacts were regenerated.
- [ ] A changed reference fleet received a new perception-index model identity
  and a score-delta report.
- [ ] The viewer was generator-produced, not hand-edited.
- [ ] Tests, package verification, browser/PNG acceptance, and release-delta
  review passed.
- [ ] The complete reviewed release—not merely the imported folder—was
  committed, tagged, and published.
