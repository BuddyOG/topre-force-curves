# EC Parts Builder lib-6.0 review record

Status: completed. The prepublication build was `lib-6.0-review.1`; publication
of `lib-6.0` was explicitly authorized on 2026-08-30.

This is the historical acceptance record for the published `lib-6.0` release.
It intentionally retains the 9-row and 13-starter scope that was tested at
that time. The later `lib-6.1` release and its completed prepublication record
are documented separately in
[EC_PARTS_LIBRARY_LIB61_REVIEW.md](EC_PARTS_LIBRARY_LIB61_REVIEW.md).

At the time of this acceptance, the repository published Force Curve Bench
`fc-3.4` and EC Parts Builder `lib-6.0`. This file preserves that historical
boundary after lib-6.1 promotion.

This plan replaces the lib-5.x interface plan. The structured catalog,
compatibility evidence, stable identities, source records, and deterministic
generator remain authoritative. The former consumer structure does not.

## Fixed product boundary

- Shopify owns the Dome Lab landing page, header, and navigation.
- `dome-lab-parts.html` is one standalone EC Parts Builder.
- The catalog feeds contextual component choosers; there is no separate Parts
  Library tab or master-list page.
- The builder contains no Home, sibling-tool link, future-tool placeholder, or
  cross-tool footer.
- The public interface exposes only categories with meaningful build slots.
- Provenance machinery validates the data but does not dictate consumer layout.

The defined review scope is 9 component rows, 13 source-backed keyboard
starters, 68 exact dome-specimen measurements carrying measured collapse force
plus released Weight Index and Tactility Index values, 2 public keycap
additions, and 338 decision-changing compatibility edges in the browser. The
complete 3,403-edge configuration remains the audit authority.

## Consumer workflow

1. Start from an empty build or an optional source-backed keyboard record.
2. Review the component rows and their current selections.
3. Open one row to choose a part in that category.
4. See candidate compatibility before selecting it.
5. Return to the build with focus preserved.
6. Review the conservative whole-build status and any **Works with
   conditions**, **Does not work**, or **Not verified** details.

Loading a keyboard fills only explicitly recorded selections. A changed
selection marks the result as modified. Owner-pending brand kits do not appear
as keyboard presets.

## Compatibility presentation

The underlying evidence remains lossless. Public copy uses exactly **Works**,
**Works with conditions**, **Does not work**, and **Not verified**. An absent
applicable edge remains unresolved as **Not verified**. Domes use the separate
label **Not evaluated**.

Those four compatibility labels describe the historical `lib-6.0` release.
The later `lib-6.1` release adds **Manufacturer matched** for an
otherwise-unverified pair whose canonical manufacturer is the same and
nonempty. It treats that pair as positive under a library policy, not as a
claim of recorded compatibility evidence. An unchanged recorded keyboard or 2u
assembly supplies exact configuration context. Outside that context, explicit
incompatible and adjudicated conditional evidence take precedence, followed by
explicit compatible evidence and then the manufacturer fallback.
Cross-manufacturer unresolved pairs remain **Not verified**. Non-interacting
keycap-to-ring and keycap-to-conical-spring pairs are not evaluated, while ring
geometry and part-scoped spring findings remain independent of the manufacturer
policy. The `lib-6.1` consumer projection contains 241 decision-changing pair
edges after suppressing 97 generic matrix-expanded edges that merely repeat
the Deskeys, KLC, or MetaPulse spring-wide finding. The affected spring is
flagged once on its own row, unrelated parts remain unflagged, and the
whole-build result inherits the part issue. True pair-specific findings remain
in force.

Domes are selectable but outside the compatibility matrix. Exact measured
dome specimens may show measured collapse force plus their released Weight
Index and Tactility Index; the builder does not display force curves,
force-wall metrics, assembly-match cards, retained runs, or full provenance
records.

That force-wall boundary is historical `lib-6.0` behavior. The later
`lib-6.1` release projects the canonical per-specimen `travel_mm` value as
**Force-Wall** and uses it, when detected, as one input to a separate displayed
build **Travel** result. Its formula, exact-specimen rule, and null handling are
specified in the [lib-6.1 review record](EC_PARTS_LIBRARY_LIB61_REVIEW.md).

## Embed boundary

The Shopify bridge is limited to origin establishment and bounded height
reporting. An exact allowlisted referrer may pre-lock the parent; otherwise the
first fully validated parent viewport message locks it. Later origins cannot
replace the lock. All numeric fields require actual JavaScript number values.
Reported height is bounded to 400–20,000 pixels. The bridge performs no modal
placement and the builder does not alter browser history or URL state.

See [SHOPIFY_EMBED.md](SHOPIFY_EMBED.md) for the normative contract.

## Completed review gates

- Generator output is byte-identical across two clean review generations.
- Review and release profiles differ only in approved presentation identity.
- All 13 public keyboard starters and every public part resolve through stable
  source IDs.
- Catalog-only categories and owner-pending presets are absent from the public
  chooser.
- The browser payload contains exactly 338 decision-changing edges, while the
  full 3,403-edge config audit remains green.
- Missing compatibility evidence is visibly **Not verified**.
- **Does not work** candidates are hidden by default but can be deliberately
  revealed for explanation.
- Keyboard, chooser, back, Escape, details, and focus-return journeys pass.
- Layout has no horizontal overflow at 360, 768, and 1280 CSS pixels.
- The iframe bridge passes source-window, exact-origin, first-lock,
  numeric-type, height-bound, and no-history tests.
- The generated root builder equals the staged picker byte for byte.
- The protected fc-3.4 viewer, canonical evidence, raw data, and remaining
  continuity endpoints remain byte-identical to the currently published fc-3.4
  package.
- Production promotion received explicit user authorization after the other
  gates passed.

See [EC_PARTS_LIBRARY.md](EC_PARTS_LIBRARY.md) for public behavior and
[RELEASE_NOTES_lib-6.0.md](RELEASE_NOTES_lib-6.0.md) for the change record.
