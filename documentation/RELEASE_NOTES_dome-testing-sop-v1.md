# Dome testing SOP v1 — freeze notes

Freeze date: 2026-08-31

Git tag: `dome-testing-sop-v1`

Importer: `test-imp.exe 1.1.4 (metrics-v4.2; intake-qc-v1.4)`

This documentation release freezes the operating procedure for acquiring and
introducing new dome cohorts into the Force Curve Bench dataset.

## What is frozen

- continued use of the same existing force-curve rig and acquisition method;
- exact importer executable and release-package identities;
- an explicit `--github-root` command that avoids the obsolete bundled default
  path on the current workstation;
- one-dome-per-source-folder handling;
- importer-controlled individual gates, mixed-population stop, replicate
  filtering, minimum two retained runs, and advisory-only RAMP review;
- preservation of original acquisitions, exclusions, retests, metadata source,
  and specimen lineage;
- a hard boundary between importer success and repository/public release;
- mandatory new evidence epoch and generator-produced viewer; and
- mandatory model versioning and delta reporting when the reference fleet
  changes.

## Scientific and product continuity

This SOP release adds no dome, removes no run, changes no retained membership,
changes no metric or index formula, and changes no Force Curve Bench or EC
Parts Builder runtime byte. It documents how the next acquisition must enter a
future release without weakening the existing evidence chain.

The signed importer ZIP remains unchanged. Its embedded default repository
path is not current for this workstation, so the repository-side guide requires
the supported `--github-root` argument instead of mutating and re-signing the
authority package.
