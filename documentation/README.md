# Unreal Keyboards tool documentation

> Force Curve Bench `fc-3.4` and EC Parts Builder `lib-6.1` are published from
> this repository. `SITE_RELEASE_MANIFEST.json` and its `SHA256SUMS` inventory
> are the active multi-tool site authority.

The canonical Force Curve Bench is
<https://buddyog.github.io/topre-force-curves/> and its frozen release tag is
`fc-3.4`. `FORCE_CURVE_BENCH_RELEASE_MANIFEST.json` remains its protected
predecessor record. The EC Parts Builder is published at
<https://buddyog.github.io/topre-force-curves/dome-lab-parts.html> and is bound
to tag `ec-parts-lib-6.1` by the active site manifest.

## Documentation set

- [Viewer Guide](VIEWER_GUIDE.md)
- [Measurement and calculation method](METHOD.md)
- [Data and provenance](DATA_PROVENANCE.md)
- [Limitations and interpretation boundaries](LIMITATIONS.md)
- [Reproduction and verification](REPRODUCING.md)
- [Browser acceptance](BROWSER_ACCEPTANCE.md)
- [Future data updates](DATA_UPDATES.md)
- [Dome testing and new-dome intake SOP](testing-sop/README.md) — frozen
  operator workflow, exact importer usage, exception handling, handoff record,
  and release gates.
- [Third-party font notice](THIRD_PARTY_NOTICES.md)
- [Subjective pilot](subjective-pilot/README.md) — sealed pilot bundle. Its
  phrase “75 raw ratings” refers to 75 session-by-dome observation rows; each
  row contains one weight and one tactility score (150 numeric scores total).
- [fc-3.4 release notes](RELEASE_NOTES_fc-3.4.md)
- [Beyond Snap Ratio Preprint 2.1 clarification notes](RELEASE_NOTES_beyond-snap-ratio-v2.1.md)
  — single-input index arithmetic, association-rank interpretation, and
  publication identities.
- [EC Parts Builder](EC_PARTS_LIBRARY.md) — standalone workflow, Evidence-beta
  labels, catalog projection, and interpretation limits.
- [lib-6.1 release notes](RELEASE_NOTES_lib-6.1.md) — current release changes,
  identity, verification, and continuity boundary.
- [EC Parts Builder lib-6.1 prepublication acceptance](EC_PARTS_LIBRARY_LIB61_REVIEW.md)
  — completed 2u-assembly, expanded-starting-point, and promotion record.
- [EC Parts Builder review record](EC_PARTS_LIBRARY_REVIEW_PLAN.md) — completed
  prepublication acceptance boundary for `lib-6.0`.
- [Shopify embed contract](SHOPIFY_EMBED.md) — required parent/child
  `postMessage` validation and acceptance checks.
- [lib-6.0 release notes](RELEASE_NOTES_lib-6.0.md) — release changes,
  limitations, and verification gates.
- [Dome Lab public release record](PUBLIC_RELEASE.md) — final storefront and
  standalone URLs, release identities, paper hashes, and rollback boundary.
- [Citation and attribution](CITATION.md) — paper, compendium, tool, and data
  citation forms with license boundaries.
- [Prospective multi-rater study](prospective-study/README.md) — frozen
  `perception-validation-v1` SOP, participant script, analysis plan, data
  dictionary, collection templates, and blinded schedule generator.
- [Full research-paper roadmap](research-paper/README.md) — required evidence
  sequence, manuscript plan, figures/tables, and claim matrix.
- [Perception-validation v1 freeze notes](RELEASE_NOTES_perception-validation-v1.md)
  — frozen design, operator package, readiness boundary, and continuity.
- [Dome testing SOP v1 freeze notes](RELEASE_NOTES_dome-testing-sop-v1.md) —
  importer identity, operator/repository boundary, and scientific continuity.
- [Documentation closeout notes](RELEASE_NOTES_dome-lab-docs-2026-08-31.md)
  — dated public-record additions with scientific continuity.

Beyond Snap Ratio Preprint 2.1 is available at
<https://doi.org/10.5281/zenodo.22295223>; the concept DOI for all versions is
<https://doi.org/10.5281/zenodo.22167064>. Its research compendium is at
<https://doi.org/10.5281/zenodo.22167047>. The preprint is the frozen methods
and exploratory-pilot foundation. The prospective package is frozen as
`perception-validation-v1` and specifies the next multi-rater evidence phase;
it is not a completed result.

## Product boundary

Shopify owns the Dome Lab landing page, header, and navigation. The EC Parts
Builder is one independently embedded tool: it contains no Home or master
library tab and no links to other tools. Its catalog exists as contextual
chooser data. The published `lib-6.1` uses 11 component rows, adding a
top-level 2u stabilizer assembly and a separate 2u silencing-ring row to the
historical lib-6.0 surface.

The published builder includes 28 keyboard starters, 4 manufacturer-parts
shortcuts, 10 recorded 2u assemblies, and 68 exact dome-specimen measurement
mappings. Eligible measured domes carry collapse force, Weight Index,
Tactility Index, and Force-Wall onset. The owner's September 3, 2026 review
supplies the 32 starting-point defaults. Manufacturer shortcuts intentionally
load no dome; four short-spacebar Realforce starters use their selected 2u
assembly instead of a separate spacebar stabilizer. These defaults are
starting points rather than compatibility verdicts.

The lib-6.1 consumer projection contains **241 decision-changing pair edges**.
Ninety-seven generic matrix-expanded conical-spring edges are suppressed
because their findings belong to the affected Deskeys, KLC, or MetaPulse
spring itself. The culprit spring is flagged once, unrelated rows remain
unflagged, the whole-build result inherits the part issue, and true
pair-specific findings remain active. The complete 3,570-edge closure remains
the audit authority. The historical lib-6.0 release and its 338-edge browser /
3,403-edge audit counts remain documented by its release notes and tag.
