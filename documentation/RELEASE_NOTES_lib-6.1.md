# EC Parts Builder lib-6.1 release notes

Status: published from Git tag `ec-parts-lib-6.1`.

EC Parts Builder `lib-6.1` supersedes `lib-6.0` at the existing standalone URL:

<https://buddyog.github.io/topre-force-curves/dome-lab-parts.html>

The Shopify presentation remains:

<https://unrealkeyboards.com/pages/topre-ec-parts-library-builder>

Force Curve Bench remains `fc-3.4`. This release changes the Parts Builder,
its structured catalog and compatibility presentation, and supporting
documentation. It does not change any raw force-curve CSV, retained-run
membership, canonical measurement, perception-index equation, or sealed
evidence identity.

## What changed

- The build surface expands from 9 to **11 component rows**.
- A top-level **2u stabilizer assembly** can load a recorded 2u housing,
  slider, and silencing ring together. Each child part remains independently
  editable, and an edit marks the loaded assembly as modified.
- A separate **2u silencing-ring** row exposes the same ring-seat geometry
  calculation used for the 1u stack.
- The starting-point catalog expands to **28 keyboard starters** and **4
  manufacturer-parts shortcuts**. The shortcuts intentionally load no dome and
  are not presented as verified working configurations.
- The library includes **10 recorded 2u assemblies**, Topre Realforce Variable
  domes, NovaTouch 1u and stabilized-key parts, and additional Realforce and
  Leopold starting points.
- Four short-spacebar Realforce starters explicitly load no separate spacebar
  stabilizer because the selected 2u assembly performs that role.
- Eligible measured domes show **Weight Index**, **Tactility Index**, and
  **Force-Wall** in that order. The visible Travel result uses the earlier of
  ring-adjusted slider travel and the selected dome's detected Force-Wall.
- **Dome compression** is shown separately from Travel. Null Force-Wall values
  remain **Not detected** and never borrow another specimen or the final sample.

## Ring-seat handling

Both 1u and 2u stacks use:

```text
total ring seat = slider ring seat + housing ring seat
fit delta = total ring seat - ring thickness
```

Zero is flush, a negative value is compression, and a positive value is
top-out clearance with possible chatter. The DynaCaps 0.05 mm and 0.25 mm
pre-compression configurations are recognized as intentional only when the
matching DynaCaps slider, housing, and supported ring are selected. The 0.5 mm
Silicone ring is the default for the DynaCaps manufacturer shortcut and 2u
assembly, matching the manufacturer recommendation.

## Compatibility presentation

The complete compatibility configuration contains **3,570 edges**. The
consumer payload contains **241 decision-changing pair edges** after 97 generic
matrix-expanded spring edges are replaced by three part-scoped findings:

- Deskeys conical spring: **Does not work**;
- KLC conical spring: **Does not work**; and
- MetaPulse conical spring: **Not verified**.

Each finding appears once on the spring that causes it. Other selected parts
are not blamed through repeated “spring + part” messages, while the whole-build
status still inherits the spring's state. Genuine pair-specific findings remain
active.

An otherwise-unverified pair with the same canonical, nonempty manufacturer
may receive **Manufacturer matched**. This is an explicit library policy, not a
claim that the pairing was physically tested. Known conflicts, recorded
conditions, and explicit compatible evidence take precedence.

## Verification and acceptance

The final `lib-6.1-review.1` prepublication build passed:

- byte-identical regeneration;
- the 85-check Parts Builder runtime battery;
- the complete generator test suite, with 518 tests passed and 13 declared
  environment-dependent skips; and
- owner review followed by explicit publication authorization.

The accepted review artifact's SHA-256 was
`1f9150b6c1910ccef480dd3b561571e93ec7ca2da59f3fd273b6fa851193b546`.
That value is retained only to identify the accepted review input. The public
release bytes and complete site tree are authoritative only through
`SITE_RELEASE_MANIFEST.json` and `SHA256SUMS`.

## Continuity and rollback

The controlled overlay replaces `dome-lab-parts.html` and its declared
generator/documentation inputs. It preserves the fc-3.4 viewer, all 184 raw CSV
paths, the canonical-evidence tree, and every other protected continuity
endpoint byte for byte. The historical `ec-parts-lib-6.0` tag and
[`RELEASE_NOTES_lib-6.0.md`](RELEASE_NOTES_lib-6.0.md) remain the rollback and
citation authority for the preceding release.

See the [current Parts Builder guide](EC_PARTS_LIBRARY.md), [completed
prepublication acceptance record](EC_PARTS_LIBRARY_LIB61_REVIEW.md),
[compatibility audit](COMPAT_AUDIT_r8.md), and [verification
instructions](REPRODUCING.md).
