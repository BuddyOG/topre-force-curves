# EC Parts Builder

EC Parts Builder is a standalone assembly-planning tool for Topre and related
electrostatic-capacitive keyboard parts. It presents one build as component
rows, opens the relevant catalog category when a row is selected, and reports
the compatibility evidence recorded for the resulting assembly.

## Publication status

The repository publishes Force Curve Bench `fc-3.5` and EC Parts Builder
`lib-6.1`. The builder is release-eligible and bound to Git tag
`ec-parts-lib-6.1` by `SITE_RELEASE_MANIFEST.json`.

The hosted path remains
<https://buddyog.github.io/topre-force-curves/dome-lab-parts.html> for URL
continuity. The Shopify wrapper is
<https://unrealkeyboards.com/pages/topre-ec-parts-library-builder>.

The completed `lib-6.1-review.1` prepublication build was promoted to this
release after deterministic regeneration, automated acceptance, owner review,
and explicit publication authorization. Its acceptance history is preserved in
[EC_PARTS_LIBRARY_LIB61_REVIEW.md](EC_PARTS_LIBRARY_LIB61_REVIEW.md).

## Product architecture

Shopify owns the Dome Lab landing page, header, and navigation. The generated
HTML is only EC Parts Builder. It has no Dome Lab home, no tab for a master
parts list, no tab or link for another tool, and no future-tool placeholder.

The catalog is data for contextual choosers, not a separate consumer page.
Opening a component row shows only candidates for that slot; returning from the
chooser returns the customer to the same build.

## Historical lib-6.0 scope

The preceding lib-6.0 release contained:

- **9 component rows:** dome, main slider, 1u housing, conical spring,
  silencing ring, keycaps, 2u stabilizer housing, 2u stabilizer slider, and
  spacebar stabilizer;
- **13 keyboard starters** selected from source-backed keyboard records;
- **68 exact dome-specimen measurements** carrying measured collapse force plus
  released Weight Index and Tactility Index values;
- **2 public keycap additions** projected from the larger vendored catalog;
  and
- **338 decision-changing compatibility edges** in the consumer payload.

Its complete **3,403-edge** compatibility configuration remains the historical
audit authority for that tag. The lib-6.0 release notes and Git tag remain
available for exact citation.

Categories without a meaningful build row remain in the source catalog but are
not exposed as unfinished consumer choices.

## Released lib-6.1 scope

The current release expands the build to 11 rows. A top-level **2u
stabilizer assembly** can load its 2u housing, slider, and separate 2u
silencing ring together; customers can then change those constituent parts
individually, which marks the assembly as modified. Shell-integrated HHKB,
HHKB Type-S, and Realforce RC1 housings are identified as integrated rather
than invented as loose parts.

The release exposes 28 keyboard starters and 4 manufacturer-parts shortcuts.
The owner's September 3, 2026 review supplies the displayed defaults for all
32. The Deskeys, DynaCaps, KLC, and MetaKeebs shortcuts load their selected
ring, MX keycaps, and manufacturer 2u assembly while intentionally loading no
dome. Realforce 106U, 108U, 89U, and 91U intentionally use their selected 2u
assembly in place of a separate spacebar stabilizer. A manufacturer shortcut
still does not claim that every selected relationship has been physically
verified.

Its consumer projection contains **241 decision-changing pair edges**. The
complete 3,570-edge audit closure remains authoritative. Ninety-seven generic
matrix-expanded edges for Deskeys, KLC, and MetaPulse conical springs are not
sent to the browser because the release represents those findings directly
on the affected spring instead.

The 2u ring uses the same calculation as the 1u ring: total ring seat is the
slider seat plus the housing seat, and fit delta is total ring seat minus ring
thickness. Zero is flush, a negative result is compression, and a positive
result is top-out clearance with chatter risk. In a complete DynaCaps
slider-and-housing stack, the manufacturer's published 0.05 mm and 0.25 mm
pre-compression configurations remain visible as measurements but are
informational rather than fit warnings. This exception does not apply to
mixed-brand stacks or other compression values. See the
[lib-6.1 release notes](RELEASE_NOTES_lib-6.1.md) for the ten 2u
assemblies, added NovaTouch parts, Realforce Variable dome, and promotion
boundary.

The release also adds a visible build **Travel** result. It first calculates
the current 1u stack geometry:

```text
total ring seat = slider ring seat + housing ring seat
dome compression = max(0, ring thickness - total ring seat)
ring-adjusted slider travel = slider nominal travel - dome compression
```

When the selected dome resolves to one exact measured specimen, or to one
unambiguous sole measured specimen, its canonical `travel_mm` value is exposed
as **Force-Wall**. If both limits are numeric, the displayed build result is:

```text
Travel = min(ring-adjusted slider travel, Force-Wall)
```

Thus a detected force wall limits Travel only when it occurs before the
ring-adjusted slider limit. The calculation retains canonical values at full
precision and rounds only for display. If no wall was detected, **Force-Wall**
displays **Not detected** and the ring-adjusted slider travel remains the only
available Travel limit; the builder never substitutes another specimen, a
family value, the recorded turnaround, or the final acquired sample.

## Starting and changing a build

Customers may begin with an empty build or choose **Start from a keyboard**.
A starter loads the selections recorded in the owner-reviewed starting-point
registry. Intentional absence is shown as such rather than as unresolved data.
After a loaded selection is changed, the build is labeled as modified rather
than continuing to imply the recorded starting configuration.

In `lib-6.1`, **Choose a starting point** also includes
manufacturer-parts shortcuts. These shortcuts are assembly aids, not keyboard
records or compatibility verdicts.

## Compatibility status: Evidence beta

Compatibility is an **Evidence beta** feature. It reports the structured
evidence currently available; it does not guarantee every physical tolerance,
production revision, layout, or modified part has been tested.

The exact public labels are:

- **Works** — recorded evidence supports the evaluated pairing or build within
  its stated scope.
- **Works with conditions** — use depends on the displayed condition or
  modification.
- **Does not work** — a recorded conflict applies.
- **Not verified** — evidence is absent, pending, or not sufficient to make a
  stronger public statement.
- **Manufacturer matched** — an otherwise-unverified pair has the same
  canonical, nonempty manufacturer. The builder treats that pair as positive
  under a library policy; the label does not claim recorded compatibility
  evidence or physical testing.

The manufacturer policy is a fallback, not an evidence override. An unchanged
recorded keyboard or 2u assembly is accepted as exact configuration context.
Outside that context, explicit incompatible or adjudicated conditional evidence
takes precedence, followed by explicit compatible evidence; only an otherwise
unverified same-manufacturer pair receives **Manufacturer matched**. An
unresolved cross-manufacturer pair remains **Not verified**. Ring geometry and
part-scoped spring findings are evaluated independently and remain visible even
when other parts receive **Manufacturer matched**. A part-scoped finding is
shown once on the affected conical-spring row, not repeated as “spring + other
part” for every selected component. Unrelated rows remain unflagged, while the
whole-build status inherits the spring's result. True pair-specific findings
that are not covered by a part-scoped issue continue to be evaluated normally.
Keycap-to-ring and keycap-to-conical-spring pairs are non-interacting and
therefore are not compatibility checks.

Domes are outside the compatibility engine and are labeled **Not evaluated**.
A measured dome is not evidence that it fits or functions with every housing,
spring, slider, PCB, plate, or keyboard.

The whole-build result follows the most conservative applicable state. A known
part issue or pair conflict cannot be hidden by other working relationships,
and an absent edge cannot be silently treated as **Works**.

## Exact dome measurements

The `lib-6.1` release may show measured collapse force, Weight Index,
Tactility Index, and **Force-Wall** for an exact measured dome specimen.
Collapse force and Force-Wall are released mechanical measurements for that
specimen. The two indices are percentile positions within the 68-dome tested
reference fleet. None of these values is a compatibility result.

**Force-Wall** is the public label for the canonical `travel_mm` field. It is a
detected onset in the complete measured assembly, not nominal dome height,
physical switch travel, or a universal bottom-out coordinate. A null value is
displayed as **Not detected** and is never replaced with the last sample or
recorded turnaround.

Measurements are never borrowed from another specimen or averaged into a
family value. Force curves, exact assembly-match cards, retained runs, and full
provenance records remain in the Force Curve Bench and generator-side evidence
rather than being duplicated in EC Parts Builder.

## Interpretation limits

- Catalog inclusion is not an endorsement.
- **Manufacturer matched** is a library policy for a shared canonical
  manufacturer, not recorded evidence that a pairing was tested.
- **Not verified** does not establish that parts work or do not work.
- **Works with conditions** is not unconditional compatibility.
- Measurements from one specimen do not establish variation across a product
  family.
- Compatibility evidence for one revision or assembly does not automatically
  apply to another.

## Updating the builder

Edit the structured catalog, keyboard registry, compatibility evidence, and
mapping files, then regenerate the tool. Do not hand-edit generated public
HTML. A changed part identity, evidence edge, source, keyboard record, or
measured-specimen mapping is a reviewed data change.

Any later release requires deterministic regeneration, runtime and browser
acceptance, Shopify iframe checks, protected-predecessor byte checks, and
explicit publication authorization. A locally generated review build does not
satisfy or bypass that publication gate.

See [SHOPIFY_EMBED.md](SHOPIFY_EMBED.md) for the iframe contract,
[EC_PARTS_LIBRARY_REVIEW_PLAN.md](EC_PARTS_LIBRARY_REVIEW_PLAN.md) for the
completed historical `lib-6.0` review record,
[EC_PARTS_LIBRARY_LIB61_REVIEW.md](EC_PARTS_LIBRARY_LIB61_REVIEW.md) for the
completed lib-6.1 prepublication acceptance record,
[RELEASE_NOTES_lib-6.1.md](RELEASE_NOTES_lib-6.1.md) for the current release,
and [RELEASE_NOTES_lib-6.0.md](RELEASE_NOTES_lib-6.0.md) for the historical
lib-6.0 release.
