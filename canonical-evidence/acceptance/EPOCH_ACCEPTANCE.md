# Step-2 canonical evidence epoch acceptance

Status: **PASS** for Step 2 only.

The epoch is frozen at commit
`6e86ac1955a0c566c7aae521705e51371992ba8a`, Git tree
`e43d25a3fed8c5177467bba96a5abbdd5a3442b0`, and evidence identity
`7aa8588b50856816b7fce90dd6e743c26c6f16926071123291cb054352b6cd4a`.

The sealed population is 76 semantic records across 75 independent measurement
cohorts, backed by 184 raw paths and 180 unique acquisitions. All 184 paths are
retained. There are no mixed-population stops, ramp-review requirements, or
canonical membership warnings. The Topre HHKB Pro2 / black-slider alias remains
two semantic interpretations of four shared physical acquisitions, never eight
independent observations.

The authoritative workbook has 65 `YES` rows and 14 `NO` rows. A fresh
artifact-tool extraction of `Untested Domes!A1:G80` is byte-identical to the
bundled snapshot. The 11 non-workbook records retain explicit predecessor
lineage rather than invented spreadsheet values.

The exact cache closes over all 189 Git paths: path, byte count, SHA-256, Git
blob OID, and recursively reconstructed root tree all agree. The corrected input
index closes 30/30 files and the input validation report passes 53/53 checks.
The independent test-imp 1.1.4 audit reports zero mismatches; its largest scalar
difference from the generator is approximately `1.42e-14`, below the `1e-12`
tolerance.

The generator now fails closed when either active exclusions or active review
registries declare a commit other than the verified frozen commit; both mutation
cases pass their targeted regression tests.

The final post-seal selections pass: 218/218 core and canonical-epoch checks,
48/48 Step-2 pipeline checks (with three viewer-only Step-3 selectors explicitly
deselected), the evidence-only generator check, and the read-only input-seal
check. Two consecutive input reseals were byte-identical. These selections may
overlap and their pass counts must not be summed. A broader mixed diagnostic
command had six checks that expect
viewer/picker/prose HTML; those checks are deliberately out of scope because
Step 3 was not executed. They are not Step-2 acceptance failures.

`bench_tests.staged.json` and `per_run_full_precision.json` are authoritative.
The 76 curve packs are explicitly marked derived and lossy.

Step 3 and Force Curve Bench release eligibility remain **deferred**. No HTML was
generated in the canonical `evidence/` tree.
