# EC Parts Builder

EC Parts Builder is a standalone assembly-planning tool for Topre and related
electrostatic-capacitive keyboard parts. It presents one build as component
rows, opens the relevant catalog category when a row is selected, and reports
the compatibility evidence recorded for the resulting assembly.

## Publication status

The repository publishes Force Curve Bench `fc-3.4` and EC Parts Builder
`lib-6.0`. The builder is release-eligible and bound to Git tag
`ec-parts-lib-6.0` by `SITE_RELEASE_MANIFEST.json`.

The hosted path remains
<https://buddyog.github.io/topre-force-curves/dome-lab-parts.html> for URL
continuity. The Shopify wrapper is
<https://unrealkeyboards.com/pages/topre-ec-parts-library-builder>.

## Product architecture

Shopify owns the Dome Lab landing page, header, and navigation. The generated
HTML is only EC Parts Builder. It has no Dome Lab home, no tab for a master
parts list, no tab or link for another tool, and no future-tool placeholder.

The catalog is data for contextual choosers, not a separate consumer page.
Opening a component row shows only candidates for that slot; returning from the
chooser returns the customer to the same build.

## Released scope

The released builder contains:

- **9 component rows:** dome, main slider, 1u housing, conical spring,
  silencing ring, keycaps, 2u stabilizer housing, 2u stabilizer slider, and
  spacebar stabilizer;
- **13 keyboard starters** selected from source-backed keyboard records;
- **68 exact dome-specimen measurements** carrying measured collapse force plus
  released Weight Index and Tactility Index values;
- **2 public keycap additions** projected from the larger vendored catalog;
  and
- **338 decision-changing compatibility edges** in the consumer payload.

The complete **3,403-edge** compatibility configuration remains the audit
authority. Closure rows that do not change a consumer decision do not need to
be sent to the browser because the runtime fails closed: an absent applicable
edge is **Not verified**.

Categories without a meaningful build row remain in the source catalog but are
not exposed as unfinished consumer choices.

## Starting and changing a build

Customers may begin with an empty build or choose **Start from a keyboard**.
A starter loads only selections explicitly recorded in its source-backed
keyboard entry. It does not guess missing parts. After a loaded selection is
changed, the build is labeled as modified rather than continuing to imply a
stock configuration.

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

Domes are outside the compatibility engine and are labeled **Not evaluated**.
A measured dome is not evidence that it fits or functions with every housing,
spring, slider, PCB, plate, or keyboard.

The whole-build result follows the most conservative applicable state. A known
conflict cannot be hidden by other working relationships, and an absent edge
cannot be silently treated as **Works**.

## Exact dome measurements

The builder may show measured collapse force, Weight Index, and Tactility Index
for an exact measured dome specimen. Collapse force is the released mechanical
measurement for that specimen. The two indices are percentile positions within
the 68-dome tested reference fleet. None of these values is a compatibility
result.

Measurements are never borrowed from another specimen or averaged into a
family value. Force curves, force-wall metrics, exact assembly-match cards,
retained runs, and full provenance records remain in the Force Curve Bench and
generator-side evidence rather than being duplicated in EC Parts Builder.

## Interpretation limits

- Catalog inclusion is not an endorsement.
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

Future promotion requires deterministic regeneration, runtime and browser
acceptance, the Shopify iframe checks, protected predecessor byte checks, and
explicit user authorization. A locally generated review build does not satisfy
or bypass that publication gate.

See [SHOPIFY_EMBED.md](SHOPIFY_EMBED.md) for the iframe contract,
[EC_PARTS_LIBRARY_REVIEW_PLAN.md](EC_PARTS_LIBRARY_REVIEW_PLAN.md) for the
completed review record, and
[RELEASE_NOTES_lib-6.0.md](RELEASE_NOTES_lib-6.0.md) for the release change
record.
