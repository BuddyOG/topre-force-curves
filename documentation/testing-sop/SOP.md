# SOP: test and introduce a new dome

SOP ID: `dome-testing-sop-v1`

Applies to: Force Curve Bench dome acquisitions and dataset additions

Rig: the same existing force-curve rig and acquisition procedure used for the
released fleet

## Purpose

This SOP makes a new dome traceable from physical test through public release.
Passing the importer is the first gate. It is not permission to hand-edit the
viewer or publish the destination folder by itself.

## Roles

**Operator:** identifies the dome, keeps the rig unchanged, collects complete
runs, runs the importer, resolves physical-test issues, and supplies the
correct metadata.

**Repository integrator:** records source and Git identities, reconciles
metadata, records exclusions and retests, creates a new canonical evidence
epoch, versions any changed reference fleet, regenerates the viewer, validates
the release, and publishes only after all gates pass.

One person may perform both roles, but the gates remain separate.

## A. Before testing

1. Use the existing rig exactly as used for the released tests. Do not create
   or label a new assembly for this SOP.
2. Confirm no intentional rig, firmware, logger, calibration, mounting,
   preload, speed, or acquisition-procedure change has occurred. If one has,
   stop. That is a method change, not an ordinary new-dome addition.
3. Write down the dome's proposed public name, manufacturer, variant, nominal
   weight, color, and physical specimen note. Unknown facts must remain
   `Unknown` or null; do not infer them from a folder name.
4. Make a new source folder outside the Git repository. Put only one dome
   specimen/cohort in it. Never mix files from different domes.
5. Place the released `test-imp.exe` and its bundled documentation in that
   source folder, or invoke that exact executable from another location.

## B. Acquire runs

1. Record complete press-and-return CSVs with the established procedure.
2. The acceptance minimum is two retained matching runs. Collecting four
   complete runs is the operating recommendation because failed or
   nonmatching runs can otherwise leave an unusable singleton. Four is a
   recommendation, not an intake-policy threshold.
3. Do not preselect traces by appearance or delete a surprising run before the
   importer sees the complete candidate cohort.
4. Keep the original acquisition folder unchanged until the resulting
   evidence epoch is released and backed up. The importer does not modify it.

## C. Run the importer

1. Verify the executable identity as shown in `IMPORTER_GUIDE.md`.
2. From PowerShell, run:

   ```powershell
   .\test-imp.exe --github-root "D:\Documents\Projects\GitHub\topre-force-curves" "Proposed_Dome_Folder"
   ```

   Replace `Proposed_Dome_Folder` with the exact destination folder name. If
   the repository is elsewhere, replace the path. Always supply
   `--github-root`; do not rely on the importer's older default path.
3. Read every per-file decision and the cohort decision.
4. If the importer reports a failure, mixed population, or fewer than two
   retained runs, do not import or manually copy files. Follow
   `EXCEPTION_CHECKLIST.md`.
5. A preferred-speed note is advisory when all hard gates pass. A hard-speed
   failure excludes the run.
6. A `RAMP REVIEW` warning is advisory only. Inspect the setup and cohort. It
   must not be used by itself to omit a run. If no physical, identity, or
   acquisition error is found, acknowledge the exact phrase requested by the
   importer. If an error may exist, cancel and investigate.
7. Confirm the import only after the cohort is correctly identified and at
   least two runs are retained.

## D. Confirm the importer result

After success, confirm all of the following:

- a new destination folder exists under the stated repository root;
- it contains only importer-retained CSVs, densely named
  `DataLog_1.csv`, `DataLog_2.csv`, and so on;
- at least two CSVs are present;
- the importer reported successful SHA-256 copy verification; and
- the original source folder still exists and is unchanged.

The importer deliberately refuses to overwrite an existing destination. Do
not delete an existing released folder to bypass that protection. A genuinely
new specimen or cohort needs a unique proposed folder name until the
repository integration review decides its permanent identity.

## E. Handoff after a successful import

Complete one row in `new_dome_change_record.csv.template` and provide:

- proposed dome/folder name;
- acquisition date and source-folder location;
- physical specimen note;
- correct metadata and its source;
- importer version and retained count;
- any excluded run, retest, speed note, or RAMP-review note; and
- the destination folder created by the importer.

Then stop. Do not hand-edit `index.html`, generated JSON, curve packs,
metadata registry, index values, release manifests, or checksums.

## F. Controlled repository integration

The repository integrator performs these gates in order:

1. review the clean Git diff and confirm that only intended raw files were
   introduced;
2. preserve every original raw path, byte count, SHA-256, and Git blob OID;
3. update the owner-controlled metadata source with the operator's correct
   values, then regenerate the metadata registry;
4. record all exclusions, retests, replacements, aliases, and specimen
   distinctions in the evidence history;
5. create and freeze the raw source commit;
6. independently reproduce importer decisions and retained membership;
7. create a new evidence epoch with full-precision per-run and cohort results,
   curve packs, provenance hashes, and complete verification;
8. if the reference fleet changes, create a new perception-index model
   version and report every resulting index delta—never silently reuse
   `perception-rank-v1` for a changed fleet;
9. regenerate the Force Curve Bench from the generator, never by editing its
   embedded data manually;
10. run tests, deterministic regeneration, package verification, browser and
    PNG-export acceptance, and release-delta review; and
11. commit, tag, and publish only the reviewed complete release.

## G. Stop conditions

Stop and investigate if any of these is true:

- the rig or method changed;
- files from more than one dome may be present;
- the executable identity does not match the frozen importer;
- the destination already exists;
- fewer than two runs are retained;
- the importer reports a mixed population;
- metadata identity or specimen lineage is uncertain;
- a generated file would need a manual scientific-data edit; or
- a changed fleet has no newly versioned index authority.
