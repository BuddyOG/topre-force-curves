# EC Parts Builder lib-6.1 prepublication acceptance record

Status: **completed and promoted**. The accepted prepublication build identified
as `lib-6.1-review.1`. It was superseded by the public `lib-6.1` release after
review, deterministic verification, owner acceptance, and explicit publication
authorization.

The public production authority is `SITE_RELEASE_MANIFEST.json`, its
`SHA256SUMS` inventory, and Git tag `ec-parts-lib-6.1`. This file preserves the
acceptance history; local review paths and review-build hashes are not
public-release authorities.

## Review scope

The accepted build kept the single-page, row-based builder and contextual chooser
architecture from `lib-6.0`. Its selectable build surface expands from 9 to
**11 component rows**:

- dome, main slider, 1u housing, conical spring, 1u silencing ring, and
  keycaps;
- 2u stabilizer assembly, 2u stabilizer housing, 2u stabilizer slider, and
  2u silencing ring; and
- spacebar stabilizer.

The 2u stabilizer assembly is a top-level convenience selection. Choosing one
loads its recorded housing, slider, and ring state. Each constituent remains
visible and can be changed independently; a change marks the loaded assembly
as modified rather than continuing to imply the recorded configuration.

The ten accepted assemblies are:

| 2u assembly | Housing | Slider | Ring |
|---|---|---|---|
| HHKB | HHKB shell-integrated; not a loose part | Topre 2u Slider | None |
| HHKB Type-S | HHKB Type-S shell-integrated; not a loose part | HHKB Type-S 2u Slider | 0.5 mm |
| Realforce RC1 | RC1 shell-integrated; not a loose part | Realforce RC1 2u Slider; 0.5 mm ring seat | 0.5 mm |
| Topre | Topre 2u Housing | Topre 2u Slider | None |
| Topre Silenced | Topre Silenced 2u Housing; 1.0 mm housing ring seat | Topre Silenced 2u Slider; 0.0 mm ring seat | Topre 2u Silencing Ring; 1.0 mm Poron |
| NovaTouch | NovaTouch 2u Housing | NovaTouch 2u Slider; 4.0 mm nominal travel | None |
| Deskeys | Deskeys Stabilizer Housing; 0.2 mm housing ring seat | Deskeys Stabilizer Slider; 0.5 mm ring seat | Deskeys 0.7 mm Poron |
| DynaCaps | DynaCaps Stabilizer Housing | DynaCaps Stabilizer Slider | DynaCaps 0.5 mm Silicone (recommended) |
| KLC | KLC Stabilizer Housing | KLC Stabilizer Slider | None |
| MetaKeebs | MetaPulse Stabilizer Housing | MetaPulse Stabilizer Slider | MetaPulse 0.5 mm Poron |

The standalone Topre assembly names intentionally do not say Realforce. These
assemblies also apply outside Realforce keyboards, including the identified
Leopold configurations. The internal 2u topology and dimensions above are
owner-supplied project facts; OEM product-family pages do not establish all of
those internal details.

## Separate 2u ring evaluation

The 2u silencing ring is independent from the 1u ring. Changing it reruns the
same geometry calculation used for 1u silencing:

```text
total ring seat = slider ring seat + housing ring seat
fit delta = total ring seat - ring thickness
```

Zero is flush. A negative result indicates compression; a positive result
indicates top-out clearance and possible chatter. The calculation uses the
full-precision values and rounds only its displayed result. An explicit
no-ring selection has zero thickness and is still evaluated when the selected
slider and housing provide ring-seat space. The result is presented as a
condition to review, not as a claim that an untested modified assembly is known
to work.

For the owner-confirmed Deskeys starting point, both the 1u and 2u calculation
are `0.5 mm slider seat + 0.2 mm housing seat - 0.7 mm ring = 0.0 mm`, so both
are flush and the starting point carries no ring-fit warning.

For a complete DynaCaps stack, the calculated compression is intentional. The
manufacturer publishes `0.25 mm slider seat + 0.0 mm housing seat - 0.5 mm
ring = -0.25 mm` as its recommended setup and the corresponding 0.3 mm-ring
setup as 0.05 mm pre-compression. The builder therefore shows 0.25 mm as
**manufacturer recommended** and 0.05 mm as **manufacturer supported**, without
raising a ring-fit warning. The exception requires the matching DynaCaps
slider, housing, and ring; mixed-brand stacks and other compression values keep
the ordinary warning. Selecting no ring still reports the resulting 0.25 mm
top-out clearance and chatter risk. These values are published in the
[DynaCap travel specifications](https://omnitype.com/pages/dynacap) and the
[DynaCap silencing-ring specifications](https://omnitype.com/products/dynacap-silencing-rings).

## Force-Wall and displayed build Travel

The accepted build exposed each eligible measured dome's canonical `travel_mm`
value under the public label **Force-Wall**. This field means detected
force-wall onset in the complete measured test assembly. It is not nominal
dome height, physical or nominal full switch travel, actuation travel, or a
universal bottom-out coordinate.

A Force-Wall value is eligible only when the selected dome resolves to the
exact selected measured specimen, or when the catalog dome has one
unambiguous sole measured specimen. The builder does not borrow a value from a
different specimen, average a family, or select one member of a multi-specimen
family without an exact selection. The dome summary presents the released
values in this order:

```text
Weight Index · Tactility Index · Force-Wall
```

The visible build **Travel** result combines that measured limit with the
current 1u part geometry. Its calculation is:

```text
total ring seat = slider ring seat + housing ring seat
dome compression = max(0, ring thickness - total ring seat)
ring-adjusted slider travel = slider nominal travel - dome compression
Travel = min(ring-adjusted slider travel, Force-Wall)
```

The final `min` operation applies when both limits are numeric. A detected wall
therefore reduces the displayed Travel only when its onset occurs before the
ring-adjusted slider limit. If Force-Wall is null or unavailable, the builder
shows **Not detected** for Force-Wall and may still show the ring-adjusted
slider limit as Travel; it never substitutes a different specimen, family
value, recorded turnaround, or final acquired sample. If the selected slider
does not supply a nominal-travel value, the geometry-derived limit is
unavailable rather than invented.

All source and intermediate values remain at their canonical full precision.
Rounding is a presentation operation applied only to visible values. The
Travel display also identifies dome compression and the available inputs so a
customer can see which limit controls the result.

## Same-manufacturer compatibility policy

An otherwise-unverified pair is labeled **Manufacturer matched** when both
parts have the same canonical, nonempty manufacturer. The builder treats that
pair as positive in candidate and whole-build rollups. This is a declared
library policy for manufacturer-matched parts; it is not presented as recorded
compatibility evidence or a claim that the pair was physically tested.

The policy applies only as a fallback. An unchanged recorded keyboard or 2u
assembly is accepted as exact configuration context. Outside that context,
explicit incompatible and adjudicated conditional evidence take precedence,
followed by explicit compatible evidence and then manufacturer matching,
including when both parts share a manufacturer. An unresolved cross-
manufacturer pair remains **Not verified**. Empty manufacturer values never
create a match, and a shared word in a display name or selection from the same
shortcut is not a substitute for the canonical manufacturer identity.

Keycaps do not physically interact with a conical spring or silencing ring, so
those category pairs are not evaluated as compatibility relationships. This
prevents an unrelated empty edge from turning every otherwise coherent
manufacturer stack into **Not verified**.

Ring-seat geometry and spring warnings are independent evaluations. A
**Manufacturer matched** relationship does not suppress compression, chatter,
or spring-condition reporting.

## Part-scoped conical-spring findings

The Deskeys and KLC conical-spring findings are part-scoped **Does not work**
results. The unresolved MetaPulse conical-spring reliability finding is a
part-scoped **Not verified** result. These findings belong to the selected
spring itself; they do not describe a separate incompatibility between that
spring and every other component in the build.

The accepted consumer projection suppresses the generic matrix-expanded
spring edges subsumed by these three part findings: 31 Deskeys incompatible
edges, 31 KLC incompatible edges, and 35 MetaPulse pending edges. The accepted
payload contains **241 decision-changing pair edges** after that suppression;
the complete 3,570-edge audit closure remains intact for provenance.

In the chooser and assembled build, the affected spring is flagged once on its
own candidate or component row. Other selected parts are not marked as the
cause, and the compatibility detail does not render repeated “spring + other
part” entries. The conservative whole-build status still inherits the
part-scoped result. Genuine pair-specific conditions or conflicts that are not
subsumed by a part issue continue to render and participate in the rollup.

## Starting points

The accepted build exposed **32 starting points**: 28 keyboard starters and 4
manufacturer-parts shortcuts. Their defaults were reviewed by the owner in
`EC_Parts_Starting_Point_Defaults_Review.xlsx` on September 3, 2026. The
recorded workbook SHA-256 is
`e2ac489dcd92a193291e9278afebb6152e8d19a7b3325781a5948de749134f9a`.
The owner's later September 3 correction supersedes the workbook's DynaCaps
ring choice only: both the DynaCaps manufacturer shortcut and its 2u assembly
now load the manufacturer-recommended 0.5 mm Silicone ring.

The keyboard list includes the existing HHKB records and Realforce RC1, plus
Leopold FC660C and FC980C, NovaTouch, Realforce R2/R3/R4, and the Realforce
101U, 103U, 104U, 106U, 108U, 86U, 87U, 89U, and 91U families.

Each starter loads the owner-reviewed starting configuration. Leopold FC660C
and FC980C load the recorded standard 45g Topre configuration. Older Realforce
starters load the recorded variable dome and standard Topre parts; R2 loads
the recorded 45g standard configuration; R3 and R4 load the recorded 45g
silenced configuration; and RC1 loads the recorded 45g selection. These are
starting-point records and do not claim that every production SKU in a broad
family is identical.

The manufacturer shortcuts are Deskeys, DynaCaps, KLC, and MetaKeebs. Each
loads its reviewed manufacturer parts, selected 1u ring state, MX keycaps, and
manufacturer 2u assembly while intentionally loading **no dome**. A
manufacturer shortcut is not a verified working configuration. Its qualifying
same-manufacturer pairs receive the policy label described above, while
unresolved cross-manufacturer pairs, such as generic keycaps without matching
evidence, remain **Not verified**.

Intentional absence is distinct from unresolved data. The manufacturer
shortcuts visibly show that no dome is loaded. Realforce 106U, 108U, 89U, and
91U visibly show that no separate spacebar stabilizer is used because the
short spacebar uses the selected 2u stabilizer assembly. These no-part markers
are display and state sentinels only and are excluded from compatibility
calculations.

## Other catalog additions and rules

- **Topre Realforce Variable** is available as a 30g/45g variable dome choice.
- **NovaTouch Slider** is a 4.0 mm, no-ring-seat 1u slider choice.
- NovaTouch has its own 2u housing, 2u slider, 2u assembly, and spacebar
  stabilizer choices.
- A spacebar shorter than 4.5u is represented with the applicable 2u
  stabilizer assembly, not a separate spacebar stabilizer.
- Existing exact measured dome-specimen values remain measurements, not
  compatibility claims. The variable dome choice does not borrow measurements
  from a different exact specimen. Eligible exact measurements now include
  Force-Wall for the Travel calculation described above.

## Acceptance and promotion outcome

The prepublication build completed deterministic regeneration, the 85-check
runtime battery, the full generator test suite, focused browser acceptance,
and owner review. The owner then explicitly authorized publication. Promotion
was performed through the controlled release process so the generated endpoint,
release identity, manifest, and checksum inventory moved together; the review
HTML was not copied into production by hand.

The review build's final known SHA-256 was
`1f9150b6c1910ccef480dd3b561571e93ec7ca2da59f3fd273b6fa851193b546`.
That hash identifies the accepted review artifact only. The release artifact
and complete public tree are identified by `SITE_RELEASE_MANIFEST.json` and
`SHA256SUMS`.

The historical [lib-6.0 review record](EC_PARTS_LIBRARY_REVIEW_PLAN.md),
[lib-6.0 release notes](RELEASE_NOTES_lib-6.0.md), package checks, and counts
remain unchanged because they describe the predecessor release. See the
[lib-6.1 release notes](RELEASE_NOTES_lib-6.1.md) for the promoted identity and
public change summary.
