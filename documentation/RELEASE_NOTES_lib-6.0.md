# EC Parts Builder lib-6.0 release notes

Status: published from Git tag `ec-parts-lib-6.0`. The combined site retains
Force Curve Bench `fc-3.4` unchanged and publishes EC Parts Builder `lib-6.0`.

`lib-6.0` is a ground-up consumer-interface replacement for the lib-5.x review
work. It preserves the source catalog, stable identities, compatibility
evidence, keyboard registry, measured-specimen mappings, and deterministic
release controls. It does not carry forward the former multi-tool navigation
or catalog-as-a-separate-page structure.

## Structural changes

- Renamed the consumer tool **EC Parts Builder** while retaining the hosted
  `dome-lab-parts.html` path.
- Made the generated page one standalone builder. Shopify owns the Dome Lab
  home page, header, and navigation.
- Removed the in-tool Home, Parts Library, Workshop, sibling-tool links, and
  placeholders for future tools.
- Replaced separate builder and catalog pages with one row-based build and a
  contextual category chooser.
- Added an optional source-backed **Start from a keyboard** workflow and a
  visible modified state after changing a loaded configuration.
- Limited public categories to parts that occupy meaningful build slots.
- Fixed the public projection at 9 component rows, 13 keyboard starters, 68
  exact dome-specimen measurements carrying measured collapse force plus
  released Weight Index and Tactility Index values, and 2 public keycap
  additions.

## Evidence presentation

- Kept an absent applicable compatibility edge visibly **Not verified**.
- Standardized customer-facing compatibility labels as **Works**, **Works with
  conditions**, **Does not work**, and **Not verified**.
- Kept domes outside the compatibility matrix with the separate label **Not
  evaluated**.
- Reduced the browser payload to 338 decision-changing edges while retaining
  the complete 3,403-edge configuration as the audit authority.
- Limited dome measurements to measured collapse force plus released Weight
  Index and Tactility Index values for exact measured specimens.
- Removed force curves, force-wall values, assembly-match cards, retained-run
  displays, and full provenance machinery from the consumer UI. Those records
  remain generator-side evidence and in the Force Curve Bench domain.

## Embed and release controls

- Restricted the Shopify bridge to exact-origin trust establishment and bounded
  height synchronization.
- Required actual numeric message fields; numeric strings are not coerced.
- Locked the trusted parent to an allowlisted referrer or, when unavailable,
  the first fully validated parent message. Later origins cannot replace it.
- Bounded reported height to 400–20,000 pixels.
- Prohibited wildcard targets, modal-placement messages, URL fragments, and
  history mutation.
- Preserved all protected predecessor-tool, continuity-endpoint, raw-data, and
  canonical-evidence byte checks and the explicit publication gate.

## Release verification

- two byte-identical release generations;
- Python release and data-contract tests;
- offline runtime battery;
- desktop and mobile browser acceptance;
- Shopify exact-origin bridge acceptance; and
- verification of the complete manifest and SHA-256 inventory.

These checks passed before the explicitly authorized promotion. Future release
candidates must pass the same gates and receive their own publication
authorization.

See [EC_PARTS_LIBRARY.md](EC_PARTS_LIBRARY.md) for the public behavior and
[SHOPIFY_EMBED.md](SHOPIFY_EMBED.md) for the normative bridge contract.
