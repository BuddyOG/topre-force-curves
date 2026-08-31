# Operator guide: `test-imp.exe 1.1.4`

This guide documents the released Windows importer used by
`dome-testing-sop-v1`. It supplements, but does not rewrite, the immutable
release ZIP. The ZIP's bundled README contains an older default repository
location. On this workstation, always provide `--github-root` explicitly.

## Frozen identity

- application: `test-imp.exe 1.1.4`
- metrics: `metrics-v4.2`
- intake policy: `intake-qc-v1.4`
- executable SHA-256:
  `351607fffe30eb6da8c7612e3e1bdfad0e3a737804e8f109bbd89c8d1a64854e`
- authority ZIP:
  `canonical-evidence/authority/test-imp-1.1.4-windows-x64.zip`
- ZIP SHA-256:
  `b1ccdaba5c4ec76b7a8516c4e8c8109c26f2cb58b0f60f49a5c5fcf9a031b284`
- ZIP size: 8,283,858 bytes

Verify before use:

```powershell
.\test-imp.exe --version
(Get-FileHash .\test-imp.exe -Algorithm SHA256).Hash.ToLower()
```

The version output must be:

```text
test-imp.exe 1.1.4 (metrics-v4.2; intake-qc-v1.4)
```

The hash must exactly match the executable SHA-256 above.

## Folder preparation

- Work from one source folder outside the repository.
- Include only one dome cohort's `DataLog_*.csv` files.
- Keep the original source folder after import.
- Never combine two dome specimens to obtain the two-run minimum.

## Exact command

For this workstation:

```powershell
.\test-imp.exe --github-root "D:\Documents\Projects\GitHub\topre-force-curves" "Proposed_Dome_Folder"
```

The final quoted value is the new folder name to create under the repository
root. The importer must refuse an existing destination.

Use `--help` to display supported arguments. `--yes` may approve an ordinary
import is not part of this SOP: physical intake is performed interactively so
the operator must see and resolve every cohort decision and RAMP-review prompt.
Do not build automation around options that are not displayed by the released
executable's `--help` contract.

## What the importer checks

The importer applies the declared policy in this order:

1. exact CSV structure and numeric rows;
2. complete monotonic 0.005 mm / 8-step press-and-return trajectory;
3. turnaround, origin, span, completion, timing, and cadence;
4. preferred and hard speed ranges;
5. signal integrity and required landmark validity;
6. possible mixed populations;
7. replicate agreement in Collapse force and position;
8. the minimum of two retained runs; and
9. advisory RAMP repeatability review.

The technical thresholds and equations are published in
`documentation/METHOD.md` and the machine-readable policy. Do not copy a
shortened threshold list into a local checklist and treat it as a replacement
for the importer.

## Decision meanings

**ACCEPT:** the run passed individual gates and belongs to the retained
cohort. Import may proceed only if the cohort retains at least two runs.

**FAIL / EXCLUDE:** the run failed a hard gate or declared owner decision. Do
not manually copy it into the destination.

**INSUFFICIENT:** fewer than two matching runs remain. Withhold the whole
cohort and retest; never release the acceptable singleton.

**MIXED POPULATION:** the candidate files support more than one population.
Stop the whole import. Check for mixed physical domes or incorrectly combined
folders; do not let an averaging/filter step merge the groups.

**PASS + note:** a preferred-range or other advisory condition was recorded,
but the hard acceptance rules passed. Preserve the note in the handoff record.

**RAMP REVIEW:** at least one retained finite RAMP is strictly more than 10%
from the retained conventional median, with at least three finite values. This
is a visual/operational review prompt only. It never removes a run or changes
cohort retention. Acknowledge it only after checking for a real setup,
identity, or acquisition problem.

## What happens on successful import

The importer:

- creates a previously nonexistent destination folder;
- copies accepted CSVs byte for byte;
- renumbers them densely from `DataLog_1.csv`;
- assigns ordered local file times for stable presentation; and
- verifies each copy by SHA-256.

It does not:

- modify the source folder;
- update the metadata workbook or registry;
- record exclusions/retests in the canonical evidence ledger;
- regenerate metrics, curve packs, indices, viewer, or documentation;
- stage, commit, tag, push, or publish Git changes.

## Retired paths

Do not use the old `bench-import.py` workflow or
`generator/domelab_pipeline/importer_core.py`. The latter is intentionally
retired and fails closed. `generator/domelab_pipeline/intake_cli.py` is a
separate repository tool for hash-bound decision manifests; it is not a
replacement acquisition copier and does not activate an imported cohort by
itself.
