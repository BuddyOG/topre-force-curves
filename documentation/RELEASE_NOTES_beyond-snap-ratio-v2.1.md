# Beyond Snap Ratio Preprint 2.1 — clarification notes

Release date: 2026-09-04

Git tag: `beyond-snap-ratio-v2.1`

Version DOI: <https://doi.org/10.5281/zenodo.22295223>

All-version concept DOI: <https://doi.org/10.5281/zenodo.22167064>

Research-compendium DOI: <https://doi.org/10.5281/zenodo.22167047>

## Clarified index arithmetic

Preprint 2.1 makes the released index construction explicit:

```text
Weight Index = fleet percentile(full-precision cohort collapse force)
Tactility Index = fleet percentile(full-precision cohort force Drop)
```

Each index is a single-input coordinate in the frozen 68-dome reference fleet.
Pearson and Spearman coefficients summarize associations; neither is an
arithmetic weight. The legacy analysis field
`rho_weighted_family_composite_spearman_rho` describes a rejected candidate-
composite diagnostic, not either released index.

## Press work to force-wall

Press work to force-wall is correctly sixth in the perceived-weight screen:

- `rho = 0.817380609886974`;
- 95% BCa interval `[0.648791394920568, 0.913590454630411]`;
- fourth-ranked Drop `rho = 0.8223999523`; and
- fifth-ranked Drop rate `rho = 0.8181528164`.

The near-tie is resolved by full-precision values. The metric remains a
separate full-stroke-effort descriptor rather than an index input because it
uses the assembly-defined detected force-wall endpoint, can be unavailable
when no wall is detected, and is highly redundant in the pilot with collapse
force (`rho = 0.900000`) and pre-collapse work (`rho = 0.943077`). The pilot
does not establish an independent contribution that warrants adding it to the
single-input Weight Index.

## Scientific and software boundary

This is an editorial clarification. It changes no force curve, subjective
observation, statistical estimate, figure, index input, reference-fleet value,
percentile calculation, model identifier, or protected Force Curve Bench
runtime byte. Preprint 2.0 remains an immutable archival version.

The 21-file Zenodo payload passed deterministic checksum validation. The
54-page PDF SHA-256 is
`1de8e71e32b557e4cffeffe03ffb13a6326789e99b04890147043f6f7728c862`;
the publication-manifest SHA-256 is
`4c9e664529f70ccb35573daab6a0248d8642d04534aef02b6b87aca8359b1686`.
