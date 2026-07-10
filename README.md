# Topre Force Curves — The Dome Lab data repo

Bench-measured force–displacement data for Topre and Topre-compatible electrostatic capacitive domes, sliders, and silencing configurations — plus the tools built on it. This repository is the data backbone of **[The Dome Lab](https://unrealkeyboards.com/pages/dome-lab)** (`lab-0.7`).

| Piece | Build | Where |
|---|---|---|
| Force Curve Bench (viewer) | `fc-2.1` | [`index.html`](https://buddyog.github.io/topre-force-curves/) · [on unrealkeyboards.com](https://unrealkeyboards.com/pages/topre-force-curve-library) |
| EC Switch Explorer | `cad-2.3` | [`ec-switch-explorer.html`](https://buddyog.github.io/topre-force-curves/ec-switch-explorer.html) · [on unrealkeyboards.com](https://unrealkeyboards.com/pages/ec-switch-explorer) |
| Parts Library + Builder | `lib-3.2 · data r2` | [`dome-lab-parts.html`](https://buddyog.github.io/topre-force-curves/dome-lab-parts.html) · [on unrealkeyboards.com](https://unrealkeyboards.com/pages/topre-ec-parts-library-builder) |
| EC parts dataset | `data r2` | `ec-parts-dataset.xlsx` — the single source of truth for every part and dome |
| Bench importer | `v1.1.0` | local GUI tool; writes this repo, the dataset, and the library in one export |

**Maintained by:** BuddyOG — [Unreal Keyboards](https://unrealkeyboards.com)

---

## The bench hardware

The measurement rig is a build of **[Open-Switch-Curve-Meter](https://github.com/bluepylons/Open-Switch-Curve-Meter)**, an open-source force-curve measurement device designed and published by **bluepylons**. Full design credit belongs to bluepylons — this project stands on that work, and none of the data here would exist without it.

The physical unit itself was commissioned as a custom build from a third-party professional. A machine of this complexity — stepper-driven displacement, load-cell instrumentation, calibration — is worth having built by an expert, and that expertise shows in the measurement repeatability. To be unambiguous: the fabricator built it to order; the design is 100% bluepylons' open-source work, not theirs.

---

## Why this exists

Domes are sold under a single number — Topre 45g, Deskeys v2 49g, DynaCaps Medium, Astro Domes 70g — and that number is generally nothing more than the dome's measured **collapse force**: the force at the tactile peak. It is one point on the curve. Your fingers feel the entire stroke, and two domes with similar collapse forces can feel completely different in weight and tactility. A dome that collapses at a *higher* force than a Topre 45g can still feel *lighter* in use.

This repository establishes a measurement standard built on two numbers that are not published anywhere else for these parts:

| Metric | What it answers | Definition |
|---|---|---|
| **Total Energy** (gf·mm) | How heavy is it, actually? | Area under the press curve from 0 to Travel — the total work done by the finger across the whole keystroke |
| **Snap %** | How tactile is it? | (Collapse − Valley) / Collapse × 100 — the dome-switch industry's tactile-ratio standard. Linear = 0%; higher = crisper |

Collapse force and collapse travel remain useful and are reported, but they are not sufficient for comparison on their own.

Dome-to-dome variation is real — for some lines (BKE Redux v1 in particular) it is wildly different unit to unit. The pipeline is built for it: **multiple physical domes of the same type are tested as separate sets and grouped**, so the data shows both the family and each individual dome.

The full write-up of the testing standard: [Topre & EC Dome Force Curves — How to Read and Compare Domes](https://unrealkeyboards.com/blogs/topre-mods/topre-dome-force-curves).

---

## Repository contents

```
topre-force-curves/
├── index.html                  # Force Curve Bench viewer (fc-2.1, single file)
├── ec-switch-explorer.html     # EC Switch Explorer (cad-2.3, single file)
├── dome-lab-parts.html         # Parts Library + Builder (lib-3.2 · data r2, single file)
├── ec-parts-dataset.xlsx       # The parts + domes source of truth (data r2)
├── <Test_Set_Name>/            # One folder per tested configuration
│   ├── DataLog_1.csv
│   ├── DataLog_2.csv
│   └── ...                     # One CSV per test run (typically 3–5 runs)
└── README.md
```

### Set-folder naming — the dome-number convention

A folder named `<Group>_<NN>` (trailing, zero-padded number) is **physical dome NN of that group**: `Sony_BKE_Gray_01`, `Sony_BKE_Gray_02`, `Sony_BKE_Brown_01`…`_03`. The viewer groups these automatically (expandable parent, per-dome children). A group with a single tested dome displays without its number until a second dome lands. Folders without a trailing number are ordinary standalone sets.

**Domes on the bench:** Topre 30g, Topre 45g, Topre 55g, Topre 55g Aged, Sony BKE Gray (2 domes), Sony BKE Brown (3 domes), NiZ 65g, BKE Redux Extreme, DynaCaps Light / Medium / Heavy.

**Topre-compatible parts:** Topre Slider, Topre Silent Slider, Topre Slider Type-S, Topre Slider + 0.3 mm Silencing Ring, Topre Slider + 0.5 mm Silencing Ring, DynaCaps Parts, DynaCaps Slider + 0.3 mm poron, DynaCaps Slider + 0.5 mm silicone. (Older folder names are preserved on disk; the viewer applies the current display names.)

---

## Data format

Each `DataLog_N.csv` is one complete keystroke — press stroke followed by return stroke — recorded at fixed 0.005 mm displacement steps (~1,600–1,700 rows per run).

| Column | Meaning |
|---|---|
| `Millis` | Timestamp of the sample, milliseconds |
| `Steps` | Stepper position (raw) |
| `Travel (mm)` | Displacement from the start of contact, mm |
| `Scale raw` | Load cell raw reading |
| `Scale (grams)` | Calibrated force, grams-force |

The press stroke runs from 0 to maximum travel; the return stroke runs back to 0. Consumers of the data should split at the row of maximum `Travel (mm)`.

## Test method

- Displacement is stepped in 0.005 mm increments at a constant, quasi-static rate (~0.15 mm/s) while force is logged from a load cell.
- The load cell is calibrated and verified against standardized test weights.
- Each configuration is tested in multiple runs (typically 3–5). Run-to-run deviation in collapse force is under one gram, so published figures round grams and gf·mm to whole numbers; the raw CSVs retain full recorded precision.
- The measurement is quasi-static by design. It captures the dome's intrinsic force curve; it does not capture rate-dependent effects (e.g., viscoelastic damping of foam silencing rings at real typing speeds).

### Derived metrics (as computed by the viewer)

All metrics are computed on the run-averaged press curve, lightly smoothed (7-sample moving average) for feature detection only; energy integrates the unsmoothed data.

1. **Collapse Force / Collapse Travel** — the tactile peak: the most prominent local maximum in the first 75% of the stroke (prominence > 2 g against the following minimum).
2. **Valley** — the post-collapse minimum within 1.6 mm after the peak. Used to compute Snap %.
3. **Travel** — where the bottom-out wall begins: the first point past the valley where the smoothed press slope exceeds 300 g/mm.
4. **Total Energy** — trapezoidal integration of the press curve from 0 to Travel, in gf·mm.
5. **Snap %** — (Collapse − Valley) / Collapse × 100.

For a **dome group**, the group curve is the average of its member domes' averaged curves, with metrics recomputed from that curve. When individual domes are displayed, **no averaging is applied across domes** — each dome is a full, separate test.

## Reference results

Averaged across runs; grams and gf·mm shown at measurement precision here (the viewer rounds for display).

| Test set | Collapse (g @ mm) | Snap % | Travel (mm) | Total Energy (gf·mm) |
|---|---|---|---|---|
| Topre 30g | 36.1 @ 0.69 | 24.9 | 3.99 | 130.8 |
| Topre 45g | 51.9 @ 1.30 | 14.1 | 3.96 | 178.4 |
| Topre 55g | 64.4 @ 1.25 | 20.2 | 3.95 | 213.1 |
| Topre 55g (aged) | 69.5 @ 1.05 | 22.6 | 3.98 | 224.1 |
| NiZ 65g | 75.6 @ 1.66 | 12.8 | 3.94 | 250.6 |
| BKE Redux Extreme | 132.0 @ 0.95 | 56.8 | 3.32 | 311.3 |
| DynaCaps Light | 44.1 @ 1.19 | 15.5 | 4.10 | 158.4 |
| DynaCaps Medium | 48.8 @ 1.15 | 17.5 | 4.02 | 172.6 |
| DynaCaps Heavy | 53.3 @ 1.11 | 19.6 | 4.00 | 184.5 |
| Topre Slider (bare) | 62.9 @ 1.13 | 23.4 | 3.99 | 207.0 |
| + 0.3 mm silencing ring | 61.2 @ 0.98 | 23.6 | 3.75 | 195.6 |
| + 0.5 mm silencing ring | 67.6 @ 0.79 | 24.9 | 3.62 | 207.0 |

### Findings on silencing rings

The slider series above demonstrates, from measurement rather than folklore:

- **Travel loss ≈ ring thickness, less for poron.** A 0.5 mm poron ring removed 0.37 mm of travel (foam absorbs part of its own thickness under preload); silicone transmits closer to its full thickness. On a standard slider, ring thickness becomes dome preload.
- **The collapse point arrives earlier** in the measured stroke by roughly the effective ring thickness, consistent with the ring precompressing the dome.
- **Measured collapse force goes up, not down.** Precompression alone cannot explain this; the increase indicates the ring changes the dome's intrinsic buckling load, consistent with shell-buckling sensitivity to load distribution.
- **Quasi-static tactility barely changes; felt tactility does.** Snap % is nearly identical bare vs. 0.5 mm ring in slow-press data, yet thick rings feel markedly less tactile — rate-dependent foam damping plus shortened pre-travel. Read Snap % alongside Collapse Travel and Travel when rings are involved.

---

## The Force Curve Bench (`index.html`, build fc-2.1)

A single self-contained HTML file — no build step. Hosted with GitHub Pages and embedded at [unrealkeyboards.com/pages/topre-force-curve-library](https://unrealkeyboards.com/pages/topre-force-curve-library).

**Features**

- Overlay any combination of test sets; press and return curves, color-coded; bench readout per set (Collapse @ travel, Snap %, Total Energy, Travel); **Export PNG** at 2× with stats baked in.
- **Dome groups:** `_NN` sibling folders appear as one expandable parent. Selecting the parent shows the group-averaged curve; the *Individual runs* toggle becomes **Individual domes** and overlays each dome as its own full test — own color, markers, readout row — with no cross-dome averaging. If any member's collapse force is more than **±10%** from the group mean, individual domes are shown by default. Children are named in full (`Sony BKE Brown 01`).
- Sidebar: DOMES and TOPRE COMPATIBLE PARTS sections are collapsible; sort is **OEM Topre first** (Topre, then Topre-made lines such as Sony BKE), then aftermarket, alphabetical within. The parts section uses a curated order starting from the stock Topre configuration; parts with defined build recipes carry a **»» info box** listing `PART TYPE / Description` (slider, silencing ring, housing, dome, spring).
- Toggles for return curve, individual runs/domes, markers, guide lines; live filter with `*` wildcard; hover crosshair on the 0.005 mm grid; dark/light theme persisted. The "how to compare" note sits below the chart.

**Data loading:** on load the viewer reads the repo tree from the GitHub API and groups every `DataLog_N.csv` by folder — **new set folders appear automatically**. CSVs are fetched on first selection and cached. If GitHub is unreachable, an embedded delta-encoded snapshot of averaged curves takes over, tagged "snapshot".

## The EC Switch Explorer (`ec-switch-explorer.html`, build cad-2.3)

An interactive, animated cross-section of a complete Topre switch — the educational companion to the bench data. The drawing is a depiction; the physics are this repository's measured curves.

- Press it with the button, the depth slider, or **any key on your keyboard**; drag the keycap, slider, dome, or spring. Release always snaps back — and with a missing silencing ring, the slider smacks the stop wall once and settles, with the **top-out chatter called out in a warning box pointing at the actual gap**.
- Swap standard / silent / Type-S sliders (4.0 / 4.0 / 3.8 mm travel), fit silencing rings (0.3 / 0.5 / 0.7 mm or custom), and watch preload, travel, collapse point, and actuation move.
- **Actuation the way current boards actually do it:** HHKB Classic/Hybrid ship fixed; Realforce R2 APC used fixed steps; R3, R4, and RC1 set actuation 0.1–3.0 mm in 0.1 mm increments from an analog signal; GX1 and Cipulot PCBs add Wooting-style variable actuation **and** reset — the Explorer's Custom mode emulates exactly that, with hysteresis in the live readings.
- Assembly per Topre patent [JP2012-138254A](https://patentimages.storage.googleapis.com/53/d7/b3/636954aedea39a/JP2012138254A.pdf).

## The Parts Library + Builder (`dome-lab-parts.html`, build lib-3.2 · data r2)

Every Topre/EC part and dome in one place, read verbatim from `ec-parts-dataset.xlsx` — names come from the raw list, never vendor terminology, and vendor claims are never treated as measurements.

- **Library:** 40 parts + the full dome catalog with hover property boxes (`STEM / Topre`, `RING SEAT / 0.5 mm`, `TRAVEL / 4.0 mm`), availability, and bench data (▦) synced live from this repo. Dome rows differing only by a trailing number are **one part** (the group), with per-dome bench runs visible from it.
- **Builder:** pick slider, silencing ring, dome, housings, stabilizers, and springs; every combination is checked live against the dataset's compatibility edge list — stem fit, ring preload and top-out chatter math (`effective = ring − (seat + housing offset)`), drilling requirements, unreleased-part warnings. Shells (HHKB, RC1, Heavy Grail) are selected as Housings / Stabilizer Housings (RC1 also Spacebar Stabilizer) and populate their linked slots together, because a shell is one injected part.

## `ec-parts-dataset.xlsx` — the source of truth

Sheets: Parts, Domes, Compatibility (edge list — no row = compatible; domes have no rows *on purpose*, they're universal), Notes, Rings, RingDefaults, Shells, Categories. Every tool is generated from this file; to change the catalog, change the workbook.

## The bench importer (local tool, v1.1.0)

A local GUI (Python/tkinter, packaged with PyInstaller) that turns a raw test session into everything above in one Export:

1. Loads a batch of `DataLog_N.csv` + a `data_log.xlsx` metadata sheet (template with vocabulary dropdowns provided).
2. Validates metadata (names, vocabulary, dome numbers) and raw runs (truncated sweeps, missing return strokes, non-monotonic travel, dropped samples). **Outlier runs (>10% collapse or energy vs. siblings) prompt keep/discard — never silent.**
3. Export writes: the `<Group>_<NN>/DataLog_1..n.csv` folders into this repo, new rows into the dataset's Domes sheet, and the Parts Library's embedded data (dome rows, bench mapping, offline snapshot) — then archives the batch and lays out a fresh blank `data_log.xlsx`.

### Versioning

- **Tool code** is versioned by hand: viewer `fc-X.Y`, Explorer `cad-X.Y`, library `lib-X.Y`, importer `vX.Y.Z` (SemVer, changelog embedded). Each page displays its build in the header.
- **Data revisions** (`data rN`) are bumped automatically by the importer on every export and stamped identically into the library header and the dataset README — if the two numbers match, library and dataset agree.

## Adding a new test set

**Importer path (normal):** fill the `data_log.xlsx` template, drop it beside the batch's CSVs, run the importer, Export, commit, push. Done — both web tools pick the new sets up live.

**Manual path:** create `<Test_Set_Name>/` (use `<Group>_<NN>` for a numbered dome), add `DataLog_1.csv`… matching the column format above, push. Folder names containing `Slider`, `Type-S`, or `Parts` group under **Topre Compatible Parts**; everything else lands under **Domes**.

## Hosting and embedding

GitHub Pages serves all three HTML files from the repo root (`main` branch); every push redeploys in about a minute. Embed with an iframe (fixed height — do **not** size embedded pages with `vh` inside auto-resizing frames):

```html
<iframe
  src="https://buddyog.github.io/topre-force-curves/"
  title="Topre Force Curve Bench — Unreal Keyboards"
  loading="lazy"
  style="display:block;width:100%;border:0;height:calc(100vh - 160px);min-height:820px;">
</iframe>
```

The Explorer and Parts Library embed the same way with their filenames appended to the `src`.

## Using this data

Exported charts and the data in this repository may be shared with attribution to **BuddyOG / Unreal Keyboards** and a link back to this repository or the live viewer.

## Credits

- **Bench design:** [bluepylons — Open-Switch-Curve-Meter](https://github.com/bluepylons/Open-Switch-Curve-Meter) (open source). All design credit for the measurement hardware belongs there.
- **Bench build:** custom-commissioned from a third-party professional fabricator, to bluepylons' design.
- **Testing, data, tools, and the Dome Lab:** BuddyOG / [Unreal Keyboards](https://unrealkeyboards.com).

## Caveats

- Aftermarket and aged parts vary; these curves characterize the specific units tested — which is exactly why multi-dome groups exist.
- The bench is quasi-static. Rate-dependent feel (notably foam silencing rings at typing speed) is discussed above but not directly measured.
- Travel detection uses a slope threshold (300 g/mm); pathological curves without a clean bottom-out wall fall back to end-of-stroke.
