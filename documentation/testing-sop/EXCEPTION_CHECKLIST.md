# Dome-testing exception checklist

When an exception occurs, stop at the first applicable row. Preserve the raw
source files and record what happened. Do not solve an exception by manually
copying or deleting repository CSVs.

| Situation | Required action | Release consequence |
| --- | --- | --- |
| Executable version or hash differs | Stop; obtain the frozen 1.1.4 authority package | No import |
| Rig, logger, calibration, mounting, preload, speed procedure, or firmware changed | Stop and document the change for method review | Not an ordinary same-method addition |
| CSVs from different domes may be mixed | Separate only by confirmed physical provenance; otherwise reacquire | No combined cohort |
| A run fails a hard gate | Preserve and record the failed acquisition; correct the physical/acquisition cause and retest | Failed run excluded |
| Preferred-speed or other advisory note only | Preserve the note; no manual exclusion if hard gates pass | May remain retained |
| Fewer than two runs remain | Reacquire enough runs and rerun the complete cohort | Whole cohort withheld |
| Mixed-population stop | Inspect physical identity and folder composition; do not average or median-filter through it | Whole cohort withheld until resolved |
| RAMP REVIEW warning | Inspect rig, identity, and curves; cancel if a real error may exist; otherwise acknowledge without removing the run | Advisory only |
| No force wall detected | Preserve the null result; never replace it with turnaround or last sample | Metric-local null may be valid |
| Destination folder already exists | Stop; do not delete or overwrite it to force import | Integration/name review required |
| Metadata is unknown or conflicts | Stop integration; obtain the owner-correct value or record null/Unknown | No invented metadata |
| A retest replaces an earlier practical result | Keep the new acquisition identity and explicitly link the retest in history | New evidence epoch required |
| Folder rename is requested | Regenerate every path-bound artifact; do not rename only raw files | New evidence epoch required |
| New dome changes the reference fleet | Create a new perception-index model version and report score deltas | Old index identity cannot be reused |
| Manual viewer/generated-data edit seems necessary | Stop and correct the generator or controlled inputs | No release until regenerated |

For an unresolved case, record it in the change record as `BLOCKED` and do not
commit, tag, or publish the proposed cohort.
