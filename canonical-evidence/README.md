# Canonical evidence epoch — Step 2

This sealed package is the self-contained canonical evidence epoch for frozen Git
commit `6e86ac1955a0c566c7aae521705e51371992ba8a` and root tree
`e43d25a3fed8c5177467bba96a5abbdd5a3442b0`.

It completes Step 2 only: exact Git-blob raw evidence, authoritative workbook
metadata, exclusion/retest history, retained-run membership, full-precision
per-run and aggregate results, derived curve packs, and provenance hashes.

Step 3 (Force Curve Bench viewer work) is explicitly **deferred and not
executed**.  Nothing under `evidence/` is HTML, and that directory is the only
canonical generated output tree.  The two HTML files under
`generator/domelab_pipeline/release_reference/` are unexecuted, historical
source dependencies whose bytes participate in generator provenance.  The
frozen `raw_cache/` also contains the complete repository tree, including its
pre-existing website files; those are raw snapshot inputs, not generated output.

`bench_tests.staged.json` and `per_run_full_precision.json` are authoritative
for aggregate and per-run numeric results.  The 76 curve packs are deliberately
lossy display derivatives and say so in both their files and
`curve_pack_provenance.json`.

The workbook supplied by the owner is authoritative for the 65 `YES` records.
Four raw acquisitions are intentionally present under both
`Topre_HHKB_Pro2_45g` and `Topre_Slider_Black`: they are one physical test with
two semantic interpretations, so the epoch has 76 semantic records but 75
independent measurement cohorts and 180 unique acquisitions across 184 paths.

The exact accepted test-imp 1.1.4 Windows release ZIP and its frozen source
checksum manifest are under `authority/`.

Verify from any Python 3 installation using only the standard library:

```text
python tools/verify_canonical_epoch.py
```

The verifier rejects missing, extra, or modified files; unsafe paths and
symlinks/junctions; cache/inventory/blob/tree disagreement; metadata and alias
inconsistency; incomplete retention or evidence closure; stale importer parity;
generated HTML; and any package that does not keep Step 3 deferred.
