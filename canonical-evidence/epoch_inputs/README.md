# Canonical evidence epoch inputs

This directory contains the reproducible metadata, raw-path, Git-blob, and
history inputs for `canonical-evidence-2026-08-15-6e86ac19`. It is deliberately
limited to Step 2. It does not change or implement the Force Curve Bench viewer.

## Frozen authorities

- Repository commit: `6e86ac1955a0c566c7aae521705e51371992ba8a`
- Repository tree: `e43d25a3fed8c5177467bba96a5abbdd5a3442b0`
- Metadata workbook: `source_workbook/untested-domes_v2.xlsx`
- Predecessor metadata lineage: `source_lineage/predecessor_dataset_manifest.json`
- Exact raw snapshot: `../raw_cache/repo-6e86ac1955a0c566c7aae521705e51371992ba8a`

`source_workbook/untested-domes_v2.xlsx` is authoritative for every matching
row and all seven workbook columns. `metadata/dome_metadata_registry.json`
preserves all 79 rows (65 `YES`, 14 `NO`), including the explicit case-only map
from `DynaCaps_Heavy_55g` to repository cohort `Dynacaps_Heavy_55g`.

The 11 repository cohorts absent from the workbook retain their exact previous
assembly metadata and are named in `legacy_metadata_sets`. Their unavailable
catalog fields—including `tested`—remain explicitly null. No catalog values
were invented for those cohorts.

The final workbook source bytes are SHA-256 `02e85a2fbdc8e025f1445ab8cb7bd830501f755b79d0a755d6ee31e53bca45a4`
(13,815 bytes). They supersede the initial ingestion copy
`c52393a1d3f33c9c21aa2de35c46cb53914fad0eadcfd4d33b1f7dc72def2921`
(13,811 bytes). Both produce the same artifact-tool A1:G80 value/formula
snapshot, SHA-256 `fee2cc5b217e8ce2600d5e8d778f6dc5eca2abbe15d93a4f983b316ca6e940ea`;
there is no metadata value or formula delta.

## Shared Topre evidence

`Topre_HHKB_Pro2_45g` and `Topre_Slider_Black` are two semantic records for one
four-run physical test. The former represents the dome; the latter represents
the black-slider assembly. The four byte-identical path pairs are declared in
`dataset_manifest.step2.json.evidence_aliases`. They share one
`measurement_cohort_id`, so they can never be interpreted as eight independent
observations.

## Primary artifacts

- `metadata/dome_metadata_registry.json`: pipeline verifier metadata authority
- `manifest/dataset_manifest.step2.json`: 76 semantic records and 184 path bindings
- `manifest/acquisition_registry.json`: 180 unique acquisition blobs
- `manifest/repository_file_inventory.csv`: all 189 tracked Git blobs
- `manifest/raw_file_inventory.csv`: all 184 CSV paths
- `manifest/repo_provenance.json`: frozen commit and inventory identities
- `history/evidence_event_ledger.json`: exact retest and nine-run prune history
- `history/exclusions_and_retests.json`: epoch-facing exclusion/retest view
- `validation/validation_report.json`: internal invariant results
- `validation/raw_cache_materialization.json`: correction and exact-cache audit
- `SHA256SUMS.csv`: hashes for every bundled file except itself and transient
  Python/Node cache files, which are not evidence-epoch artifacts

## Reproduction

The workbook snapshot must be extracted with the bundled `artifact-tool`, not
`openpyxl`. With the bundled Node runtime and package directory available to
module resolution, run:

```powershell
node scripts/extract_workbook.mjs `
  --input source_workbook/untested-domes_v2.xlsx `
  --output source_workbook/workbook_snapshot.json
```

The base builder deliberately emits a version 1 validation report. The
canonical final sequence is: rebuild the base inputs in place, rerun the
hash-verified independent test-imp 1.1.4 audit, and then run the fail-closed
seal. The seal alone writes the version 2 validation report and exhaustive
checksum index; it does not modify the audit reports, generator inputs,
staging tree, raw cache, or repository.

From this epoch's work root, use the following sequence. `$frozenRepo` must
name the clean Git working tree at the frozen commit, and `$importerRoot` must
name the hash-verified test-imp 1.1.4 source/release directory.

```powershell
$epochWorkRoot = (Get-Location).Path
$frozenRepo = 'D:\Documents\GitHub\topre-force-curves'
$importerRoot = Join-Path (Split-Path $epochWorkRoot -Parent) 'test-imp-v1.1-work'
$frozenCommit = '6e86ac1955a0c566c7aae521705e51371992ba8a'

python -B epoch_inputs/scripts/build_epoch_inputs.py `
  --repo $frozenRepo `
  --raw-cache "raw_cache/repo-$frozenCommit" `
  --workbook epoch_inputs/source_workbook/untested-domes_v2.xlsx `
  --workbook-snapshot epoch_inputs/source_workbook/workbook_snapshot.json `
  --legacy-manifest epoch_inputs/source_lineage/predecessor_dataset_manifest.json `
  --output epoch_inputs

python -B epoch_inputs/validation/audit_test_imp_1_1_4.py `
  --importer-root $importerRoot

python -B epoch_inputs/scripts/seal_epoch_inputs.py --work-root $epochWorkRoot
$reportSealOne = (Get-FileHash epoch_inputs/validation/validation_report.json -Algorithm SHA256).Hash
$indexSealOne = (Get-FileHash epoch_inputs/SHA256SUMS.csv -Algorithm SHA256).Hash

python -B epoch_inputs/scripts/seal_epoch_inputs.py --work-root $epochWorkRoot
$reportSealTwo = (Get-FileHash epoch_inputs/validation/validation_report.json -Algorithm SHA256).Hash
$indexSealTwo = (Get-FileHash epoch_inputs/SHA256SUMS.csv -Algorithm SHA256).Hash

if ($reportSealOne -ne $reportSealTwo -or $indexSealOne -ne $indexSealTwo) {
  throw 'Epoch-input reseal was not byte-deterministic.'
}

python -B epoch_inputs/scripts/seal_epoch_inputs.py `
  --work-root $epochWorkRoot --check
```

`--check` is read-only. It reconstructs both final files in memory and fails
unless their bytes and every indexed file hash/size are exact. When resealing
an existing version 2 report, the script first verifies the prior five audit
artifact bindings and active-registry/staging bindings, so post-seal tampering
cannot be normalized into a new checksum index.

The exact current cache was created by `scripts/materialize_git_snapshot.py`,
which writes raw `git cat-file blob` bytes after validating the target path.
`validation/raw_cache_materialization.json` records a 189-file/184-CSV passing
result. The archived `raw_cache_materialization.8816ffb.json` report preserves
the earlier finding that an archive-derived cache expanded all 190 text blobs
from LF to CRLF before it was corrected.

The evidence ledger also records commit `c632440` as a non-authoritative
collection transition: 15 exact raw objects under four generic Topre cohorts
were retired and 25 distinct blobs under nine labeled OEM cohorts were
introduced. Four HHKB blobs already existed under black-slider paths, so only
21 blob identities were new to the parent tree.
That event explicitly does not map old specimens to new specimens and does not
claim that the retired generic Topre 55 g no-retest decision was satisfied,
transferred, or reversed.

The final, non-authoritative history event records commit `6e86ac19` exactly: the two
`Topre_R2_45g` paths `DataLog_1.csv` and `DataLog_2.csv` were replaced in place,
and `DataLog_3.csv` was retired. It makes no claim about cause, quality,
specimen identity, or equivalence beyond that Git diff.
