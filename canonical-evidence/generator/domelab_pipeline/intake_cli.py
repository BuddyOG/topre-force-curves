"""Mechanical retained-run decision-manifest refresh.

Usage is intentionally separate from normal generation: producing a draft
does not activate it.  Review the diff, place it at the configured decision
path, then normal generation will recompute and require exact semantic parity.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile

from . import intake_policy
from .pipeline import compute_intake_decision_manifest


EXIT_RAMP_REVIEW_REQUIRED = 2


def _serialize(value):
    return json.dumps(value, sort_keys=True, indent=1, ensure_ascii=False) + "\n"


def _atomic_write(path, text):
    destination = os.path.abspath(path)
    parent = os.path.dirname(destination)
    if not os.path.isdir(parent):
        raise RuntimeError(f"output parent does not exist: {parent}")
    fd, temporary = tempfile.mkstemp(prefix=".intake-decisions-", suffix=".tmp", dir=parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, destination)
    except BaseException:
        try:
            os.unlink(temporary)
        except OSError:
            pass
        raise


def _ramp_reviews(manifest):
    return [
        (set_entry["set"], run["run"], run["ramp_review"])
        for set_entry in manifest["sets"]
        for run in set_entry["runs"]
        if run.get("ramp_review_required")
    ]


def _print_ramp_review_notice(reviews):
    print("RAMP REPEATABILITY WARNING", file=sys.stderr)
    print(
        "Retained runs listed below remain included, but differ by more than "
        "10% from their retained-run RAMP median:",
        file=sys.stderr,
    )
    for set_name, run_name, review in reviews:
        direction = "above" if review["signed_deviation_pct"] > 0.0 else "below"
        print(
            f"  {set_name}/{run_name}: RAMP {review['ramp_gf_per_mm']:.2f} gf/mm "
            f"vs median {review['retained_median_gf_per_mm']:.2f} gf/mm; "
            f"{review['absolute_deviation_pct']:.2f}% {direction}; threshold "
            f">{review['threshold_pct']:.2f}%",
            file=sys.stderr,
        )
    print("No run is omitted because of this warning alone.", file=sys.stderr)


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="domelab-intake-decisions",
        description="Recompute the hash-bound intake-qc-v1.4 decision manifest",
    )
    parser.add_argument("--cache", required=True, help="pinned raw-cache root")
    parser.add_argument("--commit", required=True, help="full verified repository commit")
    parser.add_argument(
        "--role",
        choices=sorted(intake_policy.ALLOWED_ROLES),
        default=intake_policy.PREVIEW_ROLE,
        help="preview cannot alter canonical membership; canonical is an explicit promotion",
    )
    parser.add_argument(
        "--output",
        required=True,
        help="draft JSON path, or - for stdout; never overwrites a file implicitly",
    )
    parser.add_argument(
        "--ack-ramp-review", action="store_true", help=argparse.SUPPRESS
    )
    args = parser.parse_args(argv)
    manifest = compute_intake_decision_manifest(args.cache, args.commit, args.role)
    reviews = _ramp_reviews(manifest)
    if reviews:
        _print_ramp_review_notice(reviews)
        if args.ack_ramp_review:
            print(
                "RAMP REVIEW acknowledged by explicit command-line option; warned runs remain included.",
                file=sys.stderr,
            )
        else:
            try:
                answer = input(
                    "Type RAMP REVIEW to acknowledge the warning, or press Enter to cancel: "
                ).strip()
            except EOFError:
                answer = ""
            if answer != "RAMP REVIEW":
                print(
                    "Cancelled. No intake decision draft was written. For reviewed automation, "
                    "rerun with --ack-ramp-review.",
                    file=sys.stderr,
                )
                return EXIT_RAMP_REVIEW_REQUIRED
            print(
                "RAMP REVIEW acknowledged. The warned run(s) remain included.",
                file=sys.stderr,
            )
    text = _serialize(manifest)
    if args.output == "-":
        sys.stdout.write(text)
    else:
        if os.path.exists(args.output):
            raise RuntimeError(
                f"refusing to overwrite existing decision manifest: {os.path.abspath(args.output)}"
            )
        _atomic_write(args.output, text)
        print(
            f"wrote {args.role} intake decision draft for {len(manifest['sets'])} sets -> "
            f"{os.path.abspath(args.output)}"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
