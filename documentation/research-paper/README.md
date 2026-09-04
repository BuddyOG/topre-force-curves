# Full research-paper roadmap

The full paper is a future evidence synthesis, not a cosmetic expansion of the
existing preprint. **Beyond Snap Ratio**, Version 2.0, is the frozen methods,
bench, canonical-evidence, and exploratory-pilot foundation. The planned paper
adds prospective multi-rater validation only after that study is completed.

## Current foundation

- Preprint 2.0: <https://doi.org/10.5281/zenodo.22167065>
- Research compendium: <https://doi.org/10.5281/zenodo.22167047>
- Force Curve Bench: `fc-3.4`
- EC Parts Builder: `lib-6.1`
- Objective evidence: `metrics-v4.2`, frozen commit `6e86ac1`, evidence
  identity `7aa8588b...d4a`
- Exploratory evidence: `subjective-pilot-v1`, one rater, 25 domes, three
  fixed-order sessions
- Frozen index model: `perception-rank-v1`

## Required sequence

1. **Complete:** freeze and timestamp the prospective protocol and analysis
   plan as `perception-validation-v1` before enrolling anyone.
2. Collect the blinded randomized multi-rater data without changing the
   released indices.
3. Lock, hash, validate, and analyze the blinded data under the frozen plan.
4. Release the code key and run the declared identity-linked analysis.
5. Preserve deidentified data, exclusions, code, environment, figures, tables,
   logs, and hashes in a new versioned evidence deposit.
6. Draft the full manuscript with exploratory and confirmatory results visibly
   separated.
7. Obtain independent technical/statistical review, revise with a change log,
   and release a new preprint version before journal submission if applicable.

## Planned manuscript

1. **Abstract** — objective, apparatus, evidence scale, exploratory pilot,
   prospective design/results, limits, and reproducibility.
2. **Introduction** — why nominal gram ratings and Snap ratio alone are
   insufficient; prior EC-dome work and explicit research questions.
3. **Apparatus and acquisition** — rig, assembly, trajectory, calibration
   limits, raw format, and reproducible version identities.
4. **Intake and canonical evidence** — retained/excluded logic, mixed-
   population handling, cohort aggregation, metadata, and provenance.
5. **Mechanical metrics** — collapse force, ramp, work, drop family,
   force-wall onset, null semantics, and correlated-descriptor warning.
6. **Exploratory pilot** — fixed 25-dome panel, one-rater limitations, rank
   associations, and transparent derivation of the two percentile indices.
7. **Prospective validation** — blinded randomized repeated-measures protocol,
   participants, preregistered analysis, exclusions, and results.
8. **Discussion** — convergence or disagreement across raters, assembly-
   specific interpretation, practical use, and noncausal boundaries.
9. **Limitations and future work** — additional raters/populations,
   precompression, alternate assemblies, repeatability, uncertainty, and
   independent benches.
10. **Data and code availability** — exact DOI, Git tags, hashes, manifests,
    licenses, and redactions.

## Planned tables and figures

- apparatus and frozen method-version table;
- evidence-flow diagram from raw acquisitions to retained cohorts;
- complete mechanical metric definition table;
- pilot panel and strongest rank-association table;
- prospective participant flow and protocol-deviation table;
- participant-level association forest plots for both indices;
- dome-level rating distributions against frozen indices;
- session repeatability and rater heterogeneity figures;
- declared sensitivity analyses; and
- claim-to-evidence and artifact-provenance tables.

See [`CLAIM_MATRIX.md`](CLAIM_MATRIX.md) for wording that is already supported,
wording that remains exploratory, and wording that must wait for new evidence.
