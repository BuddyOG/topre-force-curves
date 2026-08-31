# Verifying the published site

The repository publishes Force Curve Bench `fc-3.4` and EC Parts Builder
`lib-6.0`. The Force Curve Bench canonical viewer URL is
[https://buddyog.github.io/topre-force-curves/](https://buddyog.github.io/topre-force-curves/),
and its frozen release tag is `fc-3.4`. The builder is published at
`dome-lab-parts.html` and is bound to tag `ec-parts-lib-6.0`.

`SITE_RELEASE_MANIFEST.json` and the published `SHA256SUMS` are the active
combined-site authority. `FORCE_CURVE_BENCH_RELEASE_MANIFEST.json` remains the
protected predecessor record for fc-3.4.

Verification and reproduction answer different questions:

- **Tier 1 — package verification:** Is every packaged file present, safe, and
  byte-identical to the release inventory?
- **Tier 2 — full regeneration:** Do the packaged generator, frozen inputs, and
  locked JavaScript dependencies reproduce the packaged generated tree byte
  for byte?

New physical acquisitions enter this process through the frozen
[dome-testing and new-dome intake SOP](testing-sop/README.md). Importer success
alone is not Tier 1 or Tier 2 verification: the importer neither creates a new
evidence epoch nor regenerates a public package.

## Published lib-6.0 package verification

From an extracted lib-6.0 package root, run:

```text
python generator/tools/build_parts_library_release.py verify .
```

On systems where the command is named `python3`, substitute `python3`. The
verifier checks the site manifest and checksum inventory, validates
the lib-6.0 public-release identity, proves that `dome-lab-parts.html` is
exactly the generated release picker, and re-verifies the protected fc-3.4
predecessor.
Every protected predecessor endpoint other than the declared builder
replacement, the canonical evidence tree, and all 184 raw CSV paths must remain
byte-identical to fc-3.4.

The Parts endpoint is the intentional exception to predecessor-page
preservation: `dome-lab-parts.html` is replaced by the generator-owned lib-6.0
release. Overlay source paths and permitted generated changes are explicit and
fail closed; an undeclared source replacement or unrelated generated change is
a verification failure.

Passing this verifier establishes package integrity; it does not independently
prove that an extracted copy is the tree served by GitHub Pages.

## Current Force Curve Bench release identities

```text
Public build:      fc-3.4
Release tag:       fc-3.4
Canonical viewer: https://buddyog.github.io/topre-force-curves/
Raw-source commit: 6e86ac1955a0c566c7aae521705e51371992ba8a
Raw-source tree:   e43d25a3fed8c5177467bba96a5abbdd5a3442b0
Evidence identity: 7aa8588b50856816b7fce90dd6e743c26c6f16926071123291cb054352b6cd4a
Metrics:           metrics-v4.2
Intake:            intake-qc-v1.4
Importer parity:   test-imp 1.1.4
```

The 40-character commit is the immutable raw-data source, not the viewer's
publication commit. Git tag `fc-3.4` identifies the publication commit once the
release is committed and tagged. The publication tree intentionally differs
from the frozen raw-source tree because it replaces the prior `index.html` and
`README.md` and adds the versioned release material; that does not change the
raw-source or evidence identities.

## Published fc-3.4 layout

The fc-3.4 predecessor packager created an exact 752-file repository-root tree. In
addition to the fc-3.4 release-managed paths, it carries forward the complete
184-file raw CSV path set and three legacy HTML endpoints from the frozen
source snapshot:

```text
force-curve-bench-fc-3.4-public/
  .gitattributes
  .nojekyll
  index.html
  README.md
  dome-lab.html
  dome-lab-parts.html
  <other protected legacy HTML endpoint>
  <existing raw-data directories and 184 CSV paths>
  FORCE_CURVE_BENCH_RELEASE_MANIFEST.json
  SHA256SUMS
  assets/
  documentation/
  generator/
  generated/
  canonical-evidence/
```

The angle-bracketed line summarizes the existing relative CSV paths; it is not
a literal directory name. In the historical fc-3.4 package, the 184 CSV files
and the three named legacy HTML files were preserved byte for byte. The root
`index.html` and `README.md` were the only files from the 189-file frozen source
snapshot intentionally replaced. A promoted lib-6.0 overlay would later
replace `dome-lab-parts.html` by explicit policy while continuing to protect
the other two legacy endpoints and the complete raw-data/evidence surface.

The root `.gitattributes` contains exactly `* -text`. It disables Git text and
line-ending normalization for the complete publication tree, preventing a
platform-specific checkout from rewriting inventoried bytes. The empty root
`.nojekyll` directs GitHub Pages to publish the tree without Jekyll filtering
underscore-prefixed paths. Both files are release infrastructure and are not
part of the frozen 189-file raw-source snapshot or canonical evidence identity.

Key paths are:

| Item | Packaged path |
|---|---|
| Production viewer | `index.html` |
| Open Graph image | `assets/force-curve-bench-fc-3.4-og.png` |
| Protected fc-3.4 predecessor manifest | `FORCE_CURVE_BENCH_RELEASE_MANIFEST.json` |
| Active lib-6.0 combined-site manifest | `SITE_RELEASE_MANIFEST.json` |
| Whole-package checksum list | `SHA256SUMS` |
| Generator source and lockfiles | `generator/` |
| Exact generated output | `generated/` |
| Sealed evidence package | `canonical-evidence/` |
| Subjective-pilot bundle | `documentation/subjective-pilot/` |
| Browser acceptance record | `documentation/BROWSER_ACCEPTANCE.md` |
| Git byte-preservation policy | `.gitattributes`, exact content `* -text` |
| GitHub Pages static-publication marker | `.nojekyll`, exactly zero bytes |
| fc-3.4 legacy endpoints | Three preserved HTML continuity endpoints |
| Protected by the lib-6.0 overlay | Every predecessor endpoint except the declared builder replacement |
| Replaced by lib-6.0 | `dome-lab-parts.html` |
| Preserved raw measurements | 184 CSV files at their existing repository-relative paths |

The public Open Graph asset URL is
`https://buddyog.github.io/topre-force-curves/assets/force-curve-bench-fc-3.4-og.png`.

## Current Tier 1: verify the fc-3.4 package

Python 3.11 or newer is sufficient for the package verifier. From the extracted
release root, run:

```text
python generator/tools/build_public_release.py verify .
```

On systems where the command is named `python3`:

```text
python3 generator/tools/build_public_release.py verify .
```

The verifier fails closed. It checks, among other things:

- exact package membership and every SHA-256 entry;
- exact `.gitattributes` content (`* -text`) and its inclusion in the release
  inventory;
- the presence of an exactly empty root `.nojekyll` in the release inventory;
- byte identity of all 184 preserved raw CSV paths and the three preserved
  legacy HTML endpoints against the frozen raw-source snapshot;
- path safety and the absence of symlinks or junctions;
- release-mode viewer identity, canonical URL, Open Graph metadata, and footer;
- byte identity between `index.html` and
  `generated/packs/viewer.staged.html`;
- generator-source and embedded-font provenance;
- generated-manifest closure and full importer-parity evidence;
- the sealed evidence identity, raw Git blobs, reconstructed Git tree,
  retained-run closure, metadata, aliases, and exclusion history; and
- the separation of production release authority from historical evidence and
  review manifests.

This predecessor check covers all 752 fc-3.4 repository-root files. An unexpected
extra file, a missing preserved path, or any byte change to a preserved file is
a verification failure.

The nested evidence verifier can also be run directly:

```text
python canonical-evidence/tools/verify_canonical_epoch.py
```

### Manual checksum inspection

For the current public release, use the Parts release verifier and compare
against `SITE_RELEASE_MANIFEST.json` and `SHA256SUMS`. Use the fc-3.4 verifier
with `FORCE_CURVE_BENCH_RELEASE_MANIFEST.json` when auditing the protected
predecessor independently.

**PowerShell**

```powershell
Get-FileHash -Algorithm SHA256 -LiteralPath '.\index.html'
Get-FileHash -Algorithm SHA256 -LiteralPath '.\dome-lab-parts.html'
Get-FileHash -Algorithm SHA256 -LiteralPath '.\SITE_RELEASE_MANIFEST.json'
Select-String -LiteralPath '.\SHA256SUMS' -Pattern '  index.html$','  dome-lab-parts.html$','  SITE_RELEASE_MANIFEST.json$'
```

**Linux / macOS**

```bash
sha256sum index.html dome-lab-parts.html SITE_RELEASE_MANIFEST.json
grep -E '  (index\.html|dome-lab-parts\.html|SITE_RELEASE_MANIFEST\.json)$' SHA256SUMS
```

Do not substitute a review-build hash for the values recorded by the public
release package.

## Tier 2: reproduce the generated tree

Run the following against one self-consistent extracted package. Do not combine
a local generator with another release package's expected-output tree.

### Requirements

| Component | Requirement |
|---|---|
| Python | 3.11 or newer |
| Node.js | 20 through 22 |
| Python source | Packaged `generator/` tree |
| JavaScript dependencies | `generator/js/package-lock.json`, installed with `npm ci` |
| Frozen raw cache | `canonical-evidence/raw_cache/repo-6e86ac1955a0c566c7aae521705e51371992ba8a/` |
| Expected output | Packaged `generated/` tree |

The package contains the generator source, release templates, font assets,
Python lockfile, npm lockfile, frozen raw cache, and expected generated output.
Installing locked dependencies requires access to the configured Python package
index and `registry.npmjs.org`.

### PowerShell

Run from the extracted release root:

```powershell
$commit = '6e86ac1955a0c566c7aae521705e51371992ba8a'
$cache = (Resolve-Path ".\canonical-evidence\raw_cache\repo-$commit").Path

python -m venv .verify-venv
.\.verify-venv\Scripts\Activate.ps1
python -m pip install -r .\generator\requirements-lock.txt
python -m pip install -e .\generator

Push-Location .\generator\js
npm ci --no-audit --no-fund
Pop-Location
$env:NODE_PATH = (Resolve-Path '.\generator\js\node_modules').Path

python -m domelab_pipeline.cli `
  --cache $cache `
  --commit $commit `
  --out .\generated `
  --viewer-profile release `
  --check
```

### Linux / macOS

Run from the extracted release root:

```bash
commit='6e86ac1955a0c566c7aae521705e51371992ba8a'
cache="$(pwd -P)/canonical-evidence/raw_cache/repo-${commit}"

python3 -m venv .verify-venv
. .verify-venv/bin/activate
python -m pip install -r generator/requirements-lock.txt
python -m pip install -e generator
( cd generator/js && npm ci --no-audit --no-fund )
export NODE_PATH="$(pwd -P)/generator/js/node_modules"

python -m domelab_pipeline.cli \
  --cache "$cache" \
  --commit "$commit" \
  --out generated \
  --viewer-profile release \
  --check
```

The check is non-mutating. It recomputes the complete current generated output and
reports missing, unexpected, stale, or modified generated files. Exit status 0
proves that the packaged generator reproduces the packaged `generated/` tree,
including the public viewer and parity report.

To produce a clean second tree instead, give `--out` a new empty destination
such as `regenerated-fc-3.4` and use `--write`. Its
`generated_manifest.json` must be byte-identical to
`generated/generated_manifest.json`; the manifest covers every other generated
artifact.

## Completed engineering evidence

- The accepted GUI and release-integration corrections are generator-owned.
- A clean second generation reproduced the checked output byte for byte.
- Full-fleet JavaScript/Python metric parity passed for all 184 semantic run
  bindings, including exact null/flag/audit agreement.
- Local interactive browser checks, hostile-input/offline batteries, responsive
  contracts, and a real PNG export passed as recorded in
  [Browser acceptance](BROWSER_ACCEPTANCE.md).
- These checks did not change the scientific payload.

## Scientific invariants

A viewer-only fc-3.4 regeneration must not change:

- the frozen raw-source commit, Git tree, or canonical evidence identity;
- the 184 semantic raw-run bindings or 180 unique acquisitions;
- the 76 semantic records or 75 independent measurement cohorts;
- the full-precision per-run or aggregate canonical measurements;
- the `metrics-v4.2` or `intake-qc-v1.4` method identities; or
- the `perception-rank-v1` formulas, inputs, or 68-cohort calibration fleet.

If any of those values changes, the work is not merely a viewer rebuild and
must be reviewed and versioned as a new evidence or method change.

## Deployment checks

For fc-3.4, the release operator should load the canonical URL,
open a shared `?sel=` comparison, verify the documentation and bundled-license
links, check the Open Graph URL/image, and perform a human phone-width visual
check.

For lib-6.0, load `dome-lab-parts.html` directly and through the Shopify
wrapper. Confirm that Shopify owns Dome Lab navigation and that the
standalone builder has no tabs or other-tool links. Verify 9 component rows,
13 keyboard starters, 68 exact specimen measurements carrying measured collapse
force plus released Weight Index and Tactility Index values, 2 public keycap
additions, and the exact labels **Works**, **Works with conditions**, **Does not
work**, **Not verified**, and dome-only **Not evaluated**. Confirm the consumer
contains 338 decision-changing edges while the full 3,403-edge config audit
passes. These observations do not alter package bytes.
