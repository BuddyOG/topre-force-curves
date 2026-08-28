#!/usr/bin/env python3
"""Build and verify Dome Lab canonical-evidence epoch input artifacts.

This script is deliberately limited to Step 2 inputs. It does not import or
modify the Force Curve Bench generator, viewer, templates, repository, or any
previously sealed release tree.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import re
import shutil
import subprocess
from collections import defaultdict
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any


FROZEN_COMMIT = "6e86ac1955a0c566c7aae521705e51371992ba8a"
PRUNE_COMMIT = "8816ffbf80ce7fd349a1a73893ce63cd5b7ad3d2"
PRE_PRUNE_COMMIT = "c632440276254c01daa0543710b4148e6ac218e2"
EPOCH_ID = "canonical-evidence-2026-08-15-6e86ac19"
AUTHORITATIVE_WORKBOOK_SHA256 = (
    "02e85a2fbdc8e025f1445ab8cb7bd830501f755b79d0a755d6ee31e53bca45a4"
)
AUTHORITATIVE_WORKBOOK_BYTES = 13815
AUTHORITATIVE_WORKBOOK_SNAPSHOT_SHA256 = (
    "fee2cc5b217e8ce2600d5e8d778f6dc5eca2abbe15d93a4f983b316ca6e940ea"
)
SUPERSEDED_WORKBOOK_INGESTION = {
    "sha256": "c52393a1d3f33c9c21aa2de35c46cb53914fad0eadcfd4d33b1f7dc72def2921",
    "size_bytes": 13811,
    "status": "superseded_by_final_source_byte_identity",
    "metadata_value_formula_delta": False,
}
EXPECTED_HEADERS = [
    "display_name",
    "manufacturer",
    "brand",
    "style",
    "variant",
    "nominal_weight_g",
    "tested",
]

# Stable semantic identities retained from the previous manifest. These are
# not claims that the bytes stayed the same; several cohorts were explicitly
# retested. The mapping preserves the meaning represented by the test id.
WORKBOOK_LEGACY_LINEAGE = {
    "DynaCaps_Light_35g": ("DynaCaps_Light", "bt_0005"),
    "DynaCaps_Medium_45g": ("DynaCaps_Medium", "bt_0006"),
    "Dynacaps_Heavy_55g": ("Dynacaps_Heavy", "bt_0007"),
    "BKE_Redux_v1_Extreme_01": ("BKE_Redux_Extreme_01", "bt_0008"),
    "NiZ_Black_65g": ("NiZ_65g", "bt_0009"),
    "Sony_BKE_Gray_01": ("Sony_BKE_Gray_01", "bt_0010"),
    # User-confirmed shared physical test: this semantic record represents the
    # HHKB Pro2 45 g dome; bt_0015 represents the black-slider assembly.
    "Topre_HHKB_Pro2_45g": ("Topre_Slider_Black", "bt_0023"),
}

# These 11 current repository cohorts are outside the authoritative workbook.
# Their generator metadata comes only from the previous manifest lineage.
NON_WORKBOOK_LEGACY_IDS = {
    "Sony_BKE_Brown_01": "bt_0012",
    "Sony_BKE_Brown_02": "bt_0013",
    "Sony_BKE_Brown_03": "bt_0014",
    "Topre_Slider_Black": "bt_0015",
    "Topre_Slider_Type-S": "bt_0016",
    "Topre_Slider_Silenced_Purple": "bt_0017",
    "Topre_Slider_Black_Silenced_0.3mm_Poron": "bt_0018",
    "Topre_Slider_Black_Silenced_0.5mm_Poron": "bt_0019",
    "Dynacaps_Slider_0.3mm_Poron": "bt_0020",
    "Dynacaps_Slider_0.5mm_Silicone": "bt_0021",
    "DynaCaps_Parts": "bt_0022",
}

SHARED_EVIDENCE_SETS = ["Topre_HHKB_Pro2_45g", "Topre_Slider_Black"]
SHARED_EVIDENCE_GROUP_ID = "egrp_topre_hhkb_pro2_45g__topre_slider_black"

RETEST_EVENTS = [
    {
        "event_id": "evt_retest_deskeys_carrot_60g",
        "commit": "a78317a7d5d1c1e5f554c8e4c304c16160fc2649",
        "subject": "Deskeys_Carrot_60g_Retest",
        "cohorts": ["Deskeys_Carrot_60g"],
        "mappings": [
            ("Deskeys_Carrot_60g/DataLog_1.csv", "Deskeys_Carrot_60g/DataLog_1.csv"),
            ("Deskeys_Carrot_60g/DataLog_2.csv", "Deskeys_Carrot_60g/DataLog_2.csv"),
            ("Deskeys_Carrot_60g/DataLog_3.csv", None),
            ("Deskeys_Carrot_60g/DataLog_4.csv", "Deskeys_Carrot_60g/DataLog_4.csv"),
        ],
        "interpretation": (
            "Runs 1, 2, and 4 were replaced in place; old run 3 was retired "
            "without a same-event successor. The relationship is established "
            "by the owner-authored commit subject and exact Git diff."
        ),
    },
    {
        "event_id": "evt_retest_dynacaps_light_35g",
        "commit": "d04136ed58daced2818c6e00012cd0d5ce61e306",
        "subject": "DynaCaps_Light_35g_Re-test",
        "cohorts": ["DynaCaps_Light_35g"],
        "mappings": [
            ("DynaCaps_Light_35g/DynaCaps_Light-DataLog_1.csv", "DynaCaps_Light_35g/DataLog_1.csv"),
            ("DynaCaps_Light_35g/DynaCaps_Light-DataLog_2.csv", "DynaCaps_Light_35g/DataLog_2.csv"),
            ("DynaCaps_Light_35g/DynaCaps_Light-DataLog_3.csv", "DynaCaps_Light_35g/DataLog_3.csv"),
        ],
        "interpretation": (
            "Three old acquisitions were removed and three newly named "
            "acquisitions were added in the owner-authored retest commit; "
            "ordinal pairing is explicit in this epoch ledger."
        ),
    },
    {
        "event_id": "evt_retest_sony_bke_gray_01_02",
        "commit": "58f7d88e62c547b187164e11fcc35783837b7484",
        "subject": "Sony_BKE_Gray_Re-Test",
        "cohorts": ["Sony_BKE_Gray_01", "Sony_BKE_Gray_02"],
        "mappings": [
            (f"Sony_BKE_Gray_{unit}/DataLog_{run}.csv", f"Sony_BKE_Gray_{unit}/DataLog_{run}.csv")
            for unit in ("01", "02")
            for run in (1, 2, 3)
        ],
        "interpretation": (
            "All six paths were overwritten by the owner-authored Gray retest "
            "commit. Both physical-unit labels were retested together, resolving "
            "the prior path-and-hash-bound Gray 02 exclusion for this new epoch."
        ),
    },
]

OEM_TOPRE_TRANSITION = {
    "event_id": "evt_oem_topre_collection_transition",
    "commit": "c632440276254c01daa0543710b4148e6ac218e2",
    "subject": "OEM Topre Batch",
    "retired_cohorts": ["Topre_30g", "Topre_45g", "Topre_55g", "Topre_55g_Aged"],
    "introduced_cohorts": [
        "Topre_GX1_45g",
        "Topre_HHKB_Pro2_45g",
        "Topre_R1_30g",
        "Topre_R1_45g",
        "Topre_R1_55g",
        "Topre_R2_30g",
        "Topre_R2_45g",
        "Topre_R2_55g",
        "Topre_RGB_45g",
    ],
}

POST_PRUNE_RETEST_EVENTS = [
    {
        "event_id": "evt_retest_topre_r2_45g",
        "commit": FROZEN_COMMIT,
        "subject": "Topre_45g_R2_Retest",
        "cohorts": ["Topre_R2_45g"],
        "authority": {
            "scope": "exact_git_object_transition_only",
            "authoritative_for_git_object_transition": True,
            "authoritative_for_specimen_identity": False,
            "authoritative_for_quality_reason": False,
            "authoritative_for_scientific_equivalence": False,
        },
        "mappings": [
            ("Topre_R2_45g/DataLog_1.csv", "Topre_R2_45g/DataLog_1.csv"),
            ("Topre_R2_45g/DataLog_2.csv", "Topre_R2_45g/DataLog_2.csv"),
            ("Topre_R2_45g/DataLog_3.csv", None),
        ],
        "interpretation": (
            "The commit diff replaces DataLog_1.csv and DataLog_2.csv in place and "
            "retires DataLog_3.csv. No specimen, cause, quality, or equivalence claim "
            "is inferred beyond those exact Git object transitions."
        ),
    }
]

PRUNED_RUNS = [
    {
        "path": "BKE_Redux_v1_Heavy_03/DataLog_1.csv",
        "sha256": "d1a99616ab6f503b64e1f926edfff50067b316230ef7264a5fa298637e3b0c9d",
        "dimension": "collapse_force_gf",
        "absolute_deviation": 2.016,
        "tolerance": 1.840,
        "unit": "gf",
        "reason": "collapse-force deviation 2.016 gf exceeded the 1.840 gf cohort tolerance",
    },
    {
        "path": "Dynacaps_Heavy_55g/DynaCaps_Heavy-DataLog_1.csv",
        "sha256": "530b1dfb588d63ecde2f3c1ff287a97ac1159c20495ee0b4a3ab2e8bf3aeff8f",
        "dimension": "collapse_position_mm",
        "absolute_deviation": 0.065,
        "tolerance": 0.050,
        "unit": "mm",
        "reason": "collapse-position deviation 0.065 mm exceeded the 0.050 mm cohort tolerance",
    },
    {
        "path": "Dynacaps_Slider_0.3mm_Poron/Dynacaps_Slider_0.3mm_Poron-DataLog_2.csv",
        "sha256": "e66def887e82c55ddfa618f68ef99fe85e9f74c4d8b1ad12d4c636cb5170bb4e",
        "dimension": "collapse_position_mm",
        "absolute_deviation": 0.052,
        "tolerance": 0.050,
        "unit": "mm",
        "reason": "collapse-position deviation 0.052 mm exceeded the 0.050 mm cohort tolerance",
    },
    {
        "path": "Dynacaps_Slider_0.5mm_Silicone/Dynacaps_Slider_0.5mm_Silicone-DataLog_3.csv",
        "sha256": "2ec175f45b59ace28c98d3067eb97407d437e018859b20d9f940eb712d61beb2",
        "dimension": "collapse_position_mm",
        "absolute_deviation": 0.055,
        "tolerance": 0.050,
        "unit": "mm",
        "reason": "collapse-position deviation 0.055 mm exceeded the 0.050 mm cohort tolerance",
    },
    {
        "path": "NiZ_Black_65g/NiZ_65g-DataLog_1.csv",
        "sha256": "b8b27c0fdd5dec965c65dc5a8b2d8d78dd7c1392a27f61dbd78d266e45366df8",
        "dimension": "collapse_position_mm",
        "absolute_deviation": 0.065,
        "tolerance": 0.050,
        "unit": "mm",
        "reason": "collapse-position deviation 0.065 mm exceeded the 0.050 mm cohort tolerance",
    },
    {
        "path": "Sony_BKE_Brown_01/DataLog_1.csv",
        "sha256": "fe0b80ba13123e4cb328df6f1740e53da81a11d7476a6f35a3ceace431eece51",
        "dimension": "collapse_force_gf",
        "absolute_deviation": 1.121,
        "tolerance": 1.050,
        "unit": "gf",
        "reason": "collapse-force deviation 1.121 gf exceeded the 1.050 gf cohort tolerance",
    },
    {
        "path": "Topre_Slider_Black_Silenced_0.3mm_Poron/Topre_Slider_Black_Silenced_0.3mm_Poron-DataLog_5.csv",
        "sha256": "3d3899605efdd4822c8d72780bde39ec4c2ac297bfb8b2e04f65db2df6d2723a",
        "dimension": "collapse_position_mm",
        "absolute_deviation": 0.075,
        "tolerance": 0.050,
        "unit": "mm",
        "reason": "collapse-position deviation 0.075 mm exceeded the 0.050 mm cohort tolerance",
    },
    {
        "path": "Topre_Slider_Black_Silenced_0.5mm_Poron/Topre_Slider_Black_Silenced_0.5mm_Poron-DataLog_4.csv",
        "sha256": "5270e6c271db2977b99a433b77c5743c3a48e94915283edeb34cb14f5036c2a2",
        "dimension": "collapse_position_mm",
        "absolute_deviation": 0.075,
        "tolerance": 0.050,
        "unit": "mm",
        "reason": "collapse-position deviation 0.075 mm exceeded the 0.050 mm cohort tolerance",
    },
    {
        "path": "Topre_Slider_Silenced_Purple/Topre_Slider_Silenced_Purple-DataLog_3.csv",
        "sha256": "958ba019a2df2fcff461d561ccf2890dc1c8b6c241de1be95ccbdc4e4f28aa5b",
        "dimension": "collapse_position_mm",
        "absolute_deviation": 0.140,
        "tolerance": 0.050,
        "unit": "mm",
        "reason": "collapse-position deviation 0.140 mm exceeded the 0.050 mm cohort tolerance",
    },
]


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def json_bytes(value: Any) -> bytes:
    return (json.dumps(value, indent=2, ensure_ascii=False) + "\n").encode("utf-8")


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(json_bytes(value))


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field) for field in fieldnames})


def git(repo: Path, args: list[str]) -> bytes:
    return subprocess.check_output(["git", "-C", str(repo), *args])


def git_text(repo: Path, args: list[str]) -> str:
    return git(repo, args).decode("utf-8", errors="strict").strip()


def git_blob(repo: Path, oid: str) -> bytes:
    return git(repo, ["cat-file", "blob", oid])


def ls_tree(repo: Path, commit: str) -> list[dict[str, Any]]:
    records = []
    for raw in git(repo, ["ls-tree", "-r", "-z", commit]).split(b"\0"):
        if not raw:
            continue
        header, path_bytes = raw.split(b"\t", 1)
        mode, object_type, oid = header.decode("ascii").split(" ")
        path = path_bytes.decode("utf-8")
        payload = git_blob(repo, oid)
        records.append(
            {
                "path": path,
                "mode": mode,
                "git_object_type": object_type,
                "git_blob_oid": oid,
                "sha256": sha256_bytes(payload),
                "size_bytes": len(payload),
            }
        )
    return records


def ls_tree_scoped(repo: Path, commit: str, prefixes: list[str]) -> list[dict[str, Any]]:
    args = ["ls-tree", "-r", "-z", commit]
    if prefixes:
        args.extend(["--", *prefixes])
    records = []
    for raw in git(repo, args).split(b"\0"):
        if not raw:
            continue
        header, path_bytes = raw.split(b"\t", 1)
        mode, object_type, oid = header.decode("ascii").split(" ")
        path = path_bytes.decode("utf-8")
        payload = git_blob(repo, oid)
        records.append(
            {
                "path": path,
                "mode": mode,
                "git_object_type": object_type,
                "git_blob_oid": oid,
                "sha256": sha256_bytes(payload),
                "size_bytes": len(payload),
            }
        )
    return records


def blob_record_at(repo: Path, commit: str, path: str) -> dict[str, Any] | None:
    try:
        line = git_text(repo, ["ls-tree", commit, "--", path])
    except subprocess.CalledProcessError:
        return None
    if not line:
        return None
    match = re.fullmatch(r"([0-9]+) blob ([0-9a-f]+)\t(.+)", line)
    if not match or match.group(3) != path:
        raise RuntimeError(f"Unexpected ls-tree response for {commit}:{path}: {line!r}")
    payload = git_blob(repo, match.group(2))
    return {
        "path": path,
        "git_blob_oid": match.group(2),
        "sha256": sha256_bytes(payload),
        "size_bytes": len(payload),
    }


def posix_set(path: str) -> str:
    parts = PurePosixPath(path).parts
    if len(parts) < 2:
        raise RuntimeError(f"Raw acquisition path has no cohort directory: {path}")
    return parts[0]


def slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_")


def clean_cell(value: Any) -> Any:
    if isinstance(value, str):
        stripped = value.strip()
        return stripped if stripped else None
    if isinstance(value, float) and value.is_integer():
        return int(value)
    return value


def parse_workbook_snapshot(snapshot_path: Path) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))
    if snapshot.get("snapshot_format") != "artifact-tool-xlsx-values-v1":
        raise RuntimeError("Workbook snapshot was not produced by the bundled artifact-tool extractor")
    if snapshot.get("sheet_count") != 1:
        raise RuntimeError(f"Expected one worksheet, found {snapshot.get('sheet_count')}")
    sheet = snapshot["sheets"][0]
    if sheet.get("name") != "Untested Domes" or sheet.get("used_address") != "A1:G80":
        raise RuntimeError(f"Unexpected workbook shape: {sheet.get('name')} {sheet.get('used_address')}")
    values = sheet["values"]
    headers = [clean_cell(value) for value in values[0]]
    if headers != EXPECTED_HEADERS:
        raise RuntimeError(f"Unexpected workbook headers: {headers!r}")
    rows = []
    for row_number, values_row in enumerate(values[1:], start=2):
        if len(values_row) != len(headers):
            raise RuntimeError(f"Workbook row {row_number} has {len(values_row)} cells")
        record = {header: clean_cell(value) for header, value in zip(headers, values_row)}
        record["workbook_row"] = row_number
        if record["tested"] not in {"YES", "NO"}:
            raise RuntimeError(f"Workbook row {row_number} has invalid tested value {record['tested']!r}")
        if not record["display_name"]:
            raise RuntimeError(f"Workbook row {row_number} has no display_name")
        rows.append(record)
    if len(rows) != 79:
        raise RuntimeError(f"Expected 79 metadata rows, found {len(rows)}")
    if any(any(cell not in (None, "") for cell in formula_row) for formula_row in sheet["formulas"]):
        raise RuntimeError("Metadata workbook unexpectedly contains formulas")
    return rows, snapshot


def old_manifest_index(old_manifest: dict[str, Any]) -> tuple[dict[str, list[dict[str, Any]]], dict[str, dict[str, Any]]]:
    by_set: dict[str, list[dict[str, Any]]] = defaultdict(list)
    by_id = {}
    for record in old_manifest["tests"]:
        by_set[record["set"]].append(record)
        if record.get("test_id"):
            by_id[record["test_id"]] = record
    return dict(by_set), by_id


def reset_derived_metadata(metadata: dict[str, Any]) -> dict[str, Any]:
    current = deepcopy(metadata)
    # These values describe generated epoch results, not stable specimen or
    # assembly identity. Carrying old values into the new evidence epoch would
    # silently misstate the freshly generated data.
    current["travel_dev_mm"] = None
    current["flag_travel"] = None
    return current


def workbook_metadata(row: dict[str, Any], legacy_record: dict[str, Any] | None) -> tuple[dict[str, Any], dict[str, Any] | None]:
    legacy_snapshot = deepcopy(legacy_record["metadata"]) if legacy_record else None
    if legacy_snapshot:
        metadata = reset_derived_metadata(legacy_snapshot)
    else:
        dome_id = f"dome::{slug(row['display_name'])}"
        metadata = {
            "name": row["display_name"],
            "kind": "dome_baseline",
            "tested_part": dome_id,
            "dome": dome_id,
            "slider": "slider::topre",
            "silencing_ring": None,
            "housing": "housing::topre",
            "conical_spring": "conical_spring::topre",
            "is_baseline": False,
            "travel_dev_mm": None,
            "precompression_mm": 0.0,
            "flag_travel": None,
            "status": "pending_review",
            "notes": (
                "Catalog identity is authoritative from untested-domes_v2.xlsx. "
                "Standard bench assembly fields are the generator's dome-cohort convention, "
                "not additional claims made by the workbook."
            ),
        }

    # The workbook is authoritative for all seven catalog columns. `name` is
    # deliberately updated from its display_name value so a stale legacy label
    # cannot override the user's correction.
    metadata.update(
        {
            "name": row["display_name"],
            "display_name": row["display_name"],
            "manufacturer": row["manufacturer"],
            "brand": row["brand"],
            "style": row["style"],
            "variant": row["variant"],
            "nominal_weight_g": row["nominal_weight_g"],
            "tested": True,
            "metadata_source": "authoritative_workbook",
            "metadata_source_locator": (
                f"untested-domes_v2.xlsx#'Untested Domes'!A{row['workbook_row']}:G{row['workbook_row']}"
            ),
            "metadata_override_applied": True,
            "status": "verified",
            "evidence_alias_group": (
                SHARED_EVIDENCE_GROUP_ID
                if row["display_name"] == "Topre_HHKB_Pro2_45g"
                else None
            ),
            "evidence_alias_role": (
                "dome_semantic"
                if row["display_name"] == "Topre_HHKB_Pro2_45g"
                else None
            ),
        }
    )

    # The HHKB semantic record is the dome interpretation of the shared test;
    # it must not inherit the slider-assembly tested_part from bt_0015.
    if row["display_name"] == "Topre_HHKB_Pro2_45g":
        dome_id = "dome::topre_hhkb_pro2_45g"
        metadata.update(
            {
                "kind": "dome_baseline",
                "tested_part": dome_id,
                "dome": dome_id,
                "is_baseline": False,
                "status": "verified",
                "notes": (
                    "Dome interpretation of the user-confirmed shared HHKB Pro2 / black-slider "
                    "physical test. Four unique acquisitions are shared with bt_0015."
                ),
            }
        )
    return metadata, legacy_snapshot


def semantic_record(
    *,
    test_id: str,
    set_name: str,
    metadata: dict[str, Any],
    metadata_source: dict[str, Any],
    legacy_snapshot: dict[str, Any] | None,
    raw_rows: list[dict[str, Any]],
    acquisitions: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    shared = set_name in SHARED_EVIDENCE_SETS
    expected_runs = []
    for raw in sorted(raw_rows, key=lambda item: item["path"]):
        acquisition_id = f"acq_sha256:{raw['sha256']}"
        aliases = acquisitions[acquisition_id]["raw_path_aliases"]
        expected_runs.append(
            {
                "path": raw["path"],
                "sha256": raw["sha256"],
                "git_blob_oid": raw["git_blob_oid"],
                "bytes": raw["size_bytes"],
                "acquisition_id": acquisition_id,
                "path_role": "shared_alias" if len(aliases) > 1 else "direct",
            }
        )
    measurement_cohort_id = (
        "mc_topre_hhkb_pro2_45g__topre_slider_black"
        if shared
        else f"mc_{set_name}"
    )
    record = {
        "test_id": test_id,
        "set": set_name,
        "measurement_cohort_id": measurement_cohort_id,
        "metadata": metadata,
        "metadata_provenance": metadata_source,
        "legacy_metadata_snapshot": legacy_snapshot,
        "expected_runs": expected_runs,
        "disposition": "include",
        "acquisition_group_id": SHARED_EVIDENCE_GROUP_ID if shared else f"egrp_{slug(set_name)}",
        "unique_acquisition_count": len({run["acquisition_id"] for run in expected_runs}),
        "independence_key": SHARED_EVIDENCE_GROUP_ID if shared else f"egrp_{slug(set_name)}",
    }
    return record


def transition_record(repo: Path, parent: str, commit: str, old_path: str | None, new_path: str | None, frozen_inventory: dict[str, dict[str, Any]]) -> dict[str, Any]:
    old_blob = blob_record_at(repo, parent, old_path) if old_path else None
    new_blob = blob_record_at(repo, commit, new_path) if new_path else None
    if old_path and old_blob is None:
        raise RuntimeError(f"Missing expected predecessor blob {parent}:{old_path}")
    if new_path and new_blob is None:
        raise RuntimeError(f"Missing expected replacement blob {commit}:{new_path}")
    action = "retired_without_replacement" if new_blob is None else ("replaced_in_place" if old_path == new_path else "replaced_and_renamed")
    if old_blob and new_blob and old_blob["sha256"] == new_blob["sha256"]:
        raise RuntimeError(f"Retest transition did not change bytes: {old_path} -> {new_path}")
    return {
        "action": action,
        "predecessor": old_blob,
        "successor": new_blob,
        "successor_present_unchanged_at_frozen_commit": (
            new_blob is not None
            and new_path in frozen_inventory
            and frozen_inventory[new_path]["sha256"] == new_blob["sha256"]
        ),
    }


def build_oem_topre_transition(
    repo: Path, frozen_inventory: dict[str, dict[str, Any]]
) -> dict[str, Any]:
    definition = OEM_TOPRE_TRANSITION
    commit = definition["commit"]
    parent = git_text(repo, ["rev-parse", f"{commit}^"])
    subject = git_text(repo, ["show", "-s", "--format=%s", commit])
    if subject != definition["subject"]:
        raise RuntimeError(f"Unexpected OEM Topre commit subject: {subject!r}")

    retired = [
        row
        for row in ls_tree_scoped(repo, parent, definition["retired_cohorts"])
        if row["path"].lower().endswith(".csv")
    ]
    retired_after = [
        row
        for row in ls_tree_scoped(repo, commit, definition["retired_cohorts"])
        if row["path"].lower().endswith(".csv")
    ]
    introduced_before = [
        row
        for row in ls_tree_scoped(repo, parent, definition["introduced_cohorts"])
        if row["path"].lower().endswith(".csv")
    ]
    introduced = [
        row
        for row in ls_tree_scoped(repo, commit, definition["introduced_cohorts"])
        if row["path"].lower().endswith(".csv")
    ]
    if len(retired) != 15 or retired_after:
        raise RuntimeError(
            f"OEM Topre retired collection mismatch: before={len(retired)}, after={len(retired_after)}"
        )
    if introduced_before or len(introduced) != 25:
        raise RuntimeError(
            "OEM Topre introduced collection mismatch: "
            f"before={len(introduced_before)}, after={len(introduced)}"
        )

    retired_objects = []
    for row in sorted(retired, key=lambda item: item["path"]):
        retired_objects.append(
            {
                "path": row["path"],
                "git_blob_oid": row["git_blob_oid"],
                "sha256": row["sha256"],
                "size_bytes": row["size_bytes"],
                "present_at_parent": True,
                "present_at_transition_commit": False,
                "present_at_frozen_commit": row["path"] in frozen_inventory,
            }
        )

    introduced_objects = []
    for row in sorted(introduced, key=lambda item: item["path"]):
        declared_aliases = []
        if row["path"].startswith("Topre_HHKB_Pro2_45g/"):
            alias_path = row["path"].replace(
                "Topre_HHKB_Pro2_45g/", "Topre_Slider_Black/", 1
            )
            alias_blob = blob_record_at(repo, parent, alias_path)
            if alias_blob is None or alias_blob["git_blob_oid"] != row["git_blob_oid"]:
                raise RuntimeError(
                    f"OEM Topre HHKB path lacks its exact pre-existing slider alias: {row['path']}"
                )
            declared_aliases.append(alias_path)
        frozen = frozen_inventory.get(row["path"])
        frozen_epoch_object = (
            {
                "path": frozen["path"],
                "git_blob_oid": frozen["git_blob_oid"],
                "sha256": frozen["sha256"],
                "size_bytes": frozen["size_bytes"],
            }
            if frozen is not None
            else None
        )
        if frozen is None:
            later_epoch_disposition = "retired_in_later_commit"
        elif frozen["git_blob_oid"] == row["git_blob_oid"]:
            later_epoch_disposition = "present_unchanged"
        else:
            later_epoch_disposition = "replaced_in_later_commit"
        introduced_objects.append(
            {
                "path": row["path"],
                "git_blob_oid": row["git_blob_oid"],
                "sha256": row["sha256"],
                "size_bytes": row["size_bytes"],
                "present_at_parent": False,
                "present_at_transition_commit": True,
                "present_unchanged_at_frozen_commit": (
                    frozen is not None
                    and frozen["git_blob_oid"] == row["git_blob_oid"]
                    and frozen["sha256"] == row["sha256"]
                ),
                "later_epoch_disposition": later_epoch_disposition,
                "frozen_epoch_object": frozen_epoch_object,
                "declared_preexisting_same_blob_paths": declared_aliases,
            }
        )

    retired_55g = [
        row for row in retired_objects if row["path"].startswith("Topre_55g/")
    ]
    if len(retired_55g) != 4:
        raise RuntimeError("Expected four raw objects in the retired generic Topre_55g cohort")

    return {
        "event_id": definition["event_id"],
        "event_type": "non_authoritative_collection_transition",
        "commit": commit,
        "parent_commit": parent,
        "commit_tree_oid": git_text(repo, ["rev-parse", f"{commit}^{{tree}}"]),
        "parent_tree_oid": git_text(repo, ["rev-parse", f"{parent}^{{tree}}"]),
        "commit_subject": subject,
        "authority": {
            "scope": "descriptive_git_history_only",
            "authoritative_for_specimen_identity": False,
            "authoritative_for_scientific_equivalence": False,
            "authoritative_for_membership": False,
            "authoritative_for_retest_satisfaction": False,
        },
        "retired_cohorts": definition["retired_cohorts"],
        "introduced_cohorts": definition["introduced_cohorts"],
        "retired_raw_objects": retired_objects,
        "introduced_raw_objects": introduced_objects,
        "counts": {
            "retired_raw_paths": len(retired_objects),
            "retired_unique_git_blobs": len(
                {row["git_blob_oid"] for row in retired_objects}
            ),
            "introduced_raw_paths": len(introduced_objects),
            "introduced_unique_git_blobs": len(
                {row["git_blob_oid"] for row in introduced_objects}
            ),
            "introduced_git_blobs_not_present_in_parent": sum(
                not row["declared_preexisting_same_blob_paths"]
                for row in introduced_objects
            ),
            "introduced_paths_aliasing_preexisting_slider_blobs": sum(
                bool(row["declared_preexisting_same_blob_paths"])
                for row in introduced_objects
            ),
        },
        "prior_topre_55g_no_retest_decision": {
            "decision_scope": "retired generic cohort Topre_55g",
            "source": "owner task history; not encoded in the repository commit",
            "retired_raw_objects": retired_55g,
            "epoch_effect": (
                "The generic Topre_55g cohort is absent from the frozen epoch, so its "
                "no-retest decision is historical and does not govern any introduced OEM cohort."
            ),
            "decision_was_satisfied_by_this_commit": False,
        },
        "identity_mapping": None,
        "inference_prohibition": (
            "Do not infer a one-to-one specimen, run, or cohort mapping between any retired "
            "generic Topre cohort and any introduced R1, R2, HHKB, RGB, or GX1 cohort. "
            "The commit does not establish that the old Topre_55g no-retest decision was "
            "satisfied by, transferred to, or reversed for any introduced OEM specimen."
        ),
        "interpretation": (
            "Commit-level collection history only: four generic Topre cohorts (15 exact raw "
            "objects) were removed while nine specifically labeled OEM cohorts (25 paths and 25 "
            "distinct blobs within the introduced collection) were added. Four HHKB blobs already "
            "existed under black-slider paths, so 21 blob identities were new to the parent tree. "
            "No specimen equivalence is asserted."
        ),
        "basis": "exact parent/commit Git trees and blob identities",
    }


def build_event_ledger(repo: Path, frozen_inventory: dict[str, dict[str, Any]]) -> dict[str, Any]:
    events = []
    for definition in RETEST_EVENTS:
        commit = definition["commit"]
        parent = git_text(repo, ["rev-parse", f"{commit}^"])
        actual_subject = git_text(repo, ["show", "-s", "--format=%s", commit])
        if actual_subject != definition["subject"]:
            raise RuntimeError(f"Unexpected retest commit subject for {commit}: {actual_subject!r}")
        transitions = [
            transition_record(repo, parent, commit, old_path, new_path, frozen_inventory)
            for old_path, new_path in definition["mappings"]
        ]
        events.append(
            {
                "event_id": definition["event_id"],
                "event_type": "retest_supersession",
                "commit": commit,
                "parent_commit": parent,
                "commit_subject": actual_subject,
                "cohorts": definition["cohorts"],
                "interpretation": definition["interpretation"],
                "basis": "owner-authored commit subject plus exact Git blob transition",
                "transitions": transitions,
            }
        )

    events.append(build_oem_topre_transition(repo, frozen_inventory))

    prune_parent = git_text(repo, ["rev-parse", f"{PRUNE_COMMIT}^"])
    if prune_parent != PRE_PRUNE_COMMIT:
        raise RuntimeError(f"Frozen commit parent changed: expected {PRE_PRUNE_COMMIT}, found {prune_parent}")
    exclusions = []
    for definition in PRUNED_RUNS:
        path = definition["path"]
        old_blob = blob_record_at(repo, PRE_PRUNE_COMMIT, path)
        if old_blob is None:
            raise RuntimeError(f"Pruned run is absent from pre-prune commit: {path}")
        if old_blob["sha256"] != definition["sha256"]:
            raise RuntimeError(f"Pruned-run audit hash mismatch for {path}")
        if blob_record_at(repo, FROZEN_COMMIT, path) is not None:
            raise RuntimeError(f"Pruned run remains in frozen commit: {path}")
        cohort = posix_set(path)
        sibling_count = len([item for item in frozen_inventory.values() if item["path"].endswith(".csv") and posix_set(item["path"]) == cohort])
        exclusions.append(
            {
                **definition,
                "git_blob_oid": old_blob["git_blob_oid"],
                "size_bytes": old_blob["size_bytes"],
                "cohort": cohort,
                "decision": "exclude_and_prune_before_epoch",
                "current_epoch_status": "absent_from_frozen_commit",
                "retained_sibling_run_count_at_frozen_commit": sibling_count,
                "reason_source": (
                    "Pre-epoch test-imp.exe 1.1.4 importer audit supplied in the owner task; "
                    "path and SHA-256 independently verified against the pre-prune Git commit."
                ),
            }
        )
    events.append(
        {
            "event_id": "evt_prune_failed_importer_runs",
            "event_type": "quality_exclusion_and_prune",
            "commit": PRUNE_COMMIT,
            "parent_commit": PRE_PRUNE_COMMIT,
            "commit_subject": git_text(repo, ["show", "-s", "--format=%s", PRUNE_COMMIT]),
            "policy": "test-imp.exe 1.1.4 cohort check",
            "interpretation": (
                "Nine exact path-and-hash-bound runs failed the cohort force/position tolerances "
                "and were removed before the evidence epoch was frozen. They remain in history, "
                "not in current canonical raw membership."
            ),
            "exclusions": exclusions,
        }
    )

    for definition in POST_PRUNE_RETEST_EVENTS:
        commit = definition["commit"]
        parent = git_text(repo, ["rev-parse", f"{commit}^"])
        actual_subject = git_text(repo, ["show", "-s", "--format=%s", commit])
        if actual_subject != definition["subject"]:
            raise RuntimeError(
                f"Unexpected post-prune retest commit subject for {commit}: {actual_subject!r}"
            )
        transitions = [
            transition_record(
                repo, parent, commit, old_path, new_path, frozen_inventory
            )
            for old_path, new_path in definition["mappings"]
        ]
        events.append(
            {
                "event_id": definition["event_id"],
                "event_type": "retest_supersession",
                "commit": commit,
                "parent_commit": parent,
                "commit_subject": actual_subject,
                "cohorts": definition["cohorts"],
                "authority": definition["authority"],
                "interpretation": definition["interpretation"],
                "basis": "exact parent/commit Git diff and blob identities",
                "transitions": transitions,
            }
        )
    return {
        "ledger_version": 1,
        "epoch_id": EPOCH_ID,
        "frozen_commit": FROZEN_COMMIT,
        "events": events,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", required=True, type=Path)
    parser.add_argument("--raw-cache", required=True, type=Path)
    parser.add_argument("--workbook", required=True, type=Path)
    parser.add_argument("--workbook-snapshot", required=True, type=Path)
    parser.add_argument("--legacy-manifest", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    repo = args.repo.resolve()
    raw_cache = args.raw_cache.resolve()
    workbook = args.workbook.resolve()
    workbook_snapshot_path = args.workbook_snapshot.resolve()
    legacy_manifest_path = args.legacy_manifest.resolve()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)

    if git_text(repo, ["rev-parse", FROZEN_COMMIT]) != FROZEN_COMMIT:
        raise RuntimeError("Frozen commit is not available in the source repository")
    frozen_subject = git_text(repo, ["show", "-s", "--format=%s", FROZEN_COMMIT])
    frozen_commit_time = git_text(repo, ["show", "-s", "--format=%cI", FROZEN_COMMIT])
    frozen_tree_oid = git_text(repo, ["rev-parse", f"{FROZEN_COMMIT}^{{tree}}"])
    frozen_parent_commit = git_text(repo, ["rev-parse", f"{FROZEN_COMMIT}^"])

    # The exact workbook is bundled before any normalization. Copy only if the
    # caller did not already point at the bundle path.
    bundled_workbook = output / "source_workbook" / workbook.name
    bundled_workbook.parent.mkdir(parents=True, exist_ok=True)
    if workbook != bundled_workbook:
        shutil.copyfile(workbook, bundled_workbook)
    workbook_sha = sha256_file(bundled_workbook)
    workbook_bytes = bundled_workbook.stat().st_size
    if (
        workbook_sha != AUTHORITATIVE_WORKBOOK_SHA256
        or workbook_bytes != AUTHORITATIVE_WORKBOOK_BYTES
    ):
        raise RuntimeError(
            "Authoritative workbook byte identity does not match the final frozen source"
        )

    workbook_rows, workbook_snapshot = parse_workbook_snapshot(workbook_snapshot_path)
    snapshot_sha = sha256_file(workbook_snapshot_path)
    if snapshot_sha != AUTHORITATIVE_WORKBOOK_SNAPSHOT_SHA256:
        raise RuntimeError(
            "Artifact-tool workbook value/formula snapshot does not match the frozen authority"
        )
    legacy_manifest_bytes = legacy_manifest_path.read_bytes()
    legacy_manifest = json.loads(legacy_manifest_bytes)
    legacy_manifest_sha = sha256_bytes(legacy_manifest_bytes)
    old_by_set, old_by_id = old_manifest_index(legacy_manifest)

    full_inventory = ls_tree(repo, FROZEN_COMMIT)
    inventory_by_path = {record["path"]: record for record in full_inventory}
    raw_inventory = [record for record in full_inventory if record["path"].lower().endswith(".csv")]
    raw_inventory.sort(key=lambda record: record["path"])
    repo_sets = sorted({posix_set(record["path"]) for record in raw_inventory}, key=str.casefold)

    # Verify the raw cache is an exact byte snapshot of every Git-tracked file,
    # not a CRLF-converted working-tree view.
    cache_paths = sorted(
        str(path.relative_to(raw_cache)).replace(os.sep, "/")
        for path in raw_cache.rglob("*")
        if path.is_file()
    )
    tracked_paths = sorted(inventory_by_path)
    if cache_paths != tracked_paths:
        missing = sorted(set(tracked_paths) - set(cache_paths))
        extra = sorted(set(cache_paths) - set(tracked_paths))
        raise RuntimeError(f"Raw cache path mismatch; missing={missing}, extra={extra}")
    cache_hash_mismatches = []
    for record in full_inventory:
        cache_path = raw_cache / PurePosixPath(record["path"])
        actual_sha = sha256_file(cache_path)
        if actual_sha != record["sha256"]:
            cache_hash_mismatches.append(record["path"])
    if cache_hash_mismatches:
        raise RuntimeError(f"Raw cache byte mismatches: {cache_hash_mismatches}")

    workbook_yes = [row for row in workbook_rows if row["tested"] == "YES"]
    workbook_no = [row for row in workbook_rows if row["tested"] == "NO"]
    repo_casefold = defaultdict(list)
    for set_name in repo_sets:
        repo_casefold[set_name.casefold()].append(set_name)
    if any(len(values) != 1 for values in repo_casefold.values()):
        raise RuntimeError("Repository cohort names collide under case-insensitive matching")

    normalized_rows = []
    unmatched_yes = []
    for row in workbook_yes:
        matches = repo_casefold.get(row["display_name"].casefold(), [])
        if len(matches) != 1:
            unmatched_yes.append(row["display_name"])
            continue
        repo_set = matches[0]
        normalized_rows.append(
            {
                **row,
                "repo_set": repo_set,
                "match_method": "exact" if repo_set == row["display_name"] else "case_insensitive",
            }
        )
    if unmatched_yes:
        raise RuntimeError(f"Workbook YES rows missing from repository: {unmatched_yes}")
    matched_sets = {row["repo_set"] for row in normalized_rows}
    non_workbook_sets = sorted(set(repo_sets) - matched_sets, key=str.casefold)
    if set(non_workbook_sets) != set(NON_WORKBOOK_LEGACY_IDS):
        raise RuntimeError(
            f"Non-workbook cohorts differ from approved lineage set: {non_workbook_sets}"
        )

    raw_by_set: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in raw_inventory:
        raw_by_set[posix_set(record["path"])].append(record)

    # A physical acquisition is identified by its exact Git blob bytes. This
    # deliberately collapses the HHKB/slider mirror paths to four acquisitions.
    raw_by_sha: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in raw_inventory:
        raw_by_sha[record["sha256"]].append(record)
    acquisitions = {}
    for sha, paths in sorted(raw_by_sha.items()):
        oids = {record["git_blob_oid"] for record in paths}
        sizes = {record["size_bytes"] for record in paths}
        if len(oids) != 1 or len(sizes) != 1:
            raise RuntimeError(f"Equal SHA-256 content has inconsistent Git identity: {sha}")
        acquisition_id = f"acq_sha256:{sha}"
        aliases = sorted(record["path"] for record in paths)
        shared_pair = len(aliases) > 1
        acquisitions[acquisition_id] = {
            "acquisition_id": acquisition_id,
            "sha256": sha,
            "git_blob_oid": next(iter(oids)),
            "size_bytes": next(iter(sizes)),
            "raw_path_aliases": aliases,
            "evidence_group_id": SHARED_EVIDENCE_GROUP_ID if shared_pair else f"egrp_{slug(posix_set(aliases[0]))}",
            "independent_observation_count": 1,
        }

    duplicate_groups = [record for record in acquisitions.values() if len(record["raw_path_aliases"]) > 1]
    expected_shared_aliases = {
        tuple(sorted([f"Topre_HHKB_Pro2_45g/Topre_Slider_Black-DataLog_{run}.csv", f"Topre_Slider_Black/Topre_Slider_Black-DataLog_{run}.csv"]))
        for run in range(4)
    }
    actual_shared_aliases = {tuple(record["raw_path_aliases"]) for record in duplicate_groups}
    if actual_shared_aliases != expected_shared_aliases:
        raise RuntimeError(f"Unexpected duplicate acquisition groups: {actual_shared_aliases}")

    # Allocate new IDs from bt_0024 in authoritative workbook row order while
    # retaining all semantic IDs that have explicit previous-manifest lineage.
    assigned_ids = set(NON_WORKBOOK_LEGACY_IDS.values()) | {
        legacy_id for _, legacy_id in WORKBOOK_LEGACY_LINEAGE.values()
    }
    next_id = 24

    def allocate_id() -> str:
        nonlocal next_id
        while f"bt_{next_id:04d}" in assigned_ids:
            next_id += 1
        result = f"bt_{next_id:04d}"
        assigned_ids.add(result)
        next_id += 1
        return result

    tests = []
    normalized_by_set = {row["repo_set"]: row for row in normalized_rows}
    for row in normalized_rows:
        set_name = row["repo_set"]
        legacy_set_id = WORKBOOK_LEGACY_LINEAGE.get(set_name)
        legacy_record = old_by_id.get(legacy_set_id[1]) if legacy_set_id else None
        if legacy_set_id and (legacy_record is None or legacy_record["set"] != legacy_set_id[0]):
            raise RuntimeError(f"Broken legacy semantic mapping for {set_name}: {legacy_set_id}")
        test_id = legacy_set_id[1] if legacy_set_id else allocate_id()
        metadata, legacy_snapshot = workbook_metadata(row, legacy_record)
        source = {
            "catalog_source": "untested-domes_v2.xlsx",
            "catalog_source_sha256": workbook_sha,
            "sheet": "Untested Domes",
            "row": row["workbook_row"],
            "authoritative_fields": EXPECTED_HEADERS,
            "repo_set_match": row["match_method"],
            "legacy_manifest_source_sha256": legacy_manifest_sha if legacy_record else None,
            "legacy_test_id": legacy_record.get("test_id") if legacy_record else None,
            "legacy_set": legacy_record.get("set") if legacy_record else None,
            "derived_fields_reset": ["travel_dev_mm", "flag_travel"],
        }
        tests.append(
            semantic_record(
                test_id=test_id,
                set_name=set_name,
                metadata=metadata,
                metadata_source=source,
                legacy_snapshot=legacy_snapshot,
                raw_rows=raw_by_set[set_name],
                acquisitions=acquisitions,
            )
        )

    for set_name in non_workbook_sets:
        test_id = NON_WORKBOOK_LEGACY_IDS[set_name]
        legacy_record = old_by_id.get(test_id)
        if legacy_record is None or legacy_record["set"] != set_name:
            raise RuntimeError(f"Missing exact legacy lineage record {test_id} for {set_name}")
        legacy_snapshot = deepcopy(legacy_record["metadata"])
        metadata = reset_derived_metadata(legacy_snapshot)
        # Add the unified catalog keys without inventing values that the
        # workbook did not supply.
        metadata.update(
            {
                "display_name": legacy_snapshot["name"],
                "manufacturer": None,
                "brand": None,
                "style": None,
                "variant": None,
                "nominal_weight_g": None,
                "tested": None,
                "metadata_source": "predecessor_manifest",
                "metadata_source_locator": (
                    f"dataset_manifest.json#tests[test_id={test_id}].metadata"
                ),
                "metadata_override_applied": False,
                "evidence_alias_group": (
                    SHARED_EVIDENCE_GROUP_ID
                    if set_name == "Topre_Slider_Black"
                    else None
                ),
                "evidence_alias_role": (
                    "part_assembly_semantic"
                    if set_name == "Topre_Slider_Black"
                    else None
                ),
            }
        )
        source = {
            "catalog_source": None,
            "authoritative_fields": [],
            "legacy_manifest_source_sha256": legacy_manifest_sha,
            "legacy_test_id": test_id,
            "legacy_set": set_name,
            "lineage_rule": "exact non-workbook cohort metadata preserved from previous manifest",
            "catalog_fields_unavailable": EXPECTED_HEADERS[1:],
            "derived_fields_reset": ["travel_dev_mm", "flag_travel"],
        }
        tests.append(
            semantic_record(
                test_id=test_id,
                set_name=set_name,
                metadata=metadata,
                metadata_source=source,
                legacy_snapshot=legacy_snapshot,
                raw_rows=raw_by_set[set_name],
                acquisitions=acquisitions,
            )
        )

    tests.sort(key=lambda record: int(record["test_id"].split("_")[1]))
    if len(tests) != 76 or len({record["set"] for record in tests}) != 76:
        raise RuntimeError("Manifest does not contain exactly one semantic record per repository cohort")
    if len({record["test_id"] for record in tests}) != 76:
        raise RuntimeError("Manifest test ids are not unique")

    # Every tracked raw path appears exactly once as a path binding. Shared
    # bytes are de-duplicated only at the acquisition registry layer.
    manifest_paths = [run["path"] for test in tests for run in test["expected_runs"]]
    if sorted(manifest_paths) != [record["path"] for record in raw_inventory]:
        raise RuntimeError("Manifest raw paths do not form an exact bijection with tracked CSV paths")

    shared_tests = [test for test in tests if test["set"] in SHARED_EVIDENCE_SETS]
    shared_acquisition_ids = {run["acquisition_id"] for test in shared_tests for run in test["expected_runs"]}
    if len(shared_tests) != 2 or len(shared_acquisition_ids) != 4:
        raise RuntimeError("Shared Topre semantic records do not resolve to four unique acquisitions")

    test_by_set = {test["set"]: test for test in tests}
    alias_run_pairs = []
    for acquisition in sorted(duplicate_groups, key=lambda item: item["raw_path_aliases"]):
        members = []
        for path in acquisition["raw_path_aliases"]:
            set_name = posix_set(path)
            members.append(
                {
                    "test_id": test_by_set[set_name]["test_id"],
                    "set": set_name,
                    "path": path,
                    "sha256": acquisition["sha256"],
                    "git_blob_oid": acquisition["git_blob_oid"],
                }
            )
        alias_run_pairs.append(
            {
                "acquisition_id": acquisition["acquisition_id"],
                "members": members,
                "independent_observation_count": 1,
            }
        )

    manifest = {
        "manifest_version": 2,
        "schema_id": "domelab-canonical-evidence-manifest-v2",
        "epoch_id": EPOCH_ID,
        "repo_commit": FROZEN_COMMIT,
        "repo_parent_commit": frozen_parent_commit,
        "repo_tree_oid": frozen_tree_oid,
        "repo_commit_subject": frozen_subject,
        "repo_commit_time": frozen_commit_time,
        "counts": {
            "semantic_records": len(tests),
            "independent_measurement_cohorts": len({test["measurement_cohort_id"] for test in tests}),
            "tracked_raw_paths": len(raw_inventory),
            "unique_acquisitions": len(acquisitions),
            "workbook_authoritative_records": len(normalized_rows),
            "legacy_lineage_only_records": len(non_workbook_sets),
            "historically_pruned_runs": len(PRUNED_RUNS),
        },
        "metadata_source": {
            "file_name": bundled_workbook.name,
            "sha256": workbook_sha,
            "size_bytes": bundled_workbook.stat().st_size,
            "sheet": "Untested Domes",
            "used_range": "A1:G80",
            "artifact_tool_snapshot_sha256": snapshot_sha,
        },
        "legacy_metadata_source": {
            "repo_commit": legacy_manifest.get("repo_commit"),
            "sha256": legacy_manifest_sha,
            "role": "lineage only; workbook values override all matching catalog fields",
        },
        "shared_evidence_groups": [
            {
                "group_id": SHARED_EVIDENCE_GROUP_ID,
                "sets": SHARED_EVIDENCE_SETS,
                "semantic_test_ids": [next(test["test_id"] for test in tests if test["set"] == set_name) for set_name in SHARED_EVIDENCE_SETS],
                "unique_acquisition_ids": sorted(shared_acquisition_ids),
                "unique_acquisition_count": 4,
                "raw_path_count": 8,
                "user_ruling": "Same physical test, but the two semantic records represent different things.",
                "interpretations": {
                    "Topre_HHKB_Pro2_45g": "HHKB Pro2 45 g dome baseline",
                    "Topre_Slider_Black": "black-slider standard assembly baseline",
                },
                "inference_rule": (
                    "The four unique acquisitions may be exposed under both semantic interpretations, "
                    "but they must never be counted as eight independent observations or pooled together."
                ),
            }
        ],
        "evidence_aliases": [
            {
                "group_id": SHARED_EVIDENCE_GROUP_ID,
                "measurement_cohort_id": "mc_topre_hhkb_pro2_45g__topre_slider_black",
                "semantic_test_ids": [
                    test_by_set["Topre_HHKB_Pro2_45g"]["test_id"],
                    test_by_set["Topre_Slider_Black"]["test_id"],
                ],
                "run_pairs": alias_run_pairs,
                "independence_rule": (
                    "Each run pair is one physical acquisition with two paths and two semantic "
                    "interpretations; do not count both members as independent observations."
                ),
            }
        ],
        "tests": tests,
    }

    acquisition_registry = {
        "registry_version": 1,
        "epoch_id": EPOCH_ID,
        "identity_rule": "Exact SHA-256 of Git blob content identifies one physical acquisition byte record.",
        "counts": {
            "raw_paths": len(raw_inventory),
            "unique_acquisitions": len(acquisitions),
            "alias_groups": len(duplicate_groups),
        },
        "acquisitions": list(acquisitions.values()),
    }

    event_ledger = build_event_ledger(repo, inventory_by_path)

    normalized_json = {
        "normalization_version": 1,
        "source_workbook_sha256": workbook_sha,
        "sheet": "Untested Domes",
        "used_range": "A1:G80",
        "authoritative_field_rule": "Workbook values replace existing catalog values for matching cohorts.",
        "rows": normalized_rows,
    }

    reconciliation_rows = []
    for row in workbook_rows:
        matches = repo_casefold.get(row["display_name"].casefold(), [])
        reconciliation_rows.append(
            {
                "source": "workbook",
                "workbook_row": row["workbook_row"],
                "workbook_display_name": row["display_name"],
                "tested": row["tested"],
                "repo_set": matches[0] if matches else None,
                "match_method": (
                    "exact" if matches and matches[0] == row["display_name"] else
                    "case_insensitive" if matches else "not_present"
                ),
                "manifest_disposition": "include" if row["tested"] == "YES" and matches else "not_in_epoch",
                "metadata_source": "authoritative_workbook" if row["tested"] == "YES" and matches else "workbook_inventory_only",
            }
        )
    for set_name in non_workbook_sets:
        reconciliation_rows.append(
            {
                "source": "repository",
                "workbook_row": None,
                "workbook_display_name": None,
                "tested": None,
                "repo_set": set_name,
                "match_method": "not_in_workbook",
                "manifest_disposition": "include",
                "metadata_source": f"legacy_manifest:{NON_WORKBOOK_LEGACY_IDS[set_name]}",
            }
        )

    case_mismatches = [row for row in normalized_rows if row["match_method"] != "exact"]
    reconciliation = {
        "reconciliation_version": 1,
        "epoch_id": EPOCH_ID,
        "summary": {
            "workbook_rows": len(workbook_rows),
            "workbook_yes": len(workbook_yes),
            "workbook_no": len(workbook_no),
            "workbook_yes_matched": len(normalized_rows),
            "case_only_matches": len(case_mismatches),
            "repo_csv_cohorts": len(repo_sets),
            "repo_cohorts_not_in_workbook": len(non_workbook_sets),
        },
        "case_only_matches": case_mismatches,
        "non_workbook_cohorts": [
            {"set": set_name, "legacy_test_id": NON_WORKBOOK_LEGACY_IDS[set_name]}
            for set_name in non_workbook_sets
        ],
        "rows": reconciliation_rows,
        "limitations": [
            "The 11 non-workbook cohorts have no workbook catalog columns; manufacturer, brand, style, variant, nominal_weight_g, and tested remain explicitly null while legacy assembly metadata is preserved with its source hash.",
            "travel_dev_mm and flag_travel are generated-result fields, so old values were retained only in legacy_metadata_snapshot and reset in current metadata.",
            "The OEM Topre history event describes exact Git collection changes only and does not establish one-to-one specimen identity or retest satisfaction.",
            "The Topre_R2_45g retest event records two in-place blob replacements and one retirement only; no cause, specimen identity, or equivalence is inferred.",
        ],
    }

    metadata_registry_rows = []
    for row in workbook_rows:
        metadata_registry_rows.append(
            {
                **{column: row[column] for column in EXPECTED_HEADERS},
                "row_number": row["workbook_row"],
                "locator": (
                    f"untested-domes_v2.xlsx#'Untested Domes'!A{row['workbook_row']}:G{row['workbook_row']}"
                ),
            }
        )
    metadata_registry = {
        "registry_version": 1,
        "columns": EXPECTED_HEADERS,
        "rows": metadata_registry_rows,
        "set_name_aliases": {
            "DynaCaps_Heavy_55g": "Dynacaps_Heavy_55g",
        },
        "legacy_metadata_sets": sorted(non_workbook_sets, key=str.casefold),
        "source_workbook": {
            "file_name": bundled_workbook.name,
            "sha256": workbook_sha,
            "bytes": bundled_workbook.stat().st_size,
            "sheet": "Untested Domes",
            "used_range": "A1:G80",
            "artifact_tool_snapshot_sha256": snapshot_sha,
        },
        "authority_rule": (
            "For a tested YES row, the seven workbook columns replace prior values. "
            "The 11 declared legacy_metadata_sets are preserved from the predecessor manifest."
        ),
    }

    full_inventory_rows = []
    raw_inventory_rows = []
    for record in full_inventory:
        is_raw = record["path"].lower().endswith(".csv")
        row = {
            **record,
            "bytes": record["size_bytes"],
            "git_object_format": "sha1",
            "category": (
                "raw_csv" if is_raw else
                "legacy_doc" if record["path"].lower().endswith(".md") else
                "legacy_tool" if record["path"].lower().endswith(".html") else
                "repo_artifact"
            ),
            "is_raw_csv": is_raw,
            "set": posix_set(record["path"]) if is_raw else None,
            "acquisition_id": f"acq_sha256:{record['sha256']}" if is_raw else None,
            "evidence_group_id": acquisitions[f"acq_sha256:{record['sha256']}"]["evidence_group_id"] if is_raw else None,
        }
        full_inventory_rows.append(row)
        if is_raw:
            raw_inventory_rows.append(row)

    prune_events = [
        event
        for event in event_ledger["events"]
        if event["event_type"] == "quality_exclusion_and_prune"
    ]
    if len(prune_events) != 1:
        raise RuntimeError(f"Expected one prune history event, found {len(prune_events)}")
    prune_event = prune_events[0]

    exclusions_and_retests = {
        "record_version": 1,
        "epoch_id": EPOCH_ID,
        "current_manifest_exclusions": [],
        "historical_pruned_run_exclusions": prune_event["exclusions"],
        "retest_supersessions": [
            event
            for event in event_ledger["events"]
            if event["event_type"] == "retest_supersession"
        ],
        "non_authoritative_collection_transitions": [
            event
            for event in event_ledger["events"]
            if event["event_type"] == "non_authoritative_collection_transition"
        ],
        "note": (
            "Current manifest membership begins after pruning. Historical exclusions and replaced raw "
            "bytes are preserved here as path-and-hash-bound provenance, not reintroduced as candidates."
        ),
    }

    oem_events = [
        event
        for event in event_ledger["events"]
        if event["event_id"] == OEM_TOPRE_TRANSITION["event_id"]
    ]
    if len(oem_events) != 1:
        raise RuntimeError(f"Expected one OEM Topre history event, found {len(oem_events)}")
    oem_event = oem_events[0]
    final_retest_events = [
        event
        for event in event_ledger["events"]
        if event["event_id"] == "evt_retest_topre_r2_45g"
    ]
    if len(final_retest_events) != 1:
        raise RuntimeError(
            f"Expected one Topre R2 45g retest event, found {len(final_retest_events)}"
        )
    final_retest_event = final_retest_events[0]

    validation_checks = {
        "frozen_commit_available": True,
        "frozen_commit_tree_identity": (
            frozen_tree_oid == "e43d25a3fed8c5177467bba96a5abbdd5a3442b0"
            and frozen_parent_commit == PRUNE_COMMIT
        ),
        "raw_cache_exact_path_bijection": cache_paths == tracked_paths,
        "raw_cache_all_blob_hashes_match": not cache_hash_mismatches,
        "workbook_shape_A1_G80": True,
        "workbook_has_no_formulas": True,
        "authoritative_workbook_byte_identity": (
            workbook_sha == AUTHORITATIVE_WORKBOOK_SHA256
            and workbook_bytes == AUTHORITATIVE_WORKBOOK_BYTES
        ),
        "authoritative_workbook_snapshot_identity": (
            snapshot_sha == AUTHORITATIVE_WORKBOOK_SNAPSHOT_SHA256
        ),
        "workbook_yes_count_65": len(workbook_yes) == 65,
        "workbook_no_count_14": len(workbook_no) == 14,
        "workbook_yes_all_match_repo": len(normalized_rows) == 65,
        "repo_csv_cohort_count_76": len(repo_sets) == 76,
        "legacy_only_cohort_count_11": len(non_workbook_sets) == 11,
        "semantic_record_count_76": len(tests) == 76,
        "independent_measurement_cohort_count_75": len({test["measurement_cohort_id"] for test in tests}) == 75,
        "tracked_raw_path_count_184": len(raw_inventory) == 184,
        "unique_acquisition_count_180": len(acquisitions) == 180,
        "manifest_raw_path_bijection": sorted(manifest_paths) == [record["path"] for record in raw_inventory],
        "shared_topre_has_two_semantic_records": len(shared_tests) == 2,
        "shared_topre_has_four_unique_acquisitions": len(shared_acquisition_ids) == 4,
        "shared_topre_has_eight_alias_paths": sum(len(test["expected_runs"]) for test in shared_tests) == 8,
        "nine_pruned_paths_hash_verified_and_absent": len(prune_event["exclusions"]) == 9,
        "test_ids_unique": len({test["test_id"] for test in tests}) == 76,
        "sets_unique": len({test["set"] for test in tests}) == 76,
        "metadata_registry_has_79_rows": len(metadata_registry_rows) == 79,
        "metadata_registry_columns_exact": metadata_registry["columns"] == EXPECTED_HEADERS,
        "metadata_registry_legacy_sets_exact": set(metadata_registry["legacy_metadata_sets"]) == set(NON_WORKBOOK_LEGACY_IDS),
        "workbook_manifest_values_exact": all(
            all(
                test_by_set[row["repo_set"]]["metadata"].get(field)
                == (True if field == "tested" else row[field])
                for field in EXPECTED_HEADERS
            )
            for row in normalized_rows
        ),
        "workbook_authoritative_status_verified": all(
            test_by_set[row["repo_set"]]["metadata"].get("status") == "verified"
            for row in normalized_rows
        ),
        "workbook_no_rows_absent_from_manifest": not (
            {
                repo_casefold.get(row["display_name"].casefold(), [row["display_name"]])[0]
                for row in workbook_no
            }
            & {test["set"] for test in tests}
        ),
        "legacy_identity_fields_preserved": all(
            all(
                test["metadata"].get(field) == value
                for field, value in test["legacy_metadata_snapshot"].items()
                if field not in {"travel_dev_mm", "flag_travel"}
            )
            for test in tests
            if test["metadata"]["metadata_source"] == "predecessor_manifest"
        ),
        "legacy_catalog_fields_remain_unknown": all(
            all(
                test["metadata"].get(field) is None
                for field in [
                    "manufacturer", "brand", "style", "variant",
                    "nominal_weight_g", "tested",
                ]
            )
            for test in tests
            if test["metadata"]["metadata_source"] == "predecessor_manifest"
        ),
        "expected_run_identity_fields_complete": all(
            set(run) >= {"path", "sha256", "git_blob_oid", "bytes", "acquisition_id"}
            and run["acquisition_id"] == f"acq_sha256:{run['sha256']}"
            and run["bytes"] == inventory_by_path[run["path"]]["size_bytes"]
            for test in tests
            for run in test["expected_runs"]
        ),
        "shared_topre_semantics_distinct": (
            test_by_set["Topre_HHKB_Pro2_45g"]["metadata"]["kind"] == "dome_baseline"
            and test_by_set["Topre_HHKB_Pro2_45g"]["metadata"]["evidence_alias_role"] == "dome_semantic"
            and test_by_set["Topre_Slider_Black"]["metadata"]["kind"] == "part_assembly"
            and test_by_set["Topre_Slider_Black"]["metadata"]["evidence_alias_role"] == "part_assembly_semantic"
        ),
        "historical_prunes_leave_two_or_more_runs": all(
            entry["retained_sibling_run_count_at_frozen_commit"] >= 2
            for entry in prune_event["exclusions"]
        ),
        "history_has_six_events": len(event_ledger["events"]) == 6,
        "oem_topre_event_non_authoritative": (
            oem_event["event_type"] == "non_authoritative_collection_transition"
            and not any(
                value
                for key, value in oem_event["authority"].items()
                if key.startswith("authoritative_for_")
            )
            and oem_event["identity_mapping"] is None
        ),
        "oem_topre_exact_collection_counts": oem_event["counts"] == {
            "retired_raw_paths": 15,
            "retired_unique_git_blobs": 15,
            "introduced_raw_paths": 25,
            "introduced_unique_git_blobs": 25,
            "introduced_git_blobs_not_present_in_parent": 21,
            "introduced_paths_aliasing_preexisting_slider_blobs": 4,
        },
        "oem_topre_retired_objects_absent_from_epoch": all(
            not row["present_at_transition_commit"]
            and not row["present_at_frozen_commit"]
            for row in oem_event["retired_raw_objects"]
        ),
        "oem_topre_later_dispositions_exact": {
            disposition: sum(
                row["later_epoch_disposition"] == disposition
                for row in oem_event["introduced_raw_objects"]
            )
            for disposition in {
                "present_unchanged", "replaced_in_later_commit", "retired_in_later_commit"
            }
        } == {
            "present_unchanged": 22,
            "replaced_in_later_commit": 2,
            "retired_in_later_commit": 1,
        },
        "oem_topre_no_retest_decision_retired_not_satisfied": (
            oem_event["prior_topre_55g_no_retest_decision"][
                "decision_was_satisfied_by_this_commit"
            ] is False
            and len(
                oem_event["prior_topre_55g_no_retest_decision"][
                    "retired_raw_objects"
                ]
            ) == 4
        ),
        "topre_r2_45g_retest_parent_is_pruned_epoch": (
            final_retest_event["commit"] == FROZEN_COMMIT
            and final_retest_event["parent_commit"] == PRUNE_COMMIT
        ),
        "topre_r2_45g_event_is_non_authoritative_beyond_git_transition": (
            final_retest_event["authority"]
            == {
                "scope": "exact_git_object_transition_only",
                "authoritative_for_git_object_transition": True,
                "authoritative_for_specimen_identity": False,
                "authoritative_for_quality_reason": False,
                "authoritative_for_scientific_equivalence": False,
            }
        ),
        "topre_r2_45g_retest_diff_exact": (
            [row["action"] for row in final_retest_event["transitions"]]
            == ["replaced_in_place", "replaced_in_place", "retired_without_replacement"]
            and sum(
                row["successor_present_unchanged_at_frozen_commit"]
                for row in final_retest_event["transitions"]
            ) == 2
        ),
        "topre_r2_45g_current_manifest_has_two_runs": (
            len(test_by_set["Topre_R2_45g"]["expected_runs"]) == 2
            and {
                run["path"]
                for run in test_by_set["Topre_R2_45g"]["expected_runs"]
            } == {
                "Topre_R2_45g/DataLog_1.csv",
                "Topre_R2_45g/DataLog_2.csv",
            }
        ),
    }
    if not all(validation_checks.values()):
        raise RuntimeError(f"Validation checks failed: {validation_checks}")

    # Write primary artifacts.
    write_json(output / "source_workbook" / "workbook_snapshot.json", workbook_snapshot)
    write_json(output / "metadata" / "normalized_tested_domes.json", normalized_json)
    write_csv(
        output / "metadata" / "normalized_tested_domes.csv",
        ["workbook_row", *EXPECTED_HEADERS, "repo_set", "match_method"],
        normalized_rows,
    )
    write_json(output / "metadata" / "metadata_reconciliation.json", reconciliation)
    write_json(output / "metadata" / "dome_metadata_registry.json", metadata_registry)
    write_csv(
        output / "metadata" / "metadata_reconciliation.csv",
        ["source", "workbook_row", "workbook_display_name", "tested", "repo_set", "match_method", "manifest_disposition", "metadata_source"],
        reconciliation_rows,
    )
    write_json(output / "manifest" / "dataset_manifest.step2.json", manifest)
    write_json(output / "manifest" / "acquisition_registry.json", acquisition_registry)
    write_csv(
        output / "manifest" / "raw_file_inventory.csv",
        ["path", "set", "bytes", "sha256", "git_blob_oid", "git_object_format", "category", "mode", "git_object_type", "acquisition_id", "evidence_group_id"],
        raw_inventory_rows,
    )
    write_json(output / "manifest" / "raw_file_inventory.json", {"epoch_id": EPOCH_ID, "repo_commit": FROZEN_COMMIT, "files": raw_inventory_rows})
    write_csv(
        output / "manifest" / "repository_file_inventory.csv",
        ["path", "bytes", "sha256", "category", "git_blob_oid", "git_object_format", "mode", "git_object_type", "is_raw_csv", "set", "acquisition_id", "evidence_group_id"],
        full_inventory_rows,
    )
    repo_provenance = {
        "provenance_version": 2,
        "branch": "main",
        "sha": FROZEN_COMMIT,
        "parent_sha": frozen_parent_commit,
        "tree_oid": frozen_tree_oid,
        "date": frozen_commit_time,
        "commit_subject": frozen_subject,
        "git_object_format": "sha1",
        "tracked_files": len(full_inventory),
        "csvs": len(raw_inventory),
        "semantic_sets": len(tests),
        "independent_measurement_cohorts": len({test["measurement_cohort_id"] for test in tests}),
        "unique_raw_blobs": len(acquisitions),
        "repository_file_inventory_sha256": sha256_file(
            output / "manifest" / "repository_file_inventory.csv"
        ),
        "raw_file_inventory_sha256": sha256_file(
            output / "manifest" / "raw_file_inventory.csv"
        ),
        "raw_cache_identity": "exact git ls-tree/cat-file blob snapshot",
    }
    write_json(output / "manifest" / "repo_provenance.json", repo_provenance)
    write_json(output / "history" / "evidence_event_ledger.json", event_ledger)
    write_json(output / "history" / "exclusions_and_retests.json", exclusions_and_retests)

    provenance = {
        "provenance_version": 1,
        "epoch_id": EPOCH_ID,
        "deterministic_epoch_time": frozen_commit_time,
        "frozen_repository": {
            "path_as_received": str(repo),
            "commit": FROZEN_COMMIT,
            "parent_commit": frozen_parent_commit,
            "tree_oid": frozen_tree_oid,
            "subject": frozen_subject,
            "commit_time": frozen_commit_time,
            "tracked_file_count": len(full_inventory),
            "raw_csv_path_count": len(raw_inventory),
        },
        "workbook": {
            "path_as_received": str(workbook),
            "bundled_relative_path": f"source_workbook/{bundled_workbook.name}",
            "sha256": workbook_sha,
            "size_bytes": workbook_bytes,
            "artifact_tool_snapshot_sha256": sha256_file(output / "source_workbook" / "workbook_snapshot.json"),
            "superseded_ingestion_identity": {
                **SUPERSEDED_WORKBOOK_INGESTION,
                "artifact_tool_snapshot_sha256": snapshot_sha,
                "explanation": (
                    "The source workbook was resaved after initial ingestion. The final source "
                    "bytes supersede the prior copy; artifact-tool extraction proves no A1:G80 "
                    "metadata value or formula delta."
                ),
            },
        },
        "legacy_manifest": {
            "path_as_received": str(legacy_manifest_path),
            "sha256": legacy_manifest_sha,
            "repo_commit": legacy_manifest.get("repo_commit"),
        },
        "scope": "Step 2 metadata/provenance inputs only; no generator or viewer implementation changes.",
    }
    write_json(output / "provenance" / "epoch_input_provenance.json", provenance)

    validation_report = {
        "validation_report_version": 1,
        "epoch_id": EPOCH_ID,
        "checks": validation_checks,
        "counts": manifest["counts"],
        "case_only_mapping": {
            "workbook": "DynaCaps_Heavy_55g",
            "repo": "Dynacaps_Heavy_55g",
        },
        "shared_evidence_rule": manifest["shared_evidence_groups"][0],
        "warnings": reconciliation["limitations"],
        "open_questions": [],
        "result": "PASS",
    }
    write_json(output / "validation" / "validation_report.json", validation_report)

    # Hash every deliverable except the checksum index itself. The generated-at
    # timestamp above is fixed within one run; all substantive evidence is
    # content- and commit-bound.
    checksum_rows = []
    checksum_paths = []
    for directory, dirnames, filenames in os.walk(output, followlinks=False):
        dirnames[:] = sorted(
            name for name in dirnames
            if name not in {"node_modules", "__pycache__"}
        )
        for filename in sorted(filenames):
            path = Path(directory) / filename
            if path.name != "SHA256SUMS.csv" and path.suffix != ".pyc":
                checksum_paths.append(path)
    for path in sorted(checksum_paths):
        checksum_rows.append(
            {
                "path": str(path.relative_to(output)).replace(os.sep, "/"),
                "sha256": sha256_file(path),
                "size_bytes": path.stat().st_size,
            }
        )
    write_csv(output / "SHA256SUMS.csv", ["path", "sha256", "size_bytes"], checksum_rows)

    print(
        json.dumps(
            {
                "result": "PASS",
                "output": str(output),
                "epoch_id": EPOCH_ID,
                "semantic_records": len(tests),
                "raw_paths": len(raw_inventory),
                "unique_acquisitions": len(acquisitions),
                "workbook_records": len(normalized_rows),
                "legacy_only_records": len(non_workbook_sets),
                "pruned_history_records": len(PRUNED_RUNS),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
