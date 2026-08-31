# Force Curve Bench fc-3.4 — release notes

> The accepted `v416-fc-3.4v2` GUI is integrated into the generator;
> byte-identical regeneration/parity and local browser/runtime acceptance are
> complete. Publication metadata is frozen at
> [https://buddyog.github.io/topre-force-curves/](https://buddyog.github.io/topre-force-curves/)
> and Git tag `fc-3.4`. Package-specific hashes are recorded in
> `FORCE_CURVE_BENCH_RELEASE_MANIFEST.json` and `SHA256SUMS`. This preparation
> task did not create the promotion commit or tag and did not deploy the files.

## Summary

fc-3.4 delivers a more robust, shareable, touch-friendly Force Curve Bench on
top of the existing frozen evidence epoch. It changes viewer behavior and user
experience. It does not change the canonical test population, retained runs,
measurement method, full-precision results, or perception-index equations.

## Scientific and data continuity

The first v416 handoff preserved the generated scientific payloads from
`fc-3.4-review.2` byte for byte, including the build contract, canonical record
table, retained-run membership, embedded traces, and perception model. The
v416v2 second GUI update changes presentation/runtime code only and does not
change those scientific payloads.

| Contract | fc-3.4 status |
|---|---|
| Frozen source commit | Unchanged: `6e86ac1955a0c566c7aae521705e51371992ba8a` |
| Canonical evidence identity | Unchanged: `7aa8588b50856816b7fce90dd6e743c26c6f16926071123291cb054352b6cd4a` |
| Retained membership | Unchanged: 184 bindings over 180 unique acquisitions |
| Dataset population | Unchanged: 76 semantic records and 75 independent cohorts |
| Canonical metrics | Unchanged: `metrics-v4.2` |
| Intake authority | Unchanged: `intake-qc-v1.4`, checked against `test-imp 1.1.4` |
| Perception model | Unchanged: `perception-rank-v1` and its 68-dome reference fleet |
| Index inputs | Unchanged: collapse force for Weight Index; force drop for Tactility Index |

No canonical data, method, or index change is part of this viewer update.

## First GUI update: v416

### Reliability and performance

- A failed or malformed live trace request now terminates cleanly instead of
  leaving a selection stuck in a loading state.
- Live requests use a 10-second timeout and fall back to the embedded trace
  snapshot when available.
- Fatal integrity errors and unexpected runtime failures produce a visible,
  dismissible error banner while remaining fail-closed.
- Empty, loading, and error states are drawn in the chart rather than appearing
  as an unexplained blank plot.
- Pointer-only repaints no longer rebuild the comparison readout table.
- Pointer and resize redraws are coalesced with `requestAnimationFrame`.
- Group-member trace requests load in parallel, and the chart force maximum is
  computed once per paint.

### Touch, sharing, and comparison workflow

- Pointer Events support mouse, pen, and tap-to-read touch interaction while
  retaining vertical page scrolling.
- Coarse-pointer devices receive a tap-specific chart hint.
- Selection state is written back to `?sel=` with `history.replaceState`,
  including non-default record identities, so a comparison URL can be shared.
- Parts-information tips can be toggled on touch devices.
- The viewer reports dome/parts selection conflicts in an on-screen toast.
- Comparisons are capped at ten simultaneous tests to preserve distinct colors.
- The Tests tab includes a reset control and a live matching-result count.

### Provenance and exports

- Offline fallback is visible through a global snapshot notice and a snapshot
  tag in the implemented single-selection title surfaces.
- Exported PNGs include the bench build, data epoch, abbreviated frozen commit,
  and site identity.
- PNG filenames include the active chart mode and bench build, including the
  two profile views and Weight Index versus Tactility-sharpness Index scatter.

### Accessibility, safety, and deployment metadata

- The single-selection statistics remain available to assistive technology
  when the visual card is drawn on canvas.
- Sort controls are keyboard-operable buttons with `aria-sort`; collapsible
  sidebar groups expose keyboard interaction and expanded state.
- Narrow profile views use a compact legend below the plot.
- Generated strings are escaped across the principal HTML-rendering paths,
  including the test-filter self-injection case.
- The page now includes a description, Open Graph title and description,
  favicon, and a JavaScript-required fallback message.
- Obsolete individual-run display code and duplicate retained-run constants
  were removed; retained fallback paths are derived from canonical membership.
- Dataset grouping prefers generated record kind rather than filename patterns.

## Second GUI update: v416 → v416v2

This section lists only the second-update delta:

- The old combined **Comparison** tab is split into dedicated **Domes** and
  **Parts** workspaces beside **Tests**. Crossing between Domes and Parts clears
  an incompatible selection, and part deep links open the Parts workspace
  automatically.
- Sidebar tests are grouped under collapsed brand/manufacturer headings, with
  nested variant/style groups where applicable. Customer-facing names use
  spaces instead of source-key underscores.
- The Domes sidebar adds collapsible minimum/maximum filters for Weight Index,
  Tactility Index, Collapse, and Snap %.
- Named dome colors use semantic curve colors, including a progression from
  lighter V1 to fully saturated T1 treatments across Deskeys V1/V2/V3/T1;
  unmapped records retain the fallback comparison palette.
- Customer-facing index labels are shortened to **Weight Index** and
  **Tactility Index**. The pilot origin and percentile interpretation remain in
  the method copy.
- The comparison readout now begins with columns relevant to the active chart
  mode and offers **More columns** / **Fewer columns** for the remaining fields.
- Profile and scatter legends reserve a separate band on wide layouts and move
  below the plot on narrow layouts. They show the relevant index summary;
  force-wall remains a force-curves/readout concern.
- The force-curve x-axis remains absolute displacement but trims to the selected
  traces, force-wall markers, and recorded turnaround extents within the
  generated fleet-wide bound.

The canonical scientific payload, retained membership, measurement method,
full-precision values, pilot model, and Weight/Tactility index equations did
not change in this second GUI update.

## Release integration corrections

The following corrections were made while the v416v2 candidate was integrated
into the release generator. They supersede the affected candidate behaviors;
they are not additions to the historical v416→v416v2 delta above.

- The selection-dependent x-axis trimming introduced in v416v2 was removed.
  Every curve now uses one generated, fleet-wide absolute displacement scale.
  Its normal endpoint is 4.0 mm and it expands in 0.5 mm steps only when a
  released force-wall marker requires it. The current fleet produces a
  0–4.5 mm axis; recorded turnaround and sample length no longer inflate it.
- Dynamic values in the parts-information tooltip are escaped before insertion
  into the document.
- Detected force-wall onset is reported only as the measured onset of the
  complete test assembly. The candidate-only comparative delta readout was
  removed; recorded turnaround remains a separate acquisition extent.
- Repeated index-scale reminders were removed from the viewer and supporting
  guides. Weight Index and Tactility Index are described simply as percentiles
  compared with the other domes tested; the full equations and interpretation
  remain in the method specification.
- PNG exports add a faint, large, centered **UNREAL KEYBOARDS** watermark behind
  the chart while retaining the build/evidence footer.
- Physical siblings that share a semantic hue receive deterministic lightness
  offsets from stable source identity, so color assignment no longer depends on
  selection order.
- Sidebar filtering evaluates nested family members correctly, preserves a
  family parent when a child matches, and hides nonmatching siblings.
- Inter and IBM Plex Mono are embedded in the single-file viewer. This removes
  the Google Fonts runtime dependency. Both fonts remain third-party works
  licensed under the SIL Open Font License 1.1; see
  [Third-party font notice](THIRD_PARTY_NOTICES.md).
- Canonical and Open Graph metadata use
  `https://buddyog.github.io/topre-force-curves/` and
  `https://buddyog.github.io/topre-force-curves/assets/force-curve-bench-fc-3.4-og.png`.
- The accepted GUI and these corrections are now owned by the production
  generator template. Generator checks and byte-identical regeneration/parity
  completed successfully.

These release-integration corrections did not change the scientific payload,
retained membership, method, full-precision values, pilot model, or index
equations.

## Repository and URL continuity

fc-3.4 is published as an exact 752-file repository-root tree. Relative to the
189-file frozen raw-source snapshot, the release has this deliberate
disposition:

- all 184 raw CSV files remain byte-identical at their existing relative paths;
- `dome-lab.html`, `dome-lab-parts.html`, and `ec-switch-explorer.html` remain
  byte-identical so their established URLs continue to resolve; and
- the root `index.html` and `README.md` are intentionally replaced by the
  fc-3.4 viewer and public overview; and
- a root `.gitattributes` containing exactly `* -text` is added to disable Git
  text and line-ending normalization across the sealed publication tree; and
- an empty root `.nojekyll` is added so GitHub Pages publishes the tree
  directly without Jekyll filtering underscore-prefixed paths.

The three retained legacy HTML endpoints are compatibility surfaces. Preserving
them does not mean their science, interface, or wording was revalidated as part
of fc-3.4. Every preserved and release-managed file is included in
`FORCE_CURVE_BENCH_RELEASE_MANIFEST.json` and `SHA256SUMS`; the verifier treats
the 752-file repository-root inventory as exact. `.gitattributes` and
`.nojekyll` are release infrastructure, not part of the frozen raw-source
evidence.

## Publication handoff

The generator-integrated viewer is release-eligible. Its canonical URL is
[https://buddyog.github.io/topre-force-curves/](https://buddyog.github.io/topre-force-curves/),
its Open Graph image is
`https://buddyog.github.io/topre-force-curves/assets/force-curve-bench-fc-3.4-og.png`,
and its frozen tag name is `fc-3.4`.

The fail-closed release packager records exact viewer, manifest, evidence,
generator, preserved-root-file, and package-file hashes in
`FORCE_CURVE_BENCH_RELEASE_MANIFEST.json` and `SHA256SUMS`. It also excludes the
internal `DRAFT_CHECKLIST.md`.

Publication consists of committing the verified package, creating tag
`fc-3.4`, deploying it at the canonical URL, and performing the deployment
checks in [Browser acceptance](BROWSER_ACCEPTANCE.md), including a human
phone-width visual check. This documentation-preparation task did not perform
those repository or deployment actions.

## Rights and limited sharing

© 2026 Brian “BuddyOG” Gebo — Unreal Keyboards. All rights reserved.

The owner permits sharing unmodified charts exported by Force Curve Bench and
unmodified data files published with the repository when the share includes
attribution to **BuddyOG / Unreal Keyboards** and a link to the repository or
the canonical live viewer. This is limited sharing permission, not an open
license or a broader grant for the software, documentation, or data. It does
not permit relicensing or imply endorsement.

The embedded font files are licensed separately under the SIL Open Font
License 1.1, as detailed in
[Third-party font notice](THIRD_PARTY_NOTICES.md). Those font licenses do not
change the project terms above.

## Documentation shipped with the bench

The public documentation covers:

- how to use and compare tests;
- the measurement and intake method;
- metric and index definitions and limitations;
- data provenance and evidence identities;
- package verification and conditional full regeneration;
- the subjective pilot and its one-rater, fixed-order limitations;
- third-party embedded-font notices; and
- these release notes.

The longer research paper and the EC parts-library release are separate later
milestones. Their deferral does not change the frozen evidence or the method
documentation required to audit and use the Force Curve Bench.

## Publication-status addendum — 2026-08-31

The preceding publication-handoff wording records the state at which fc-3.4
was prepared. It is retained as history. The repository actions were later
completed: fc-3.4 was committed, tagged `fc-3.4`, published at the canonical
URL, and followed by EC Parts Builder `lib-6.0` under tag
`ec-parts-lib-6.0`. Beyond Snap Ratio Preprint 2.0 and its research compendium
were also released. See [`PUBLIC_RELEASE.md`](PUBLIC_RELEASE.md) for the live
URLs, DOI records, hashes, and current release boundary.

None of those later publication actions changed the frozen fc-3.4 scientific
payload, index equations, retained-run membership, or evidence identity.
