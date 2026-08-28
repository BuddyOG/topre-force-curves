# Force Curve Bench data and provenance

> Provenance documentation for Force Curve Bench fc-3.4. Generator integration,
> byte-identical regeneration/parity, and local browser/runtime acceptance are
> complete. The canonical viewer is
> [https://buddyog.github.io/topre-force-curves/](https://buddyog.github.io/topre-force-curves/)
> and the frozen release tag is `fc-3.4`. Exact production-package hashes are
> recorded by `FORCE_CURVE_BENCH_RELEASE_MANIFEST.json` and `SHA256SUMS`. This
> preparation task did not create the promotion commit or tag and did not
> deploy the files.

The Force Curve Bench is a presentation layer over a frozen evidence epoch. Its
source measurements, retained-run membership, full-precision results, and
metadata are tied to one Git commit and one independently verifiable evidence
identity. Viewer changes do not silently change that evidence.

## Frozen evidence identity

| Property | Frozen value |
|---|---|
| Repository | `BuddyOG/topre-force-curves` |
| Git commit | `6e86ac1955a0c566c7aae521705e51371992ba8a` |
| Git root tree | `e43d25a3fed8c5177467bba96a5abbdd5a3442b0` |
| Canonical epoch | `canonical-evidence-2026-08-15-6e86ac19` |
| Canonical evidence identity | `7aa8588b50856816b7fce90dd6e743c26c6f16926071123291cb054352b6cd4a` |
| Evidence package | `canonical-evidence-epoch-6e86ac19-step2` |
| Metrics method | `metrics-v4.2` |
| Intake policy | `intake-qc-v1.4` |
| Importer parity authority | `test-imp 1.1.4` |

The Git commit identifies the repository snapshot. The Git tree identifies the
complete directory tree at that commit. The evidence identity seals the
canonical inputs, decisions, and generated evidence surfaces. These identities
serve different purposes and should be reported together.

## Population and count definitions

Several correct counts describe different layers of the dataset. They must not
be treated as interchangeable.

| Count | Meaning |
|---:|---|
| 189 | All files in the frozen repository snapshot. |
| 184 | Raw CSV paths in that snapshot. All 184 are retained. This is also the number of semantic run bindings used by the viewer. |
| 180 | Unique physical acquisitions after shared evidence is counted once. |
| 76 | Semantic records shown by the generated dataset. A semantic record is one stated interpretation of evidence, not necessarily an independent physical test. |
| 75 | Independent measurement cohorts after the shared-evidence alias is counted once. |
| 76 | Derived curve packs, one for each semantic record. |
| 68 | Release-eligible dome-baseline cohorts in the frozen reference fleet used to calibrate the two perception indices. Part-assembly records are excluded from this calibration population. |

### Why 184 paths become 180 acquisitions

Four raw acquisitions appear under both `Topre_HHKB_Pro2_45g` and
`Topre_Slider_Black`. They are one physical test with two legitimate semantic
interpretations: the assembled HHKB Pro2 test and the black-slider parts test.
The epoch therefore keeps both semantic records and all eight path bindings,
while counting the four underlying acquisitions only once for independence.

This shared-evidence ruling produces:

- 76 semantic records;
- 75 independent measurement cohorts;
- 184 retained raw paths or semantic run bindings; and
- 180 unique physical acquisitions.

The two records may be displayed separately, but they must never be described
as eight independent observations.

## Publication-tree continuity

The fc-3.4 publication tree keeps 187 of the frozen snapshot's 189 files byte
for byte: all 184 raw CSV files at their existing repository-relative paths,
plus `dome-lab.html`, `dome-lab-parts.html`, and `ec-switch-explorer.html` for
URL continuity. The prior root `index.html` and `README.md` are intentionally
replaced by the fc-3.4 viewer and public overview.

The three preserved HTML endpoints are not part of the fc-3.4 viewer
validation surface and were not scientifically revalidated by this release.
Their preservation is a compatibility decision. The final 752-file
repository-root inventory, including those 187 preserved files, is sealed by
`FORCE_CURVE_BENCH_RELEASE_MANIFEST.json` and `SHA256SUMS`.

The publication root also adds `.gitattributes` with exact content `* -text`.
This disables Git text and line-ending normalization so platform-specific
checkouts do not rewrite sealed bytes. The file is publication
byte-preservation infrastructure; it is not part of the frozen raw-source
snapshot or canonical scientific evidence. An empty root `.nojekyll` is also
added so GitHub Pages publishes the exact static tree without Jekyll filtering
underscore-prefixed paths. It too is release infrastructure, not source
evidence.

The raw-source commit and Git root tree above continue to identify the
scientific input snapshot. The later fc-3.4 publication commit and tag identify
the expanded release tree. Keeping those identities distinct prevents a viewer
or documentation update from being mistaken for a new raw-data epoch.

## Metadata authority

The owner-supplied workbook contains 79 metadata rows:

- 65 rows marked `YES`, which are authoritative for the corresponding tested
  records;
- 14 rows marked `NO`, which remain documented but are not treated as tested
  records in the canonical fleet; and
- 11 additional released semantic records that are not represented by a
  workbook `YES` row.

Those 11 records retain explicit predecessor-dataset lineage. Spreadsheet
values were not invented to fill the gap. The 65 workbook-authoritative records
plus the 11 predecessor-lineage records produce the 76 semantic records.

The frozen workbook is
`epoch_inputs/source_workbook/untested-domes_v2.xlsx`, with SHA-256
`02e85a2fbdc8e025f1445ab8cb7bd830501f755b79d0a755d6ee31e53bca45a4`.
Its normalized metadata and reconciliation records are preserved alongside the
source workbook.

## Provenance chain

The evidence can be followed from source files to the viewer:

1. **Frozen repository snapshot.** The exact commit is materialized into an
   immutable raw cache. The repository inventory records each path, byte count,
   SHA-256 digest, and Git blob OID; the root tree is reconstructed recursively.
2. **Metadata and history.** The workbook extraction, normalized metadata,
   predecessor lineage, exclusions, retests, and evidence-event ledger preserve
   where every released record came from and what happened before the frozen
   epoch.
3. **Intake and retention.** The retained-run decision artifact binds every raw
   path to its semantic record and records intake decisions under
   `intake-qc-v1.4`, checked independently against `test-imp 1.1.4`.
4. **Canonical calculations.** Per-run and aggregate measurements are generated
   at full precision under `metrics-v4.2`.
5. **Presentation derivatives.** Curve packs and the single-file viewer are
   generated from the canonical data. They support visualization; they do not
   replace the full-precision authority.

At the frozen epoch, all 184 raw paths are retained. Canonical intake reports
no mixed-population stop, no required ramp review, and no unresolved membership
warning. Historical exclusions and nine historically pruned runs remain in the
lineage record; they are not silently reintroduced as frozen raw evidence.

## Which artifacts are authoritative?

Paths below are relative to the root of the sealed canonical-evidence package.

| Artifact | Role |
|---|---|
| `EPOCH_MANIFEST.json` | Package identity, frozen counts, component identities, and canonical artifact map. |
| `SHA256SUMS.csv` | Complete package inventory and SHA-256 checksums. |
| `epoch_inputs/manifest/raw_file_inventory.json` | Raw path, blob, byte-count, and hash authority. |
| `epoch_inputs/metadata/dome_metadata_registry.json` | Reconciled record metadata and its source. |
| `epoch_inputs/history/exclusions_and_retests.json` | Exclusion, replacement, and retest history. |
| `evidence/intake_retention_decisions.json` | Retained-run membership and intake-decision authority. |
| `evidence/per_run_full_precision.json` | Authoritative full-precision per-run results. |
| `evidence/bench_tests.staged.json` | Authoritative full-precision aggregate results. |
| `evidence/generated_manifest.json` | Generated evidence inventory and hashes. |
| `evidence/curve_pack_provenance.json` | Provenance from canonical records to display curve packs. |
| `evidence/packs/curves/*.staged.json` | Derived, lossy display curves; not numeric measurement authority. |

`bench_tests.staged.json` and `per_run_full_precision.json` are the numeric
authorities. Human-readable CSV surfaces are useful for inspection, but the
sealed epoch designates the JSON artifacts above as authoritative.

### Key artifact hashes

These SHA-256 values identify the sealed Step-2 evidence artifacts incorporated
into fc-3.4. They are not hashes of the production viewer or public release
package; use the packaged `FORCE_CURVE_BENCH_RELEASE_MANIFEST.json` and
`SHA256SUMS` for those values.

| Artifact | SHA-256 |
|---|---|
| `EPOCH_MANIFEST.json` | `a1837f802de436035d605e9971563147308e86e7fc089902b30bb22e0581d354` |
| `SHA256SUMS.csv` | `726b9b84dd34b94880cb7d95660c40c7a686f336d73198748800cd48da9caac3` |
| `epoch_inputs/manifest/raw_file_inventory.json` | `3652c2db9a2cf7f464aac53dca40cba6ad214f5cbf3bb1c8963c968cf09b5ca3` |
| `epoch_inputs/metadata/dome_metadata_registry.json` | `3531da02a466ad335bddba5f78fd1c9782e564e5fe488605a0a7500a6194eefb` |
| `epoch_inputs/history/exclusions_and_retests.json` | `f42b4ad91201bd8be93b687d6b2a9a51450c0dae477c38e1a89a313032c44d32` |
| `evidence/intake_retention_decisions.json` | `e6d438b672408cd3e711d907e58424af1f73c13650674526900ce24ceeea9bf4` |
| `evidence/per_run_full_precision.json` | `28c2d6dbc4391a69b637223bcef3b68429a7c31cbcfd2754c631f0a2dd7d52ee` |
| `evidence/bench_tests.staged.json` | `6d2d482921a6b2de698841287f5ba416613b6f69c471b1124d26ab0887269b6e` |
| `evidence/generated_manifest.json` | `b50d04604e639e19e9ace5ccc5426ceb9deffe75768a34ff61838dfc1a1c880c` |
| `evidence/curve_pack_provenance.json` | `0fe1b9195c71111e578e264469f6de2a381ad49a7241f3b2878ced8f87384888` |

The complete per-file inventory remains `SHA256SUMS.csv`; this abbreviated
table is provided for convenient citation.

### Full precision versus curve packs

Canonical scalar calculations retain full precision. Rounding is a display
operation performed by the viewer. Curve packs are intentionally resampled and
compact, so they are lossy by design. They are suitable for drawing traces, but
not for recalculating, replacing, or auditing the canonical scalar values.

The viewer follows the same separation online and offline:

- raw files from the pinned commit can provide live visualization traces;
- the embedded snapshot provides fallback traces if the pinned files cannot be
  reached; and
- displayed scalar measurements come from the generated canonical record in
  either mode.

An embedded-snapshot fallback does not authorize client-side recomputation of
the released measurements.

## Perception-index provenance

`perception-rank-v1` is an exploratory presentation model layered on the frozen
evidence; it does not modify the canonical epoch.

The Weight Index ranks full-precision collapse force within 68 released
dome-baseline cohorts. The Tactility-sharpness Index ranks full-precision force
drop within the same 68-cohort fleet. Collapse force and force drop were chosen
because they had the strongest observed rank associations in a one-rater,
25-dome, three-session pilot. The pilot selects the mechanical inputs; it does
not transform them into predicted 1–10 ratings.

Each index is the percentile compared with the other domes tested. The
reference fleet, percentile equations, tie handling, interpolation, clamping,
and null rules are fixed by the [index specification](METHOD.md#pilot-derived-perception-indices).
Part assemblies receive no index, and force-wall onset is not an input to
either index.

## Verification

The sealed evidence package includes a standard-library Python verifier. It
checks exact package membership, hashes, path safety, raw-cache and Git-tree
closure, metadata and alias consistency, retention closure, importer parity,
and the absence of generated viewer HTML from the Step-2 evidence output.

See [REPRODUCING.md](REPRODUCING.md) for the distinction between verifying a
released package and regenerating the viewer from source.
