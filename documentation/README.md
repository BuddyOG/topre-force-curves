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

The longer research paper is not part of this documentation set. These files
contain the method, data identity, calculation rules, and limitations needed to
use and audit the released Force Curve Bench without that paper.

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
