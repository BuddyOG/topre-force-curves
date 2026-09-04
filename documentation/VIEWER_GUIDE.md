# Force Curve Bench Viewer Guide

> **fc-3.5 status:** Control names and workflows in this guide match the
> generator-integrated public viewer. The canonical viewer is
> [https://buddyog.github.io/topre-force-curves/](https://buddyog.github.io/topre-force-curves/),
> and the release tag is `fc-3.5`. Exact current-package hashes are recorded in
> `SITE_RELEASE_MANIFEST.json`, `SHA256SUMS`, and
> `FORCE_CURVE_BENCH_RELEASE_MANIFEST_fc-3.5.json`; the latter records the
> viewer-specific release boundary.

This guide explains how to select tests, compare curves and measurements, use
the comparison profiles, share a selection, and export a chart. For the
calculation rules, use [METHOD.md](METHOD.md). For frozen identities and
artifact authority, use [DATA_PROVENANCE.md](DATA_PROVENANCE.md). Interpretation
boundaries are collected in [LIMITATIONS.md](LIMITATIONS.md).

## 1. Open the viewer

Open the canonical viewer at
[https://buddyog.github.io/topre-force-curves/](https://buddyog.github.io/topre-force-curves/).
The released `index.html` is also usable when opened directly as a local file.

The viewer contains an immutable generated catalog and embedded fallback curve
traces. Network access is used to read the retained raw traces from their exact
pinned Git commit when available. It is not used to discover new tests.

On first load, the force-curve chart asks you to select a test. The sidebar
reports the generated fleet size and retained-run count for that build. The
comparison tabs remain visible even before a test is selected.

## 2. Choose a test

The top navigation keeps the two comparison workspaces separate:

- **Domes** contains measured dome-baseline records.
- **Parts** contains measured part-assembly records.
- **Tests** opens the complete sortable record browser described in the next
  section.

The Domes and Parts sidebars have two top-level disclosures. **Filters** starts
collapsed. **Tests** contains the selectable records and can also be collapsed.
With no active filter, tests are organized under collapsible brand headings,
with the manufacturer shown when it differs from the brand. Brands with
multiple recorded variants or styles can contain a second collapsible level,
such as the Deskeys T1, V1, V2, and V3 groups.

Select a row to add it to the chart. Its selection box and curve use the same
color. Select the row again to remove it.

Expand **Filters** to search by test name and set optional minimum or maximum
ranges. Domes expose Weight Index, Tactility Index, Collapse force, Ramp,
Pre-collapse work, Drop, Snap %, Steepest drop, Drop rate, and detected
force-wall onset. Parts expose the applicable mechanical values plus recorded
precompression; perception indices are not calibrated for part assemblies.

The name search is case-insensitive and operates on the displayed test name. A
record with no value for an active range does not pass that range. While a name
or value filter is active, every matching test is shown in one flat,
left-aligned list with no inherited brand indentation. **Clear filters** clears
the name and every value range without changing the chart selection.

Some dome families have an expandable parent row. Selecting that parent draws
a synthetic average of the member-dome averaged traces. It is a visualization
aid, not a separately measured record, so it does not receive generated scalar
measurements or perception indices. Expand the family and select its individual
members when you need record-level results.

Part rows with an information symbol can show the recorded assembly components.
Hover over the symbol with a mouse, or tap it and then tap elsewhere to close it
on a touch device.

### Selection rules

- You can overlay no more than 10 direct force curves at once. The derived
  comparison tabs can load the complete compatible fleet.
- Dome and part-assembly records cannot be mixed in one comparison. Moving
  between **Domes** and **Parts** automatically clears an incompatible current
  selection.
- Each selected physical dome record is its own test. Similar names or
  appearances do not make specimens interchangeable.
- Individual retained runs are not separate viewer series. Their accepted
  retained set is averaged for the displayed result.

## 3. Use the Tests browser

Choose **Tests** to browse the generated records in a table. It uses the same
name-and-value filter model and filter state as the matching Domes or Parts
sidebar.

Choose **Dome tests** or **Parts tests**. The kinds remain separate because a
part assembly is outside the dome perception-index calibration.

The collapsed **Filters** panel provides a name search, minimum and maximum
ranges for the values available to that record kind, a live “shown of total”
count, and **Clear filters**. Manufacturer, version, and style checkbox filters
are intentionally not duplicated here.

When a minimum or maximum is active, a record with no value for that field does
not pass that range filter.

Choose a column heading to sort. Choose the same heading again to reverse the
order. Numeric missing values sort below finite values in ascending order. The
table keeps its horizontal and vertical scroll position while the sort is
applied.

Choose **Compare** on a row to add it to the chart. The button changes to
**Remove** for that active record. If one source set can carry more than one
semantic record, **Use record** changes which generated record interpretation
is active without changing the raw trace.

The table includes record identity, source set, and measurement cohort. Rows
with the same measurement cohort share acquisition evidence and must not be
treated as independent physical tests.

## 4. Read one force curve

With one test selected, the viewer shows its averaged press and return traces
on the force-curve chart.

- The horizontal axis is absolute press displacement in millimetres.
- The vertical axis is force in gram-force.
- Every series uses one shared fleet-wide absolute horizontal scale. Its normal
  endpoint is 4.0 mm. If a released force-wall marker exceeds 4.0 mm, the
  generator extends the shared endpoint in 0.5 mm steps. This fleet therefore
  uses 0–4.5 mm regardless of the current selection. Recorded turnaround and
  sample length do not enlarge the axis. It is not a normalized-travel axis.
- The force axis expands as needed for the selected data.

The header above a single dome curve reports Weight Index, Tactility Index, and
detected force-wall onset. The default **Simplified** display adds Collapse and
Drop dimensions directly to the curve and intentionally omits a duplicate
measurement strip below the chart.

Open **Graph display** to choose **Detailed** when you want all descriptors:
Ramp, Pre-collapse work, Collapse force, Drop and Snap %, Steepest drop, Drop
rate, detected force-wall onset, and the separate recorded-turnaround test
limit. The same menu can show or hide measurement labels and measurement
visuals independently. The test name, two indices, axes, and force-curve line
remain visible. Weight-family elements are pink, tactility-family elements are
blue, travel-related elements are purple, and the force curve is a separate,
thicker neutral stroke.

The values come from generated scalar measurements. The viewer does not
recalculate them from the visible averaged trace.

### Force-wall marker

When detected, force-wall onset appears as a purple vertical marker and as a
numeric measurement. In a force-curve comparison, **More columns** includes
the measured onset.

Force-wall onset is an operational proxy from the complete measured assembly.
It is not physical or nominal full travel. The recorded turnaround range is
only the extent of the retained acquisitions and is shown separately. If no
force wall satisfies the rule, the viewer says **Not detected** and never uses
the last recorded sample as a substitute.

### Why a marker may not sit exactly on the averaged line feature

The pipeline detects scalar landmarks independently on each retained run and
then takes their arithmetic mean. It builds the displayed averaged curve by a
separate trace-averaging procedure. Averaging can soften or move a visible
feature, so the generated mean marker does not have to coincide perfectly with
the feature you see in the averaged trace.

## 5. Compare force curves

Select two or more compatible tests to overlay their averaged curves. Direct
force-curve overlays are limited to 10 records. A sortable measurement table
appears below the chart.

The compact comparison readout follows the active chart mode. Choose **More
columns** for the remaining measurements and identity fields, or **Fewer
columns** to return to the mode-specific view. Profile and scatter views do not
add a redundant single-selection measurement strip below the graph.

Move the pointer near a curve to emphasize its chart series and its table row.
You can also point at a table row to emphasize the corresponding series. Use
the remove button at the end of a row to remove it from the comparison.

The table preserves three different missing-state meanings:

- **Not detected** for an undetected force wall;
- **Not available** for a measurement that is absent or undefined; and
- **Not calibrated** for perception indices that are intentionally not assigned
  to part assemblies.

## 6. Choose a comparison mode

All five mode controls are visible at all times. If no tests are selected,
opening **Weight profile**, **Tactility profile**, **Force-wall onset**, or
**Weight vs tactility** loads all compatible records automatically. Those
fleet-wide views provide **Clear selection** and **Load all domes** (or **Load
all parts**) controls and keep a fixed graph height regardless of record count.
Returning to **Force curves** requires no more than 10 selected tests.

### Force curves

This is the direct force-versus-displacement overlay. Use it to compare the
shapes and absolute forces of the measured curves. Exact values at the selected
displacement appear in the pointer or touch tooltip.

### Weight profile

The Weight profile compares three weight-family descriptors:

- Collapse force
- Ramp
- Pre-collapse work

Their units are different, so the profile places each raw value at its
percentile position within the frozen 68-dome reference fleet. Tap or hover over
a point to see both the raw value and percentile.

The **Weight Index** itself uses collapse force only:

```text
Weight Index = fleet percentile(full-precision cohort collapse force)
```

It is the percentile of the dome's collapse force compared with the other
domes tested, from 0 (lightest) to 100 (heaviest). The profile's three plotted
points are separate comparisons, not ingredients in a combined score. RAMP
and pre-collapse work remain useful descriptors but are not folded into the
index.

### Tactility profile

The Tactility profile compares four tactility-sharpness-family descriptors:

- Drop
- Snap %
- Steepest drop (the fixed 0.10 mm-window measurement)
- Drop rate

As in the Weight profile, each metric is shown at its own frozen-fleet
percentile because their raw units are not interchangeable. Tap or hover over a
point to see the raw value and percentile.

The **Tactility Index** itself uses force drop only:

```text
Tactility Index = fleet percentile(full-precision cohort force Drop)
```

It is the percentile of the dome's force drop compared with the other domes
tested, from 0 (least sharp) to 100 (sharpest). The profile's four plotted
points are separate comparisons, not ingredients in a combined score. The
other three measurements remain supporting descriptors and are not folded
into the index. A low value does not classify a dome as linear/off; the pilot
contained no linear/off observation.

Spearman rank correlations were used as primary evidence when selecting the
single input for each index; Pearson correlations were secondary descriptions.
Neither set of coefficients is used as a mathematical weight.

### Force-wall onset

This view compares detected force-wall onset without mixing in recorded
turnaround. Individual specimen markers are collected into meaningful assembly
groups such as DynaCaps, Astro Domes, and Deskeys generations. The measured
Topre production-dome mean is shown as a reference context so reduced assembly
travel is visible; it is not a nominal specification, proof of advertised
travel, or a better/worse score. Dome baselines add no test precompression.
Part-assembly records retain their recorded precompression context. Records
with no detected wall remain explicitly unavailable rather than receiving the
last sample position.

### Weight vs tactility

This scatter plot places:

- Weight Index on the horizontal axis; and
- Tactility Index on the vertical axis.

Both axes remain fixed at 0–100. A point farther right has a higher collapse-
force rank in the tested fleet. A point farther up has a higher force-drop rank
in that fleet. Neither direction is a universal quality judgment.

Force-wall onset is kept separate and does not affect either coordinate. It is
shown in the force-curves and dedicated Force-wall-onset views, not as an input
to either profile or scatter coordinate.

The canonical evidence also retains **Press work to force-wall**, the press
integral from the recorded start to the detected wall. It ranked sixth of the
fourteen screened metrics for perceived weight in the pilot
(`Spearman rho = 0.817381`), but it remains a separate full-stroke-effort
descriptor. It is not included in Weight Index because it depends on the
assembly-defined wall endpoint, is unavailable when no wall is detected, and
was highly redundant with collapse force (`rho = 0.900`) and pre-collapse work
(`rho = 0.943`) without evidence of an independent contribution. Its close
screening rank is supporting evidence, not an index coefficient.

Only calibrated dome-baseline records with both indices can be plotted. A
part-assembly selection is reported as **Not calibrated**. A missing dome index
is **Not available** rather than imputed.

## 7. Get exact readings

### Mouse or trackpad

Move across the force-curve plot to show the press displacement and per-series
force readings. Hover near a profile, force-wall, or scatter point to show that
point's details. Hover over a measurement annotation to read its explanation;
hovering the matching description in the Detailed measurement strip emphasizes
the same geometry on the graph.

Leaving the chart clears mouse hover state. Pointer movement repaints the chart
without rebuilding the comparison table, so selecting text in the table is not
interrupted.

### Touch screen or pen

Tap the chart to pin an exact reading at that location. Tap another point to
move it. Tapping an annotation or profile/force-wall/scatter point shows its explanation.
Tap outside the plotted horizontal range to clear the reading. Vertical page
scrolling remains available.

### Keyboard

Selection rows and table-sort controls are buttons. Sidebar group headings can
be focused and toggled with Enter or Space. The generated measurement content
for a single selection is also exposed as document text rather than existing
only as pixels on the canvas.

## 8. Share a comparison

The viewer writes the current selection to the `sel` query parameter after
each add, removal, or record switch. Copy the current address from the browser
to share the same selection.

A human-readable example is:

```text
https://buddyog.github.io/topre-force-curves/?sel=Topre_R1_45g,DynaCaps_Light_35g
```

The browser may percent-encode punctuation when it copies the URL; that is
normal.

The stable form uses the generated source-set key. Display names are also
accepted case-insensitively when a link is opened. Multiple `sel` parameters
and comma-separated selections are accepted.

Most sets have one default record. When a non-default semantic record is
needed, append `@` and its record ID:

```text
https://buddyog.github.io/topre-force-curves/?sel=Some_Set@bt_0042
```

The `@record` suffix changes the generated record interpretation, not the raw
source trace. Copying the address bar is safer than composing a link by hand.
Unknown tokens are ignored. The viewer updates the current history entry rather
than creating a new Back-button entry after every selection change.

A valid link whose first recognized selection is a part assembly opens the
**Parts** workspace automatically before loading the selection.

## 9. Understand live and snapshot traces

The viewer has two trace-source states:

1. **Pinned raw read:** the browser fetches retained CSVs from the exact frozen
   repository commit and averages those traces for display.
2. **Embedded snapshot:** if a pinned read fails or does not answer within the
   timeout, the viewer uses its built-in trace snapshot.

“Pinned raw read” is not a read from a moving main branch. The commit and
retained-run list are fixed in the viewer build.

When an embedded trace is in use, the viewer displays a snapshot notice. The
displayed scalar measurements do not change: generated records supply those
values in both states. The browser never re-analyzes the downloaded or embedded
averaged trace to produce customer-facing measurements.

This design lets the released file remain useful without network access while
keeping its evidence identity visible.

## 10. Export a PNG

Select at least one test, choose the chart mode you want, and choose **Export
PNG**.

The export:

- uses the same chart layout and values as the viewer;
- uses the same Simplified/Detailed choice and label/visual visibility as the
  screen;
- places a faint, large **UNREAL KEYBOARDS** watermark behind the chart;
- renders in the clean light theme even if the viewer is in dark mode;
- targets approximately 3000 pixels of output width;
- includes the Detailed measurement block when that mode displays it; and
- stamps the image with export date/time, bench build, data epoch, pinned
  commit prefix, and site identity.

The filename includes the selected test or comparison dataset, chart mode, and
bench build. The supported mode names are `curves`, `weight-profile`,
`tactility-profile`, `force-wall-onset`, and `index-scatter`.

The current viewer export is a PNG image export. It is not a raw-data export.
The packaged raw evidence is under `canonical-evidence/`, and generated
records and curve packs are under `generated/`.

## 11. Change the theme

Use **Light mode** or **Dark mode** at the bottom of the page. The preference is
stored in the browser when storage is available. Where a dome name identifies
a color, the viewer uses a corresponding semantic curve color; Deskeys V1, V2,
V3, and T1 variants progress from lighter to more saturated treatments.
Physical siblings retain a hue family but receive deterministic lightness
offsets from their stable source identity, so their colors do not depend on
selection order. Unmapped dome and part records use the distinct fallback
palette. Colors are adjusted for legibility in each theme, and PNG exports
remain light for consistent sharing.

The viewer embeds Inter and IBM Plex Mono, so rendering does not require a
third-party font request. Both fonts are licensed under the SIL Open Font
License 1.1; see [Third-party font notice](THIRD_PARTY_NOTICES.md).

On wide Weight profile, Tactility profile, and scatter charts, the legend has a
reserved band beside the plot so it cannot cover data. On narrow screens the
legend moves below the plot.

## 12. Interpret the indices carefully

The pilot used one rater, 25 domes, and three fixed-order sessions. Its fixed
5×5 grid held 25 separate, nominally matched OEM Topre assemblies, each with an
OEM housing, black Topre slider, and OEM conical spring. Dome identity, grid
position, and unit-to-unit assembly variation were confounded; continuity of
each individual assembly across sessions was not separately recorded. Collapse
force had the strongest observed rank association with perceived weight, and
force drop had the strongest observed rank association with tactility
sharpness. Those findings select the index inputs; they are not causal
coefficients.

Weight Index and Tactility Index are percentiles compared with the other domes
tested. They are not predicted 1–10 ratings, universal perceptual units, or
promises about a different assembly. Part assemblies receive no index, and
force-wall onset never enters either equation. See the
[method specification](METHOD.md#pilot-derived-perception-indices) for the full
calculation.

## 13. Troubleshooting

### A selection says snapshot

The pinned raw network read failed or timed out. The viewer is using the
embedded trace. Generated scalar measurements remain the same. Reload when the
network is available if you want a fresh read of the same frozen raw bytes.

### I cannot add a force curve

Check for one of two conditions:

- The current force-curve overlay already has 10 tests. Remove one. The derived
  comparison tabs can load the complete compatible fleet.
- The new test is a different kind when added from **Tests**. Open the matching
  **Domes** or **Parts** workspace, which clears the incompatible selection, or
  remove the current selections manually.

### A profile omits a selection

The record is not calibrated for that profile or a required value is not
available. The viewer does not invent missing percentiles.

### I want to return from a fleet-wide comparison

Choose **Clear selection**, then return to **Force curves** or select only the
records you want. **Clear filters** is different: it clears the sidebar search
and value ranges without removing selected records.

### The force wall says Not detected

No point satisfied the detection rule. This is a valid result, not a request to
substitute the recorded turnaround or last sample.

### The page reports an evidence-integrity error

Stop using the displayed result for comparison and record the full error
message, viewer build, data epoch, and pinned commit shown on the page. The
viewer fails loudly when generated records that should share scalar identity
diverge or when an unexpected fault prevents trustworthy presentation.
