# Dome testing and new-dome intake

SOP ID: `dome-testing-sop-v1`

Status: frozen operating procedure

Importer: `test-imp.exe 1.1.4 (metrics-v4.2; intake-qc-v1.4)`

This package is the operating procedure for testing another collapsing dome,
checking its CSV files, and handing an accepted cohort into the versioned
Force Curve Bench release process. It uses the same force-curve rig and test
procedure used for the released fleet. It does not create a new rig and does
not alter the future multi-rater perception study.

## The short version

The operator does only this:

1. Confirm the existing rig is unchanged and identify the dome.
2. Put only that dome's new `DataLog_*.csv` files beside the released importer.
3. Run the importer with the repository path stated explicitly.
4. Do not override failures, mix domes, or release fewer than two retained
   runs.
5. After a successful import, complete one handoff row and stop. Repository
   integration, evidence regeneration, index versioning, review, and release
   are separate controlled steps.

Start with [SOP.md](SOP.md). Keep [NEW_DOME_CHECKLIST.md](NEW_DOME_CHECKLIST.md)
open while testing. Use [IMPORTER_GUIDE.md](IMPORTER_GUIDE.md) for the exact
command and decision meanings. If anything unusual happens, stop and use
[EXCEPTION_CHECKLIST.md](EXCEPTION_CHECKLIST.md).

## Files in this package

- `SOP.md`: the complete plain-language procedure and responsibility boundary;
- `IMPORTER_GUIDE.md`: exact importer identity, invocation, behavior, and
  interpretation;
- `NEW_DOME_CHECKLIST.md`: one-page operator-to-release gate checklist;
- `EXCEPTION_CHECKLIST.md`: required response to failures and ambiguous cases;
- `new_dome_change_record.csv.template`: one row per proposed dome cohort;
- `FROZEN_SOP_MANIFEST.json`: hashes binding this SOP to its importer, policy,
  method, and release authorities.

## Authority order

For intake calculations, the machine-readable
`generator/domelab_pipeline/config/intake_policy.json` and the hash-identified
`test-imp.exe 1.1.4` release are authoritative. `documentation/METHOD.md`
explains the method. This SOP controls operator actions. If prose and the
machine-readable policy disagree, stop; do not improvise or silently choose
one.
