#!/usr/bin/env python3
"""Materialize an exact, byte-for-byte Git blob snapshot at a validated target."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
from pathlib import Path


def git(repo: Path, args: list[str]) -> bytes:
    return subprocess.check_output(["git", "-C", str(repo), *args])


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def inventory(repo: Path, commit: str) -> list[dict[str, object]]:
    rows = []
    for raw in git(repo, ["ls-tree", "-r", "-z", commit]).split(b"\0"):
        if not raw:
            continue
        header, path_raw = raw.split(b"\t", 1)
        mode, object_type, oid = header.decode("ascii").split(" ")
        if object_type != "blob":
            raise RuntimeError(f"Unexpected non-blob object at {path_raw!r}")
        payload = git(repo, ["cat-file", "blob", oid])
        rows.append(
            {
                "path": path_raw.decode("utf-8"),
                "mode": mode,
                "git_blob_oid": oid,
                "sha256": sha256(payload),
                "size_bytes": len(payload),
                "payload": payload,
            }
        )
    return rows


def is_within(child: Path, parent: Path) -> bool:
    try:
        child.relative_to(parent)
        return True
    except ValueError:
        return False


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", required=True, type=Path)
    parser.add_argument("--commit", required=True)
    parser.add_argument("--epoch-root", required=True, type=Path)
    parser.add_argument("--target", required=True, type=Path)
    parser.add_argument("--report", required=True, type=Path)
    args = parser.parse_args()

    repo = args.repo.resolve()
    epoch_root = args.epoch_root.resolve()
    target = args.target.resolve()
    report_path = args.report.resolve()
    expected_target = (epoch_root / "raw_cache" / f"repo-{args.commit}").resolve()
    if target != expected_target or not is_within(target, epoch_root):
        raise RuntimeError(f"Refusing unsafe target {target}; expected {expected_target}")
    if not is_within(report_path, epoch_root):
        raise RuntimeError(f"Refusing report outside epoch root: {report_path}")
    resolved_commit = git(repo, ["rev-parse", args.commit]).decode("ascii").strip()
    if resolved_commit != args.commit:
        raise RuntimeError(f"Commit did not resolve exactly: {resolved_commit}")
    tree_oid = git(
        repo, ["rev-parse", f"{args.commit}^{{tree}}"]
    ).decode("ascii").strip()
    commit_time = git(repo, ["show", "-s", "--format=%cI", args.commit]).decode("utf-8").strip()

    rows = inventory(repo, args.commit)
    expected_paths = sorted(str(row["path"]) for row in rows)
    if target.exists():
        actual_paths = sorted(
            str(path.relative_to(target)).replace(os.sep, "/")
            for path in target.rglob("*")
            if path.is_file()
        )
        expected_by_path = {str(row["path"]): row for row in rows}
        mismatch_count = 0
        for path_string in set(actual_paths) & set(expected_paths):
            payload = (target / path_string).read_bytes()
            if sha256(payload) != expected_by_path[path_string]["sha256"]:
                mismatch_count += 1
        if actual_paths != expected_paths or mismatch_count:
            raise RuntimeError(
                "Existing exact-cache target failed path/hash validation before replacement"
            )

    staging = (target.parent / f".{target.name}.exact-staging").resolve()
    if staging.exists():
        raise RuntimeError(f"Refusing to overwrite stale staging directory: {staging}")
    staging.mkdir(parents=True)
    try:
        for row in rows:
            destination = staging / str(row["path"])
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(row["payload"])

        staged_paths = sorted(
            str(path.relative_to(staging)).replace(os.sep, "/")
            for path in staging.rglob("*")
            if path.is_file()
        )
        if staged_paths != expected_paths:
            raise RuntimeError("Staged snapshot path set does not match Git tree")
        for row in rows:
            staged = staging / str(row["path"])
            if sha256(staged.read_bytes()) != row["sha256"]:
                raise RuntimeError(f"Staged Git blob hash mismatch: {row['path']}")

        # The exact target has already been resolved and checked above. The old
        # CRLF-expanded cache is a reproducible derivative of Git, not unique
        # evidence, and is removed only after the replacement fully validates.
        if target.exists():
            shutil.rmtree(target)
        staging.rename(target)
    except Exception:
        if staging.exists():
            shutil.rmtree(staging)
        raise

    final_paths = sorted(
        str(path.relative_to(target)).replace(os.sep, "/")
        for path in target.rglob("*")
        if path.is_file()
    )
    if final_paths != expected_paths:
        raise RuntimeError("Promoted snapshot path set changed unexpectedly")
    for row in rows:
        if sha256((target / str(row["path"])).read_bytes()) != row["sha256"]:
            raise RuntimeError(f"Promoted snapshot hash mismatch: {row['path']}")

    report = {
        "report_version": 2,
        "deterministic_commit_time": commit_time,
        "repo_path": str(repo),
        "commit": args.commit,
        "tree_oid": tree_oid,
        "target": str(target),
        "method": "git ls-tree -r -z plus git cat-file blob; bytes written without text decoding",
        "result": {
            "status": "PASS",
            "tracked_files": len(rows),
            "raw_csv_files": sum(str(row["path"]).lower().endswith(".csv") for row in rows),
            "path_bijection": True,
            "all_sha256_match_git_blobs": True,
        },
    }
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
