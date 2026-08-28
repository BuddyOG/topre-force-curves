#!/usr/bin/env python3
"""Build the frozen, separate subjective-pilot review sidecar.

The Force Curve Bench's canonical mechanical records remain untouched.  This
tool cross-binds the already-audited pilot extracts to canonical test IDs and
emits a small human/machine-readable package.  It deliberately refuses to
replace an existing destination.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import html
import json
import math
from pathlib import Path
import shutil
import tempfile
from typing import Any


PILOT_ID = "subjective-pilot-v1"
EXPECTED_WORKBOOK_SHA256 = (
    "d4bbaad6831ccab1003bcc7e2974ef7100ee32e083fa88f27d468e64d7a323d0"
)
EXPECTED_REPO_COMMIT = "6e86ac1955a0c566c7aae521705e51371992ba8a"
EXPECTED_EVIDENCE_IDENTITY = (
    "7aa8588b50856816b7fce90dd6e743c26c6f16926071123291cb054352b6cd4a"
)
POSITIONS = [f"{number}{letter}" for number in range(1, 6) for letter in "abcde"]
OBJECTIVE_FIELDS = (
    "collapse_force_gf",
    "collapse_travel_mm",
    "valley_force_gf",
    "valley_travel_mm",
    "drop_gf",
    "drop_travel_mm",
    "snap_pct",
    "drop_rate_gf_per_mm",
    "norm_drop_rate_per_mm",
    "steepest_drop_0p10mm_gf_per_mm",
    "ramp_10_90_gf_per_mm",
    "precollapse_work_gf_mm",
    "full_stroke_press_work_gf_mm",
    "travel_mm",
)
METRIC_LABELS = {
    "collapse_force_gf": "Collapse force",
    "ramp_10_90_gf_per_mm": "Ramp",
    "precollapse_work_gf_mm": "Pre-collapse work",
    "full_stroke_press_work_gf_mm": "Press work to force-wall",
    "drop_gf": "Drop",
    "steepest_drop_0p10mm_gf_per_mm": "Steepest 0.10 mm drop",
    "drop_rate_gf_per_mm": "Drop rate",
    "snap_pct": "Snap %",
    "norm_drop_rate_per_mm": "Normalized drop rate",
    "travel_mm": "Detected force-wall onset (canonical field: travel_mm)",
}
LIMITATIONS = [
    "One rater; repeated sessions improve within-rater precision but do not make n=75.",
    "All sessions used the same fixed grid order, so position/order and dome identity are confounded.",
    "The 1–10 endpoints are relative to this selected 25-dome panel, not calibrated perceptual units.",
    "All tactility ratings were 2–10; the pilot contains no linear/off tactility observation.",
    "Associations are exploratory and do not identify causal, independent metric contributions.",
]


class PilotError(RuntimeError):
    pass


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str]) -> None:
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def write_json(path: Path, value: Any) -> None:
    path.write_text(
        json.dumps(value, sort_keys=True, indent=1, ensure_ascii=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def numeric(value: str, label: str) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError) as error:
        raise PilotError(f"{label} is not numeric: {value!r}") from error
    if not math.isfinite(result):
        raise PilotError(f"{label} is not finite")
    return result


def validate_sources(
    workbook: Path,
    observations_path: Path,
    summary_path: Path,
    analysis_path: Path,
    bench_path: Path,
) -> tuple[list[dict[str, str]], list[dict[str, str]], dict[str, Any], dict[str, dict[str, Any]]]:
    for label, path in (
        ("workbook", workbook),
        ("observations", observations_path),
        ("summary", summary_path),
        ("analysis", analysis_path),
        ("canonical bench records", bench_path),
    ):
        if path.is_symlink() or not path.is_file():
            raise PilotError(f"{label} must be an existing regular file: {path}")
    if sha256(workbook) != EXPECTED_WORKBOOK_SHA256:
        raise PilotError("subjective workbook SHA-256 does not match the frozen pilot")

    observations = read_csv(observations_path)
    summary = read_csv(summary_path)
    analysis = json.loads(analysis_path.read_text(encoding="utf-8"))
    bench = json.loads(bench_path.read_text(encoding="utf-8"))
    if not isinstance(bench, list):
        raise PilotError("canonical bench records must be an array")
    records = {
        record["set"]: record
        for record in bench
        if isinstance(record, dict) and record.get("kind") == "dome_baseline"
    }

    if len(observations) != 75 or len(summary) != 25:
        raise PilotError("pilot must contain 75 observations and 25 dome summaries")
    if sorted({row["position"] for row in observations}) != sorted(POSITIONS):
        raise PilotError("observation grid is not the complete 5x5 physical grid")
    if sorted({row["position"] for row in summary}) != sorted(POSITIONS):
        raise PilotError("summary grid is not the complete 5x5 physical grid")
    for position in POSITIONS:
        rows = [row for row in observations if row["position"] == position]
        if sorted(int(row["session"]) for row in rows) != [1, 2, 3]:
            raise PilotError(f"{position} does not have exactly sessions 1, 2 and 3")
    for row in observations:
        for field in ("weight", "tactility"):
            score = numeric(row[field], f"{row['position']} {field}")
            if not 1 <= score <= 10:
                raise PilotError(f"{row['position']} {field} is outside 1–10")

    for row in summary:
        canonical_set = row["canonical_set"]
        record = records.get(canonical_set)
        if record is None:
            raise PilotError(f"no canonical dome record for {canonical_set}")
        provenance = record.get("provenance", {})
        if provenance.get("repo_commit") != EXPECTED_REPO_COMMIT:
            raise PilotError(f"{canonical_set} is not bound to the frozen repository commit")
        if provenance.get("config_hash") != EXPECTED_EVIDENCE_IDENTITY:
            raise PilotError(f"{canonical_set} is not bound to the frozen evidence identity")
        for field in OBJECTIVE_FIELDS:
            actual = numeric(row[field], f"{canonical_set} {field}")
            expected = record.get(field)
            if not isinstance(expected, (int, float)) or isinstance(expected, bool):
                raise PilotError(f"canonical {canonical_set} lacks numeric {field}")
            if not math.isclose(actual, expected, rel_tol=0.0, abs_tol=1e-12):
                raise PilotError(f"objective metric mismatch for {canonical_set} {field}")

    if analysis.get("observation_count") != 75 or analysis.get("dome_count") != 25:
        raise PilotError("analysis counts do not match the frozen pilot")
    if analysis.get("score_bounds") != {
        "weight_min": 1.0,
        "weight_max": 10.0,
        "tactility_min": 2.0,
        "tactility_max": 10.0,
    }:
        raise PilotError("analysis score bounds do not match the audited pilot")
    return observations, summary, analysis, records


def top_rows(analysis: dict[str, Any], outcome: str, count: int = 5) -> list[dict[str, Any]]:
    rows = analysis.get("correlations", {}).get(outcome, [])
    if not isinstance(rows, list) or len(rows) < count:
        raise PilotError(f"analysis lacks {outcome} correlation rows")
    return rows[:count]


def build_html(analysis: dict[str, Any]) -> str:
    def correlation_table(outcome: str) -> str:
        body = "".join(
            "<tr><td>" + html.escape(METRIC_LABELS.get(row["metric"], row["metric"])) +
            "</td><td>" + f"{row['spearman_rho']:.3f}" + "</td></tr>"
            for row in top_rows(analysis, outcome)
        )
        return "<table><thead><tr><th>Mechanical metric</th><th>Spearman ρ</th></tr></thead><tbody>" + body + "</tbody></table>"

    limitations = "".join(f"<li>{html.escape(item)}</li>" for item in LIMITATIONS)
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Dome Lab subjective pilot v1</title>
<style>
:root{{--ink:#1d2421;--muted:#66726d;--line:#dbe2de;--paper:#fbfcfb;--accent:#7048b6}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--paper);color:var(--ink);font:16px/1.55 system-ui,sans-serif}}
main{{max-width:980px;margin:auto;padding:40px 24px 70px}}h1{{font-size:2rem;margin-bottom:.2rem}}h2{{margin-top:2rem}}
.tag{{color:var(--accent);font-weight:700;letter-spacing:.06em;text-transform:uppercase;font-size:.78rem}}
.warning{{border:1px solid var(--line);border-left:5px solid var(--accent);padding:14px 16px;background:white}}
.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:20px}}table{{width:100%;border-collapse:collapse;background:white}}
th,td{{text-align:left;padding:8px 10px;border-bottom:1px solid var(--line)}}th:last-child,td:last-child{{text-align:right}}
a{{color:var(--accent)}}code{{font-size:.9em}}.files a{{margin-right:14px;white-space:nowrap}}
</style></head><body><main>
<div class="tag">Exploratory evidence · {PILOT_ID}</div>
<h1>25-dome subjective pilot</h1>
<p>One rater scored 25 dome assemblies in three fixed-order sessions using the same Topre housing, slider, and conical spring. Weight and tactility sharpness used panel-relative 1–10 scales.</p>
<div class="warning"><strong>Read this first.</strong> The effective sample is 25 domes, not 75. These results describe associations inside this selected panel. They are not causal effects, calibrated perceptual units, population norms, or a tactile on/off classifier.</div>
<h2>Strongest rank associations</h2>
<div class="grid"><section><h3>Perceived weight</h3>{correlation_table('weight')}</section><section><h3>Tactility sharpness</h3>{correlation_table('tactility')}</section></div>
<p>Collapse force led the perceived-weight ranking (ρ = {top_rows(analysis,'weight',1)[0]['spearman_rho']:.3f}). The force-drop family led tactility-sharpness: Drop ρ = {top_rows(analysis,'tactility',1)[0]['spearman_rho']:.3f}. These correlated metric families overlap strongly, so this pilot does not assign independent causal contributions.</p>
<h2>Limits</h2><ul>{limitations}</ul>
<h2>Files</h2><p class="files"><a href="README.md">Methods</a><a href="observations.csv">75 raw ratings</a><a href="dome_summary.csv">25 dome means</a><a href="grid_mapping.json">Explicit 5x5 mapping</a><a href="analysis.json">Analysis results</a><a href="source_identity.json">Provenance</a></p>
<p><a href="../../index.html">Return to Force Curve Bench</a></p>
</main></body></html>
"""


def build_package(
    workbook: Path,
    observations_path: Path,
    summary_path: Path,
    analysis_path: Path,
    bench_path: Path,
    output: Path,
) -> None:
    if output.exists() or output.is_symlink():
        raise PilotError(f"refusing to replace existing output: {output}")
    observations, summary, analysis, records = validate_sources(
        workbook, observations_path, summary_path, analysis_path, bench_path
    )
    summary_by_position = {row["position"]: row for row in summary}
    bound: dict[str, dict[str, str]] = {}
    for position in POSITIONS:
        row = summary_by_position[position]
        record = records[row["canonical_set"]]
        bound[position] = {
            "canonical_set": row["canonical_set"],
            "test_id": record["test_id"],
            "dome_label": row["dome_label"],
        }

    parent = output.parent.resolve()
    parent.mkdir(parents=True, exist_ok=True)
    candidate = Path(tempfile.mkdtemp(prefix="subjective-pilot-", dir=parent))
    try:
        observation_fields = [
            "session", "tab", "date_serial", "time_serial", "position", "dome_label",
            "canonical_set", "test_id", "weight", "tactility",
        ]
        observation_rows = []
        for row in observations:
            link = bound[row["position"]]
            if row["dome_label"] != link["dome_label"]:
                raise PilotError(f"label mismatch at {row['position']}")
            observation_rows.append({**row, **link})
        write_csv(candidate / "observations.csv", observation_rows, observation_fields)

        summary_fields = [
            "position", "dome_label", "canonical_set", "test_id",
            "weight_mean", "weight_sd", "weight_min", "weight_max", "weight_range",
            "tactility_mean", "tactility_sd", "tactility_min", "tactility_max", "tactility_range",
        ]
        summary_rows = []
        for position in POSITIONS:
            row = summary_by_position[position]
            summary_rows.append({key: ({**row, **bound[position]}).get(key, "") for key in summary_fields})
        write_csv(candidate / "dome_summary.csv", summary_rows, summary_fields)

        write_json(candidate / "grid_mapping.json", {
            "mapping_rule": "visual row-major: scoring row A = 1a–1e, B = 2a–2e, through E = 5a–5e",
            "positions": [{"position": position, **bound[position]} for position in POSITIONS],
        })
        curated_analysis = {
            "pilot_id": PILOT_ID,
            "effective_n": 25,
            "rater_count": 1,
            "session_count": 3,
            "fixed_order": True,
            "score_bounds": analysis["score_bounds"],
            "reliability": analysis["reliability"],
            "correlations": analysis["correlations"],
            "session_summary": analysis.get("session_summary", []),
            "metric_display_names": METRIC_LABELS,
            "limitations": LIMITATIONS,
            "modeling_status": "No prediction model or causal contribution estimate is released.",
        }
        write_json(candidate / "analysis.json", curated_analysis)
        source_identity = {
            "pilot_id": PILOT_ID,
            "artifact_role": "exploratory_subjective_pilot",
            "release_eligible": False,
            "workbook_filename": workbook.name,
            "workbook_sha256": EXPECTED_WORKBOOK_SHA256,
            "workbook_included": False,
            "objective_repo_commit": EXPECTED_REPO_COMMIT,
            "objective_evidence_identity": EXPECTED_EVIDENCE_IDENTITY,
            "objective_record_binding": "canonical test_id and set for each of 25 domes",
            "assembly": "Topre housing, Topre slider, and Topre conical spring for every dome",
            "weight_scale": "1 = feather weight; 10 = maximum perceived weight within this 25-dome panel",
            "tactility_scale": "1 = linear/off; 10 = maximum sharpness within this 25-dome panel",
            "raw_source_hashes": {
                "observations_extract_sha256": sha256(observations_path),
                "dome_summary_extract_sha256": sha256(summary_path),
                "analysis_extract_sha256": sha256(analysis_path),
                "canonical_bench_records_sha256": sha256(bench_path),
            },
        }
        write_json(candidate / "source_identity.json", source_identity)
        readme = f"""# Dome Lab subjective pilot v1

This is a separate exploratory sidecar. It does not change any canonical Force
Curve Bench metric, curve, retained-run decision, or release eligibility.

## Protocol

- One rater scored 25 domes in three fixed-order sessions.
- Every dome used the same Topre housing, slider, and conical spring.
- Weight: 1 = feather weight; 10 = the heaviest dome in this panel.
- Tactility: 1 = linear/off; 10 = the sharpest dome in this panel.
- Physical grid mapping is row-major: 1a–1e, then 2a–2e, through 5a–5e.
- Each dome's three-session arithmetic mean is the analysis value; effective n = 25.

## Interpretation

Perceived-weight ranks were associated most strongly with collapse force and the
ramp/work family. Tactility-sharpness ranks were associated most strongly with
the force-drop/Snap family. These are exploratory associations within the
selected panel. They are not causal contributions, calibrated units, population
norms, or predictions for untested domes.

No tactility score was 1, so this dataset cannot evaluate tactile-event presence
versus linear/off behavior.

## Provenance

- Pilot ID: `{PILOT_ID}`
- Workbook SHA-256: `{EXPECTED_WORKBOOK_SHA256}` (workbook intentionally not included)
- Objective commit: `{EXPECTED_REPO_COMMIT}`
- Objective evidence identity: `{EXPECTED_EVIDENCE_IDENTITY}`

See `source_identity.json` for exact source hashes, `grid_mapping.json` for the
explicit orientation, `observations.csv` for all 75 raw ratings,
`dome_summary.csv` for full-precision means, and `analysis.json` for descriptive
statistics and correlations.
"""
        (candidate / "README.md").write_text(readme, encoding="utf-8", newline="\n")
        (candidate / "index.html").write_text(build_html(analysis), encoding="utf-8", newline="\n")

        inventory = []
        for path in sorted(candidate.iterdir(), key=lambda item: item.name):
            if path.is_file():
                inventory.append({"path": path.name, "bytes": path.stat().st_size, "sha256": sha256(path)})
        write_json(candidate / "SHA256SUMS.json", {
            "pilot_id": PILOT_ID,
            "inventory_scope": "all regular files in this directory except SHA256SUMS.json",
            "files": inventory,
        })
        candidate.rename(output)
    finally:
        if candidate.exists():
            shutil.rmtree(candidate)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workbook", required=True)
    parser.add_argument("--observations", required=True)
    parser.add_argument("--summary", required=True)
    parser.add_argument("--analysis", required=True)
    parser.add_argument("--bench-tests", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    try:
        build_package(
            Path(args.workbook), Path(args.observations), Path(args.summary),
            Path(args.analysis), Path(args.bench_tests), Path(args.out),
        )
    except (PilotError, OSError, json.JSONDecodeError) as error:
        print(f"SUBJECTIVE PILOT BUILD FAILED: {error}")
        return 1
    print(f"built {PILOT_ID} -> {Path(args.out).absolute()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
