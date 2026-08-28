"""Retired legacy importer surface.

The former importer combined old acquisition QC with runfilter-v1.1. The owner
subsequently selected the independently released test-imp 1.1.4
(`intake-qc-v1.4`) as the acquisition authority. This module's old path is
intentionally not made to look equivalent: its canonical entry points fail
closed. ``discover_runs`` remains available as an explicitly non-scientific
filename-discovery helper.
"""

import os


RETIRED_IMPORTER_MESSAGE = (
    "legacy bench-import canonical orchestration is retired and non-authoritative; "
    "use the hash-bound test-imp 1.1.4 release (intake-qc-v1.4) for acquisition "
    "validation/import, then generate a role-bound intake decision manifest"
)


def discover_runs(batchdir, pattern=r"DataLog_\d+\.csv$"):
    """Every candidate raw file in the batch directory, sorted, no filtering."""
    import re
    out = []
    for fn in sorted(os.listdir(batchdir)):
        if re.search(pattern, fn, re.I):
            out.append(os.path.join(batchdir, fn))
    return out


def canonical_batch(paths, commit="local-batch", adjudications=None, diagnostics=None):
    """Reject the superseded QC/runfilter-v1.1 batch path.

    The arguments remain solely so older callers receive an explicit, stable
    failure instead of an import error or (worse) scientifically different
    output bearing a current-looking calculation version.
    """
    raise RuntimeError(RETIRED_IMPORTER_MESSAGE)


def orchestrate(batchdir=None, paths=None, commit="local-batch", diagnostics=None):
    """Reject every former canonical orchestration call, before reading data."""
    raise RuntimeError(RETIRED_IMPORTER_MESSAGE)
