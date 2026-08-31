#!/usr/bin/env python3
"""Generate deterministic blinded schedules for the 25-dome validation study."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import random
import secrets
from pathlib import Path


FIELDS_INTERNAL = (
    "participant_id",
    "session",
    "trial_order",
    "blinded_code",
    "position",
    "test_id",
    "canonical_set",
    "dome_label",
)
FIELDS_PARTICIPANT = (
    "participant_id",
    "session",
    "trial_order",
    "blinded_code",
)
FIELDS_KEY = (
    "blinded_code",
    "position",
    "test_id",
    "canonical_set",
    "dome_label",
    "physical_specimen_id",
    "key_assigned_at",
    "key_custodian",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--participants", type=int, default=24)
    parser.add_argument("--sessions", type=int, default=2, choices=(2,))
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--code-key",
        type=Path,
        required=True,
        help="private code-key CSV; created securely if it does not exist",
    )
    parser.add_argument(
        "--mapping",
        type=Path,
        default=Path(__file__).resolve().parents[1]
        / "subjective-pilot"
        / "grid_mapping.json",
    )
    return parser.parse_args()


def read_panel(path: Path) -> list[dict[str, str]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    panel = payload.get("positions")
    if not isinstance(panel, list) or len(panel) != 25:
        raise ValueError("mapping must contain exactly 25 positions")
    required = {"position", "test_id", "canonical_set", "dome_label"}
    for row in panel:
        if not isinstance(row, dict) or required.difference(row):
            raise ValueError("every mapping row must contain all identity fields")
    for field in ("position", "test_id", "canonical_set"):
        values = [str(row[field]) for row in panel]
        if len(set(values)) != 25:
            raise ValueError(f"mapping field {field!r} is not unique")
    return panel


def opaque_codes(count: int) -> list[str]:
    values: set[str] = set()
    while len(values) < count:
        values.add(f"D{secrets.randbelow(900_000) + 100_000}")
    codes = sorted(values)
    secrets.SystemRandom().shuffle(codes)
    return codes


def write_csv(path: Path, fields: tuple[str, ...], rows: list[dict[str, object]]) -> None:
    with path.open("x", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def load_or_create_code_key(
    panel: list[dict[str, str]], path: Path
) -> list[dict[str, str]]:
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        codes = opaque_codes(len(panel))
        rows = [dict(row, blinded_code=code) for row, code in zip(panel, codes)]
        write_csv(path, FIELDS_KEY, rows)
        return rows

    with path.open(encoding="utf-8", newline="") as stream:
        rows = list(csv.DictReader(stream))
    if len(rows) != 25:
        raise ValueError("code key must contain exactly 25 data rows")
    by_test_id = {row.get("test_id", ""): row for row in rows}
    if len(by_test_id) != 25 or "" in by_test_id:
        raise ValueError("code key test_id values must be present and unique")
    codes = [row.get("blinded_code", "") for row in rows]
    if any(not code for code in codes) or len(set(codes)) != 25:
        raise ValueError("code key blinded_code values must be present and unique")

    result: list[dict[str, str]] = []
    for panel_row in panel:
        row = by_test_id.get(panel_row["test_id"])
        if row is None:
            raise ValueError(f"code key is missing {panel_row['test_id']}")
        for field in ("position", "canonical_set", "dome_label"):
            if row.get(field) != panel_row[field]:
                raise ValueError(
                    f"code key identity mismatch for {panel_row['test_id']}: {field}"
                )
        result.append({**panel_row, "blinded_code": row["blinded_code"]})
    return result


def main() -> int:
    args = parse_args()
    if args.participants < 1:
        raise ValueError("participants must be positive")
    if args.output.exists():
        raise FileExistsError(f"refusing to overwrite existing output: {args.output}")

    panel = read_panel(args.mapping)
    rng = random.Random(args.seed)
    coded_panel = load_or_create_code_key(panel, args.code_key)

    internal: list[dict[str, object]] = []
    public: list[dict[str, object]] = []
    for participant_number in range(1, args.participants + 1):
        participant_id = f"P{participant_number:03d}"
        prior_order: tuple[str, ...] | None = None
        for session in range(1, args.sessions + 1):
            ordered = list(coded_panel)
            rng.shuffle(ordered)
            current_order = tuple(str(row["blinded_code"]) for row in ordered)
            while current_order == prior_order:
                rng.shuffle(ordered)
                current_order = tuple(str(row["blinded_code"]) for row in ordered)
            prior_order = current_order
            for trial_order, row in enumerate(ordered, start=1):
                schedule_row: dict[str, object] = {
                    "participant_id": participant_id,
                    "session": session,
                    "trial_order": trial_order,
                    **row,
                }
                internal.append(schedule_row)
                public.append(schedule_row)

    for participant_number in range(1, args.participants + 1):
        participant_id = f"P{participant_number:03d}"
        for session in range(1, args.sessions + 1):
            subset = [
                row
                for row in internal
                if row["participant_id"] == participant_id and row["session"] == session
            ]
            if len(subset) != 25 or len({row["blinded_code"] for row in subset}) != 25:
                raise AssertionError("invalid randomized schedule")

    args.output.mkdir(parents=True)
    write_csv(args.output / "operator_schedule.csv", FIELDS_INTERNAL, internal)
    write_csv(args.output / "participant_schedule.csv", FIELDS_PARTICIPANT, public)
    code_key_sha256 = hashlib.sha256(args.code_key.read_bytes()).hexdigest()
    metadata = {
        "generator": Path(__file__).name,
        "participants": args.participants,
        "sessions": args.sessions,
        "panel_size": len(panel),
        "seed": args.seed,
        "schedule_rows": len(internal),
        "code_key_sha256": code_key_sha256,
        "note": "order is determined by seed; specimen codes come from the private key",
    }
    (args.output / "schedule_metadata.json").write_text(
        json.dumps(metadata, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(f"wrote {len(internal)} scored trials to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
