"""Run the complete acceptance suite and record an isolated platform result.

``DOMELAB_RESULTS_PATH`` may redirect the result file.  Tests that invoke this
runner must use a temporary path so they cannot overwrite the package's live
Windows/Linux result while pytest is still reading fixtures from that tree.
"""
import json, locale, os, platform, subprocess, sys, tempfile, time

HERE = os.path.dirname(os.path.abspath(__file__))
GEN = os.path.dirname(HERE)


def main():
    tag = "windows" if os.name == "nt" else "linux"
    out = os.path.abspath(os.environ.get(
        "DOMELAB_RESULTS_PATH", os.path.join(GEN, f"test_results.{tag}.json")))
    started = time.time()
    child = dict(os.environ)
    child.setdefault("PYTHONIOENCODING", "utf-8")
    # DOMELAB_PYTEST_TARGET lets a failure-injection test point the recorder at a
    # small target instead of the whole suite, which would otherwise recurse into
    # the test that invoked it. Unset in normal operation: the default is the
    # complete suite.
    target = os.environ.get("DOMELAB_PYTEST_TARGET") or os.path.join(GEN, "tests")
    cmd = [sys.executable, "-m", "pytest", "-q", "--tb=short", target]
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8",
                       errors="replace", cwd=GEN, env=child)
    tail = (r.stdout or "").strip().splitlines()
    summary = tail[-1] if tail else ""
    # standalone --check
    chk = subprocess.run([sys.executable, "-m", "domelab_pipeline.cli",
                          "--cache", os.environ.get("DOMELAB_CACHE", "../raw_cache/repo-9175069"),
                          "--commit", os.environ.get(
                              "DOMELAB_COMMIT", "9175069f4e49cf968b911fbe6a5587e1921a4c18"),
                          "--out", "staging", "--check"],
                         capture_output=True, text=True, encoding="utf-8",
                         errors="replace", cwd=GEN, env=child)
    passed = r.returncode == 0 and chk.returncode == 0
    payload = {
        "executed": True,
        "status": "PASS" if passed else "FAIL",
        "platform": tag,
        "os": platform.platform(),
        "python": sys.version.split()[0],
        "pythonutf8_env": os.environ.get("PYTHONUTF8", "<unset>"),
        "preferred_encoding": locale.getpreferredencoding(False),
        "lang_env": os.environ.get("LANG", "<unset>"),
        "lc_all_env": os.environ.get("LC_ALL", "<unset>"),
        "pytest_returncode": r.returncode,
        "pytest_summary": summary,
        "pytest_stdout_tail": tail[-25:],
        "standalone_check_returncode": chk.returncode,
        "standalone_check_stdout": (chk.stdout or "").strip().splitlines()[-3:],
        "duration_s": round(time.time() - started, 1),
        "environment_workaround_applied": False,
    }
    out_dir = os.path.dirname(out) or os.curdir
    os.makedirs(out_dir, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=os.path.basename(out) + ".",
                               suffix=".tmp", dir=out_dir)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as f:
            json.dump(payload, f, indent=1, sort_keys=True)
            f.write("\n")
        os.replace(tmp, out)
    except Exception:
        try:
            os.unlink(tmp)
        except FileNotFoundError:
            pass
        raise
    print(json.dumps({k: payload[k] for k in
                      ("platform", "python", "pythonutf8_env", "preferred_encoding",
                       "pytest_returncode", "pytest_summary",
                       "standalone_check_returncode")}, indent=1))
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
