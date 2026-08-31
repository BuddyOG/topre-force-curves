# Updating the Force Curve Bench dataset

Force Curve Bench releases are tied to immutable Git commits and evidence
identities. Adding, removing, replacing, or renaming raw tests is therefore a
new versioned dataset operation—not a live edit to an existing release.

The released viewer never discovers folders from a moving branch. Its
selectable records, retained runs, scalar measurements, and fallback traces are
generated together from a frozen commit.

## Deployment files versus evidence files

The fc-3.4 repository update preserves all 184 raw CSV files byte for byte at
their existing relative paths. It also preserves three legacy HTML endpoints
for URL continuity, without claiming that those pages were revalidated as part
of fc-3.4. Replacing the root `index.html` and `README.md` with the fc-3.4
viewer and overview is a
publication-surface change; it is not a raw-data change.

The current published tree combines Force Curve Bench `fc-3.4` with EC Parts
Builder `lib-6.0`. The builder replaces `dome-lab-parts.html` through an
explicit, versioned overlay policy. That overlay protects
every predecessor endpoint other than the declared builder replacement, all
raw CSVs, and the canonical evidence tree against incidental change.

The release-root `.gitattributes` must contain exactly `* -text` so Git does
not normalize line endings or otherwise apply text conversion to inventoried
files. This is byte-preservation infrastructure for publication checkouts, not
source evidence and not a substitute for the evidence manifest or hashes.
The release root also carries an exactly empty `.nojekyll` so GitHub Pages does
not apply Jekyll filtering to underscore-prefixed paths. Preserve both
infrastructure files in future publication trees unless the hosting contract is
explicitly changed.

Any future packager or deployment must not delete, move, or overwrite raw CSVs as
an incidental consequence of updating the viewer. Any intended raw-path or
raw-byte change must follow the evidence-epoch workflow below. Retirement or
replacement of a legacy HTML endpoint should likewise be an explicit URL-policy
decision, not an accidental side effect of copying a release tree.

## Required workflow

1. **Record the new acquisition honestly.** Add each new raw CSV as a complete
   press-and-return acquisition. A retest is a new acquisition even if it
   replaces the practical role of a rejected run.
2. **Run the declared importer.** Evaluate the complete candidate cohort with
   the versioned intake authority by following the frozen
   [dome-testing SOP](testing-sop/README.md). For the current Windows importer,
   supply the repository explicitly with `--github-root`; do not rely on its
   older default path. Record every accepted, excluded, mixed,
   insufficient-replicate, and advisory result. Do not select runs by visual
   preference. The old `bench-import.py` / `importer_core.py` path is retired.
3. **Require a valid retained cohort.** The active policy must retain at least
   two runs that pass the individual gates and the collapse-force and
   collapse-position replicate bands. A cohort that does not meet the minimum
   is withheld for retest.
4. **Update metadata from its authority.** Correct names, manufacturers,
   variants, nominal values, and tested status in the owner-controlled metadata
   source and regenerate the metadata registry. Folder names are not a
   substitute for authoritative metadata.
5. **Preserve exclusions and retest history.** Record why an earlier run or
   cohort was excluded and which acquisition replaced it. Git history preserves
   old bytes, but the evidence ledger must also make the relationship explicit.
6. **Freeze the source commit.** Build the new raw-path inventory with byte
   counts, SHA-256 values, Git blob OIDs, acquisition identities, semantic
   bindings, and shared-evidence aliases.
7. **Create a new evidence epoch.** Regenerate retained membership,
   full-precision per-run and cohort results, curve packs, and provenance. Run
   the symmetric package verifier and importer-parity audit.
8. **Version any changed model.** If the calibrated dome reference population
   changes, do not silently move existing Weight or Tactility-sharpness Index
   ranks. Freeze and identify the new reference arrays under a new perception
   model version, then report the score delta.
9. **Regenerate the viewer.** Generated record scalars, retained-run lists,
   embedded traces, build identity, and documentation must come from the new
   epoch. Do not hand-edit generated measurements in `index.html`.
10. **Review and release the delta.** Publish the changed paths, retained-run
    changes, metric/index changes, evidence identity, tests, browser acceptance,
    and release hashes before replacing the public viewer.

The importer stops at the raw-copy boundary. It does not update metadata,
create the evidence epoch, recompute indices, regenerate the viewer, perform
Git operations, or publish. A successful import is therefore an intake result,
not a completed dataset release.

## Retests and replacements

Deleting a rejected CSV and adding a retest in a later commit does not erase
the earlier file from Git history. It does, however, create a new frozen source
commit and a new acquisition identity. The retest must be logged as a retest;
it must not inherit the old run's hash or be described as the same acquisition.

Reusing an old filename is technically traceable through Git, but a new,
unambiguous filename is easier to audit. In either case, the new epoch's raw
inventory and retention manifest are authoritative for the new release.

## Folder renames and metadata corrections

A folder rename is allowed, but every path-bound artifact must be regenerated:
the raw inventory, metadata binding, retained-run manifest, acquisition aliases,
curve-pack provenance, viewer allowlist, and package hashes. Do not rename only
the folder and leave generated records pointing to the old path.

A metadata correction does not change raw force samples, but it still changes
the published record and provenance. Record the correction and its source,
regenerate the affected artifacts, and state whether any measured or derived
number changed.

## What not to do

- Do not expect a pushed folder to appear automatically in an existing viewer.
- Do not manually add a folder to the viewer or edit its generated scalar table.
- Do not average two supported populations into one cohort.
- Do not release a singleton because it is the only run that passed.
- Do not substitute turnaround or the final sample for an undetected force
  wall.
- Do not reuse an old evidence identity after source, membership, method,
  metadata, or calibrated-reference changes.
