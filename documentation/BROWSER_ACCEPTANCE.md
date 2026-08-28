# Browser acceptance — Force Curve Bench fc-3.4

Date: 2026-08-28  
Release profile: `public_release` / `fc-3.4`  
Frozen source commit: `6e86ac1955a0c566c7aae521705e51371992ba8a`  
Canonical evidence identity: `7aa8588b50856816b7fce90dd6e743c26c6f16926071123291cb054352b6cd4a`

This record covers the generator-integrated release bytes accepted before
publication. The canonical viewer URL is
[https://buddyog.github.io/topre-force-curves/](https://buddyog.github.io/topre-force-curves/),
the public Open Graph image is
`https://buddyog.github.io/topre-force-curves/assets/force-curve-bench-fc-3.4-og.png`,
and the frozen publication tag is `fc-3.4`. This preparation task did not
create the tag and did not deploy the files.

## Interactive browser checks

The generated single-file viewer was served from a local HTTP origin and
tested in the Codex in-app Chromium browser at its available 1440 × 900 and
1280 × 720 desktop viewports. The final correction pass below used 1280 × 720.

| Area | Result | Evidence checked |
|---|---|---|
| Fresh load | Pass | Empty chart, generated-fleet count, release identity, method, and footer rendered with no console warning or error. |
| Single dome | Pass | Topre R2 45g showed both indices, the seven requested mechanical descriptors, detected force-wall onset as `3.96 mm` with no reference comparison, and recorded turnaround as the separate `4.25–4.26 mm` test limit. |
| Shared displacement axis | Pass | Force view rendered one 0–4.5 mm fleet-wide scale and its visible force-wall marker. The 4.5 mm endpoint covers the released fleet maximum force-wall onset of 4.04 mm; recorded turnaround and longer samples do not expand the axis. |
| Multi-selection | Pass | Topre R1 45g plus Sony BKE Brown 01/02/03 rendered together; physical siblings received distinct, stable semantic colors. |
| Comparison modes | Pass | Force curves, Weight profile, Tactility profile, and Weight vs tactility each activated and exposed the correct chart label. |
| Readout | Pass | Compact columns and More/Fewer columns worked; the expanded view included detected force-wall onset, turnaround, record ID, source set, and measurement cohort. |
| Sidebar filtering | Pass | Matching nested children remained visible, nonmatching siblings stayed hidden, and selected nonmatching records remained available. |
| Domes / Parts separation | Pass | Switching workspaces cleared incompatible selections; part assemblies displayed `Not calibrated` for both perception indices. |
| Tests workspace | Pass | The 68 dome records and 8 part-assembly records remained separate, sortable/filterable populations. |
| URL restoration | Pass | A four-record `?sel=` comparison restored the same four records in a fresh tab. |
| Theme | Pass | Light and dark themes both rendered with the expected computed page colors. |
| Fonts and requests | Pass | Inter and IBM Plex Mono loaded from embedded data; no third-party font request occurred. Runtime trace requests were limited to immutable raw CSV URLs at the frozen commit. |
| PNG export | Pass | A fresh Topre R2 45g export was produced and visually inspected at 3005 × 1962 pixels: 611,063 bytes, SHA-256 `504f2e1a54a63ff58f1832627260231b816b0a82023d1e328bae45c6b882a224`. It included the shared 4.5 mm scale, the `3.96 mm` force-wall marker without a comparison, the separate recorded turnaround, the build/evidence footer, and a large centered `UNREAL KEYBOARDS` watermark at low opacity behind the chart. The watermark was absent from the live viewer. |
| Rights/footer | Pass | Footer text is `© 2026 Brian “BuddyOG” Gebo — Unreal Keyboards. All rights reserved.` and links to the bundled documentation and terms. |

## Executable runtime batteries

The final correction-focused Python/Node viewer and release suite passed all
157 checks. The batteries cover:

- missing-network and malformed-success responses;
- embedded offline fallback;
- null and hostile-string behavior across cards, curves, profiles, scatter,
  readouts, tooltips, and PNG exports;
- pointer-event and compact-layout behavior;
- all four PNG export modes and evidence-stamped filenames;
- the 390 px scatter/legend geometry and compact-chart height calculation;
- review-versus-release profile separation; and
- one shared fleet-wide axis that covers every released force-wall marker and
  is not expanded by recorded turnaround or longer samples; and
- a PNG-only, low-opacity `UNREAL KEYBOARDS` watermark drawn behind the chart.

Full generator parity also passed for all 184 semantic run bindings, with exact
null/flag/audit agreement and a maximum scalar difference of
`2.1316282072803006e-13` against the accepted JavaScript implementation.

## Responsive visual limitation

The in-app browser advertised a viewport override but did not apply the
requested 390 px width, even after reload and a fresh tab. Therefore this run
does **not** claim a real-browser 390 px screenshot. The 390 px layout math,
compact legend placement, touch/pointer paths, and responsive CSS contracts
passed the executable batteries, and the supplied GUI itself was preserved as
the accepted starting point. A final human phone-width spot check is still a
useful deployment check, but this tooling limitation did not expose a viewer
failure.

## Deployment checks

After publication, load the canonical URL and confirm its Open Graph URL/image,
open one shared `?sel=` URL, confirm the documentation and bundled-license
links, and perform the human phone-width visual check described above. Also
confirm that `dome-lab.html`, `dome-lab-parts.html`, and
`ec-switch-explorer.html` still resolve, and spot-check one published raw CSV at
its preserved relative path. These are continuity checks, not fc-3.4
revalidation of the legacy pages. Exact viewer and package hashes are recorded by
`FORCE_CURVE_BENCH_RELEASE_MANIFEST.json` and `SHA256SUMS` in the packaged
release.
