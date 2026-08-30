"""Scientific-copy control.

Step 2.2 rewrote claims with `str.replace(old, new, 1)`. The release viewer
contains two occurrences each of several prohibited sentences, so one survived
into the generated artifact; two further phrases ("TOTAL ENERGY", "Every dome is
sold as one number") had no rule at all. Step 2.3 replaces every occurrence,
asserts an expected occurrence count for each rule, and then re-scans every
generated user-visible surface for the prohibited vocabulary.

Mechanical descriptors remain distinct from the separately versioned,
pilot-derived percentile indices. Each replacement avoids claiming that an
individual descriptor is itself a calibrated or causal perceptual measure.
"""
import re

# Semantic-detector building blocks (Step 2.3.1).
# _G permits up to 60 characters of intervening text so a claim cannot evade the
# scan merely by inserting words. _UNDER_1GF matches the quantity in any of the
# spellings the copy has actually used.
_G = r"[^.<>]{0,60}?"
_UNDER_1GF = (r"(?:under|below|less than|within|better than|no more than|<)\s*"
              r"(?:one\s*gram|1\s*(?:\.0\s*)?g(?:f|ram)?s?\b)")

# ---------------------------------------------------------------- prohibited
# Matched case-insensitively against every generated user-visible surface.
# A hit is a generation failure, not a warning.
PROHIBITED = [
    r"TOTAL ENERGY",
    r"how heavy it really is",
    r"how tactile",
    r"total work your finger does",
    r"closest energy proxy",
    r"Every dome is sold as one number",
    r"higher is crisper",
    r"industry[- ]standard",
    r"industry standard",
    r"sharpness per mm",
    r"tactile peak",
    r"tactile bump",
    r"bottom-out onset",
    r"bottom-out wall",
    # Step 2.3.1: the misleading repeatability claim is detected SEMANTICALLY.
    # Step 2.3 matched only the contiguous literal "run-to-run deviation under
    # one gram", so the release sentence ("run-to-run deviation in collapse
    # force is under one gram") slipped straight through the scan AND through a
    # rewrite rule that declared zero expected occurrences.
    # These patterns tolerate intervening words. `_G` is the permitted gap.
    _G + r"run-?to-?run" + _G + r"(?:deviation|variation|spread|repeatab)" + _G + _UNDER_1GF,
    _G + r"(?:deviation|variation|spread)" + _G + _UNDER_1GF,
    _G + _UNDER_1GF + _G + r"(?:repeatab|reproducib|precision|accuracy|accurate)",
    _G + r"(?:repeatab|reproducib|precision|accuracy)" + _G + _UNDER_1GF,
    # perceptual-claim vocabulary bound to a metric
    r"measures? (?:how )?(?:perceived |the )?(?:weight|tactility|crispness|sharpness|effort|fatigue)",
    r"how (?:heavy|crisp|sharp|tactile|hard) (?:it|the dome|the switch) (?:really |actually )?(?:is|feels)",
]

# Surfaces exempt from the scan: machine-readable provenance that legitimately
# quotes a prohibited string in order to prove it was removed.
SCAN_EXEMPT_SUFFIXES = ("prose_scan_report.json",)


_R8_SRC_BLOB = re.compile(r"const R8_SRC = \{.*?\}; /\* GENERATED", re.S)


def mask_verbatim_source(text):
    """Blank the labeled verbatim r8 source layer (R8_SRC) for scanning.

    The prohibited-copy gate governs presentation copy; the R8_SRC blob is
    the vendored source embedded verbatim under an explicit "every field,
    verbatim" label, and losslessness requires its text intact. Returns
    (masked_text, masked_chars)."""
    m = _R8_SRC_BLOB.search(text)
    if not m:
        return text, 0
    return (text[:m.start()] + "const R8_SRC = {}; /* GENERATED"
            + text[m.end():]), m.end() - m.start()


def scan(text):
    """Return [(pattern, matched_text, offset), ...] for every prohibited hit
    in the PRESENTATION text (the labeled verbatim source layer is masked)."""
    text, _ = mask_verbatim_source(text)
    hits = []
    for pat in PROHIBITED:
        for m in re.finditer(pat, text, re.IGNORECASE):
            hits.append((pat, m.group(0), m.start()))
    return sorted(hits, key=lambda h: h[2])


# ---------------------------------------------------------------- rewrites
# (old, new, expected_occurrences). expected_occurrences is asserted so that a
# release-template edit which adds or removes an occurrence fails generation
# instead of silently leaving prohibited copy in place.
VIEWER_CLAIMS = [
    ("the tactile peak of the press curve",
     "the detected mechanical collapse peak of the press curve", 0),
    ("The peak of the tactile bump. The point where the dome collapses.",
     "The detected mechanical collapse peak of the press curve.", 1),
    ("The valley of the tactile bump. The minimum force after the collapse and before the switch bottoms out.",
     "The detected post-collapse mechanical valley before the force-wall rise.", 1),
    ("The distance travelled when the switch bottoms out at the end of the stroke.",
     "The distance to detected force-wall onset, an operational bottom-out proxy rather than observed contact.", 0),
    ("bottom-out wall", "force-wall pattern", 0),
    ("Full-stroke press work", "Press work to force-wall", 0),
    ("peak-relative sharpness per mm", "peak-normalized force-loss secant per millimetre", 0),
    ("the dome-switch industry's tactile-ratio standard, where linear = 0% and higher is crisper",
     "a relative peak-to-valley force-drop ratio (linear = 0%); a mechanical descriptor, not a "
     "calibrated perceptual score", 0),
    ("the total work your finger does across the keystroke",
     "the one-way mechanical work integral to detected force-wall onset", 0),
    ("the closest energy proxy for how hard the dome feels to overcome",
     "the one-way mechanical work integral to collapse", 1),
    ("The industry standard for measuring how tactile the switch feels.",
     "Relative peak-to-valley force-drop ratio, (Collapse \u2212 Valley) / Collapse. A mechanical "
     "descriptor, not a calibrated perceptual score.", 0),
    ("These quantities describe different aspects of the stroke and are not a single universal "
     "measure of feel.",
     "Collapse force, Ramp, Pre-collapse work, Drop, Steepest 0.10 mm drop, Drop rate and Snap % "
     "are mechanical descriptors of the measured curve. Their pilot associations do not establish "
     "independent causal contributions.", 1),
    # Step 2.3.1. Observed maximum retained pairwise collapse-force range across
    # the pinned fleet is 1.3085 gf (Topre_Slider_Black_Silenced_0.5mm_Poron),
    # so the original sentence was not merely imprecise, it was false.
    ("Every configuration is tested in multiple runs and averaged; run-to-run deviation in "
     "collapse force is under one gram, which is why forces in gf and work in gf\u00b7mm are "
     "displayed as whole numbers.",
     "Every configuration is tested in multiple runs and averaged. Under runfilter-v1.1, "
     "retained runs must lie within 1.0\u00a0gf of the batch median collapse force and "
     "0.10\u00a0mm of the batch median collapse position. These are retention criteria, not "
     "claims of measurement accuracy or universal run-to-run repeatability. Calculations "
     "retain full precision; displayed values are rounded for presentation.", 1),
]

PICKER_CLAIMS = [
    ("peak of the tactile bump", "supplier-listed peak force", 8),
    ("Full-stroke press work", "Press work to force-wall", 2),
    ("Total Energy (how heavy it really is) and Snap % (how tactile)",
     "full-stroke press work and SNAP % \u2014 mechanical descriptors of the measured curve", 1),
    ("a precompressed dome reduces tactility and travel",
     "a precompressed dome reduces the measured force drop and travel", 1),
    ("Every dome is sold as one number",
     "Vendor weight figures are single nominal numbers", 1),
    ("TOTAL ENERGY", "PRESS WORK", 1),
    ("Total Energy", "Full-stroke press work", 0),
]

# Release-reference template text that must never reappear anywhere.
WORK_LANGUAGE = {
    "full_stroke": "retained in canonical evidence but omitted from the perception-focused viewer",
    "precollapse": "pre-collapse work \u2014 the one-way mechanical work integral to collapse",
}


def apply_claims(text, claims, what):
    """Replace EVERY occurrence and assert the declared count.

    Returns (text, [(old, n_replaced), ...]).
    """
    log = []
    for old, new, expected in claims:
        n = text.count(old)
        if n != expected:
            raise RuntimeError(
                f"{what}: claim rewrite target count mismatch for {old[:60]!r} \u2014 "
                f"expected {expected}, found {n}. The release template changed; "
                f"update prose.py deliberately rather than letting copy drift.")
        if n:
            text = text.replace(old, new)
        log.append((old, n))
    return text, log


def assert_clean(surfaces):
    """surfaces = {relpath: text}. Raise on any prohibited phrase."""
    problems = []
    for rel, text in sorted(surfaces.items()):
        if rel.endswith(SCAN_EXEMPT_SUFFIXES):
            continue
        for pat, got, off in scan(text):
            ctx = text[max(0, off - 60):off + 80].replace("\n", " ")
            problems.append(f"{rel}: prohibited /{pat}/ matched {got!r} \u2014 \u2026{ctx}\u2026")
    if problems:
        raise RuntimeError("prohibited scientific copy in generated output:\n  "
                           + "\n  ".join(problems[:20]))
    return True
