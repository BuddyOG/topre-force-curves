# Dome Lab public release record

Publication date: 2026-08-31  
Repository: <https://github.com/BuddyOG/topre-force-curves>

This record identifies the public Dome Lab system after the Force Curve Bench,
EC Parts Builder, storefront pages, and Preprint 2.0 were released. It does not
replace the tool-specific manifests or the frozen research record.

## Public entry points

- [Dome Lab](https://unrealkeyboards.com/pages/dome-lab) — public hub.
- [Force Curve Bench](https://unrealkeyboards.com/pages/topre-force-curve-library)
  — Shopify presentation of `fc-3.4`.
- [EC Parts Builder](https://unrealkeyboards.com/pages/topre-ec-parts-library-builder)
  — Shopify presentation of `lib-6.0`.
- [Beyond Snap Ratio](https://unrealkeyboards.com/pages/beyond-snap-ratio) —
  Preprint 2.0 overview and download links.
- [Topre & EC Dome Force Curves](https://unrealkeyboards.com/blogs/topre-mods/topre-dome-force-curves)
  — public explanatory article.

The standalone tools remain available at:

- <https://buddyog.github.io/topre-force-curves/>
- <https://buddyog.github.io/topre-force-curves/dome-lab-parts.html>

## Released identities

| Artifact | Public identity |
|---|---|
| Force Curve Bench | `fc-3.4`; Git tag `fc-3.4`; release commit `f8203d4` |
| EC Parts Builder | `lib-6.0`; Git tag `ec-parts-lib-6.0`; release commit `134e0c2` |
| Frozen raw-source commit | `6e86ac1955a0c566c7aae521705e51371992ba8a` |
| Canonical evidence identity | `7aa8588b50856816b7fce90dd6e743c26c6f16926071123291cb054352b6cd4a` |
| Measurement method | `metrics-v4.2` |
| Intake authority | `intake-qc-v1.4`, implementation-parity bound to `test-imp 1.1.4` |
| Perception-index model | `perception-rank-v1` |
| Active site authority | `SITE_RELEASE_MANIFEST.json` and `SHA256SUMS` |
| Protected predecessor authority | `FORCE_CURVE_BENCH_RELEASE_MANIFEST.json` |

`SITE_RELEASE_MANIFEST.json` inventories every released repository path and
its SHA-256 digest. The Force Curve Bench predecessor manifest remains in the
site package and protects the fc-3.4 viewer, raw CSV files, canonical evidence,
and continuity endpoints.

## Paper and research compendium

**Beyond Snap Ratio: Reproducible Force–Travel Measurement and Exploratory
Perceptual Correlates of Weight and Collapse Sharpness in Electrocapacitive
Domes**, Brian Gebo, Version 2.0, 2026-08-29.

- Paper DOI: <https://doi.org/10.5281/zenodo.22167065>
- Research-compendium DOI: <https://doi.org/10.5281/zenodo.22167047>
- Paper PDF SHA-256:
  `4dcbd938149b3ce17c27d121e07675bb1c5c9cf8ab05be9a3ec0e11fd2e35caf`
- Paper manifest SHA-256:
  `ac88859d5ad13992d83df27c6d4da3b601fba79026ab9e0cafa5ee9bd819fbf7`

The paper is a preprint and has not been independently peer reviewed. Its
manuscript and original figures are released under CC BY 4.0. Files in the
research compendium retain the path-scoped rights stated in that compendium;
the paper license does not silently relicense the bench software, repository
documentation, raw data, or third-party material.

## Storefront release and rollback boundary

The public Shopify navigation exposes Dome Lab and its released pages. The
pre-release review page, review article, review theme, and pre-Dome-Lab menu
backup were retained in Shopify on publication day. They are rollback assets,
not public release authorities, and should remain retained through at least
2026-09-14. Preview keys or private administrative links must never be added to
the repository.

The separately retained final Shopify release kit has SHA-256:
`b7aa49f550c56b29035e24659fb8f3c9588b4d34d85e8059ee1a88869fedcc9a`.
It is an operational backup, not part of the public repository package.

## Interpretation boundary

The tools provide versioned bench measurements and evidence-scoped
compatibility information. They do not establish universal product quality,
comfort, preference, manufacturer specifications, or causal perceptual laws.
The 25-dome subjective pilot is exploratory. The planned multi-rater study is
specified in [`prospective-study/`](prospective-study/README.md); no
confirmatory result exists until that study is conducted and analyzed under
its frozen protocol.
