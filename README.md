# Topre Force Curves

Bench-measured force–displacement data for Topre and Topre-compatible electrostatic capacitive domes, sliders, and silencing configurations, plus an interactive viewer for comparing them.

**Live viewer:** https://buddyog.github.io/topre-force-curves/
**Maintained by:** BuddyOG — [Unreal Keyboards](https://unrealkeyboards.com)

---

## Why this exists

Domes are sold under a single number — Topre 45g, Deskeys v2 49g, DynaCaps Medium, Astro Domes 70g — and that number is generally nothing more than the dome's measured **collapse force**: the force at the tactile peak. It is one point on the curve. Your fingers feel the entire stroke, and two domes with similar collapse forces can feel completely different in weight and tactility. A dome that collapses at a *higher* force than a Topre 45g can still feel *lighter* in use.

This repository establishes a measurement standard built on two numbers that are not published anywhere else for these parts:

| Metric | What it answers | Definition |
|---|---|---|
| **Total Energy** (gf·mm) | How heavy is it, actually? | Area under the press curve from 0 to Travel — the total work done by the finger across the whole keystroke |
| **Snap %** | How tactile is it? | (Collapse − Valley) / Collapse × 100 — the dome-switch industry's tactile-ratio standard. Linear = 0%; higher = crisper |

Collapse force and collapse travel remain useful and are reported, but they are not sufficient for comparison on their own.

---

## Repository contents

```
topre-force-curves/
├── index.html                  # The interactive viewer (single file, no build step)
├── <Test_Set_Name>/            # One folder per tested configuration
│   ├── [<Test_Set_Name>-]DataLog_1.csv
│   ├── [<Test_Set_Name>-]DataLog_2.csv
│   ├── ...                     # One CSV per test run (typically 3–5 runs)
│   ├── *.pdf                   # Annotated per-run force curve plots
│   └── *_DataLog.xlsx          # Source workbook (where present)
└── README.md
```

Test set folders currently cover two categories:

**Domes** — bare dome sheets tested directly:
Topre 30g, Topre 45g, Topre 55g, Topre 55g (aged), NiZ 65g, BKE Redux Extreme, DynaCaps Light, DynaCaps Medium, DynaCaps Heavy.

**Topre-compatible parts** — slider/housing assemblies, including silencing configurations:
Topre Slider Black (bare), Topre Slider Black + 0.3 mm poron silencing ring, Topre Slider Black + 0.5 mm poron silencing ring, Topre Slider Silenced Purple, Topre Slider Type-S, DynaCaps Parts, DynaCaps Slider + 0.3 mm poron, DynaCaps Slider + 0.5 mm silicone.

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
- The measurement is quasi-static by design. It captures the dome's intrinsic force curve; it does not capture rate-dependent effects (e.g., viscoelastic damping of foam silencing rings at real typing speeds). Findings that depend on that distinction are noted below.

### Derived metrics (as computed by the viewer)

All metrics are computed on the run-averaged press curve, lightly smoothed (7-sample moving average) for feature detection only; energy integrates the unsmoothed data.

1. **Collapse Force / Collapse Travel** — the tactile peak: the most prominent local maximum in the first 75% of the stroke (prominence > 2 g against the following minimum).
2. **Valley** — the post-collapse minimum within 1.6 mm after the peak. Not displayed in the viewer, but used to compute Snap %.
3. **Travel** — where the bottom-out wall begins: the first point past the valley where the smoothed press slope exceeds 300 g/mm. Dome bottom-out walls are near-vertical, so this detection is robust.
4. **Total Energy** — trapezoidal integration of the press curve from 0 to Travel, in gf·mm.
5. **Snap %** — (Collapse − Valley) / Collapse × 100.

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
| Topre Slider Black (bare) | 62.9 @ 1.13 | 23.4 | 3.99 | 207.0 |
| + 0.3 mm poron ring | 61.2 @ 0.98 | 23.6 | 3.75 | 195.6 |
| + 0.5 mm poron ring | 67.6 @ 0.79 | 24.9 | 3.62 | 207.0 |

### Findings on silencing rings

The slider series above demonstrates, from measurement rather than folklore:

- **Travel loss ≈ ring thickness, less for poron.** A 0.5 mm poron ring removed 0.37 mm of travel (foam absorbs part of its own thickness under preload); silicone transmits closer to its full thickness.
- **The collapse point arrives earlier** in the measured stroke by roughly the effective ring thickness, consistent with the ring precompressing the dome — the curve begins partway up its intrinsic shape (visible as an elevated force reading in the first hundredths of a millimeter).
- **Measured collapse force goes up, not down.** Precompression alone cannot explain this — a pure preload moves you along the same curve. The increase indicates the ring changes the dome's intrinsic buckling load, consistent with shell-buckling behavior: critical snap-through load is highly sensitive to load distribution and boundary constraint, and the ring loads the dome crown through a wider annulus than the slider's native contact.
- **Quasi-static tactility barely changes; felt tactility does.** Snap % is nearly identical bare vs. 0.5 mm ring in slow-press data, yet thick rings feel markedly less tactile. The perceived loss is dominated by rate-dependent effects — foam damping the snap transient at keystroke speeds — plus the shortened pre-travel before the break. This is why Snap % should be read alongside Collapse Travel and Travel when rings are involved.

A detailed write-up of the testing standard is in progress.

---

## The viewer (`index.html`)

A single self-contained HTML file — no build step, no dependencies to install. Hosted with GitHub Pages from this repo and embedded on [unrealkeyboards.com](https://unrealkeyboards.com/pages/pages-topre-force-curves).

**Features**

- Overlay any combination of test sets; press and return curves, color-coded.
- Bench readout per set: Collapse Force and Travel, Snap %, Total Energy, Travel.
- Single-set view renders the test name and full stat panel directly on the chart; multi-set view renders a legend with compact stats — exports are self-contained and readable without the readout table.
- **Export PNG** — 2× resolution chart with title, markers, guide lines, and stats baked in.
- Toggles: return curve, individual runs (vs. run-averaged), markers (collapse/valley dots + travel line), guide lines (dashed drop lines from collapse point and collapse bottom to both axes).
- Live filter box over the test list; plain text is a contains-match, `*` acts as a wildcard (`t*black` matches "Topre Slider Black …").
- Hover crosshair snapped to the 0.005 mm sample grid; shows readings as recorded (full stored precision in individual-runs mode).

**Data loading**

1. On load, the viewer fetches the repo file index from the GitHub git-trees API and groups every `*DataLog_N.csv` by folder — **new test folders pushed to the repo appear automatically with no changes to the viewer.**
2. CSVs are fetched from `raw.githubusercontent.com` on first selection and cached for the session.
3. If GitHub is unreachable (offline, sandboxed embeds, API rate limit), the viewer falls back to an embedded, delta-encoded snapshot of the averaged curves and tags affected rows "snapshot". Live data always takes priority.

**Display conventions**

Grams, gf·mm, and Snap % are rounded to whole numbers — matching run-to-run repeatability rather than implying false precision. Millimeter values show 2 decimals. The X axis is fixed at 4.1 mm (Topre maximum travel is 4.0 mm).

## Adding a new test set

1. Create a folder named for the configuration, e.g. `Deskeys_Blue_49g`. Underscores become spaces in the viewer.
2. Put one CSV per run inside, named `DataLog_1.csv`, `DataLog_2.csv`, … (a `FolderName-` prefix on the filenames is also accepted). Match the column format above.
3. Folder names containing `Slider`, `Type-S`, or `Parts` are grouped under **Topre Compatible Parts** in the viewer; everything else lands under **Domes**.
4. Commit and push. The live viewer picks the set up on next load.

To update the embedded offline snapshot with new sets, regenerate it from the CSVs and replace the `EMBEDDED` constant in `index.html` — this is optional and only affects offline/sandboxed fallback behavior, not the live site.

## Hosting and embedding

- GitHub Pages serves `index.html` from the repo root (`main` branch) at the live URL above. Every push redeploys automatically in about a minute.
- Embed anywhere with an iframe:

```html
<iframe
  src="https://buddyog.github.io/topre-force-curves/"
  title="Topre Force Curve Bench — Unreal Keyboards"
  loading="lazy"
  style="display:block;width:100%;border:0;height:calc(100vh - 160px);min-height:820px;">
</iframe>
```

## Using this data

Exported charts and the data in this repository may be shared with attribution to **BuddyOG / Unreal Keyboards** and a link back to this repository or the live viewer. The viewer's Export PNG button produces self-contained charts with the source branding included.

## Caveats

- Aftermarket and aged parts vary; these curves characterize the specific units tested.
- The bench is quasi-static. Rate-dependent feel (notably foam silencing rings at typing speed) is discussed above but not directly measured.
- Travel detection uses a slope threshold (300 g/mm); pathological curves without a clean bottom-out wall would fall back to end-of-stroke.
