# Unreal Keyboards tool documentation

> Force Curve Bench `fc-3.4` and EC Parts Builder `lib-6.0` are published from
> this repository. `SITE_RELEASE_MANIFEST.json` and its `SHA256SUMS` inventory
> are the active multi-tool site authority.

The canonical Force Curve Bench is
<https://buddyog.github.io/topre-force-curves/> and its frozen release tag is
`fc-3.4`. `FORCE_CURVE_BENCH_RELEASE_MANIFEST.json` remains its protected
predecessor record. The EC Parts Builder is published at
<https://buddyog.github.io/topre-force-curves/dome-lab-parts.html> and is bound
to tag `ec-parts-lib-6.0` by the active site manifest.

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
- [EC Parts Builder](EC_PARTS_LIBRARY.md) — standalone workflow, Evidence-beta
  labels, catalog projection, and interpretation limits.
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

Beyond Snap Ratio Preprint 2.0 is available at
<https://doi.org/10.5281/zenodo.22167065>, with its research compendium at
<https://doi.org/10.5281/zenodo.22167047>. The preprint is the frozen methods
and exploratory-pilot foundation. The prospective package is frozen as
`perception-validation-v1` and specifies the next multi-rater evidence phase;
it is not a completed result.

## Product boundary

Shopify owns the Dome Lab landing page, header, and navigation. The EC Parts
Builder is one independently embedded tool: it contains no Home or master
library tab and no links to other tools. Its catalog exists as contextual
chooser data for 9 component rows.

The published builder includes 13 source-backed keyboard starters, 68
exact dome-specimen measurement mappings carrying measured collapse force plus
released Weight Index and Tactility Index values, 2 public keycap additions,
and 338 decision-changing compatibility edges. The complete 3,403-edge
configuration remains the audit authority. Customer-facing compatibility
labels are **Works**, **Works with conditions**, **Does not work**, and **Not
verified**; domes are **Not evaluated**.
