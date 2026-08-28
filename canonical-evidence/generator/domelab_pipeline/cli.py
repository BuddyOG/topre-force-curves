import argparse, json, os, sys
from .pipeline import generate, check

def main(argv=None):
    ap = argparse.ArgumentParser(prog="domelab-gen", description="Dome Lab metrics-v4.2 generator")
    ap.add_argument("--cache", required=True, help="pinned raw cache root (repo-<sha7>)")
    ap.add_argument("--commit", required=True, help="full repository commit SHA (verified, not trusted)")
    ap.add_argument("--out", required=True, help="staging output dir")
    ap.add_argument("--viewer-html", default=None, help="release viewer template (default: packaged copy)")
    ap.add_argument("--picker-html", default=None, help="release picker template (default: packaged copy)")
    ap.add_argument("--release-bench-tests", default=None, help="release records for the diff report (default: packaged copy)")
    ap.add_argument("--no-parity", action="store_true", help="skip the node/jsdom parity artifact")
    ap.add_argument(
        "--evidence-only", action="store_true",
        help="emit canonical evidence and derived curve JSON packs without Force Curve Bench HTML/UI artifacts",
    )
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--write", action="store_true")
    g.add_argument("--check", action="store_true", help="non-mutating reproducibility/conformance check")
    a = ap.parse_args(argv)
    kw = dict(viewer_html=a.viewer_html, picker_html=a.picker_html,
              release_bench_tests=a.release_bench_tests, run_parity=not a.no_parity,
              evidence_only=a.evidence_only)
    if a.check:
        problems = check(a.cache, a.commit, a.out, **kw)
        for p in problems: print(p)
        print("CHECK OK — regeneration is byte-identical and the staging tree is exact"
              if not problems else "CHECK FAILED")
        return 0 if not problems else 1
    staged, *_ = generate(a.cache, a.commit, a.out, write=True, **kw)
    print(f"wrote {len(staged)} artifacts -> {a.out}")
    return 0

if __name__ == "__main__":
    sys.exit(main())
