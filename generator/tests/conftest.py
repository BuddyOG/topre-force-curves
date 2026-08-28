"""Layout-independent test configuration. Every location is an env var or pytest
option; defaults resolve the DELIVERED handoff layout first, then the dev tree.
No path depends on any historical workspace."""
import json, os, sys, pytest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))  # generator/ (package parent)
FROZEN_COMMIT = "6e86ac1955a0c566c7aae521705e51371992ba8a"
FROZEN_CACHE_DIR = f"repo-{FROZEN_COMMIT}"

def _first(cands):
    for c in cands:
        if c and os.path.exists(c): return os.path.abspath(c)
    return None

def pytest_addoption(parser):
    parser.addoption("--cache", default=None, help=f"pinned raw cache root ({FROZEN_CACHE_DIR})")
    parser.addoption("--importer", default=None, help="path to bench-import.py")

@pytest.fixture(scope="session")
def commit():
    return os.environ.get("DOMELAB_COMMIT", FROZEN_COMMIT)

@pytest.fixture(scope="session")
def cache(request):
    p = _first([request.config.getoption("--cache"), os.environ.get("DOMELAB_CACHE"),
        os.environ.get("DOMELAB_RAW_CACHE"),
        os.path.join(HERE, "..", "..", "..", "raw_cache", FROZEN_CACHE_DIR),
        os.path.join(os.getcwd(), FROZEN_CACHE_DIR)])
    if not p:
        pytest.fail("raw cache not found: pass --cache, set DOMELAB_CACHE, or extract "
                    f"the exact {FROZEN_CACHE_DIR} snapshot into the epoch workspace", pytrace=False)
    return p

@pytest.fixture(scope="session")
def staging_dir():
    return _first([os.environ.get("DOMELAB_STAGING"),
        os.path.join(HERE, "..", "..", "..", "epoch_outputs", "staging_canonical_6e86ac19"),
        os.path.join(HERE, "..", "staging")])

@pytest.fixture(scope="session")
def importer_path(request):
    return _first([request.config.getoption("--importer"), os.environ.get("DOMELAB_IMPORTER"),
        os.path.join(HERE, "..", "..", "local_project", "bench-import.py"),
        os.path.join(HERE, "..", "..", "..", "bench-import.py")])

@pytest.fixture(scope="session")
def active_intake_identity():
    """Current importer/policy identity from the executable policy artifact."""
    path = os.path.join(HERE, "..", "domelab_pipeline", "config", "intake_policy.json")
    with open(path, encoding="utf-8") as stream:
        policy = json.load(stream)
    return {
        "policy_version": policy["policy_version"],
        "parity_target": policy["implementation_parity_target"],
    }
