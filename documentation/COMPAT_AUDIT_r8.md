# Compatibility audit — six-state evidence source

Truth source: `config/compat_evidence.json` (schema compat-evidence-v2),
regenerated deterministically by `tools/generate_catalog_config.py` from the
vendored r8 source plus the two committed authored overlays. The template
carries no authored compatibility graph; the generator injects this file and
the runtime synthesizes an explicit, surfaced *unknown* for any absent
lookup. Nothing absent ever renders as compatible. This audit is the same
tool's fifth output: every number below is computed from the evidence and
asserted at generation time.

## Universe and closure
- Items: 85 co-selectable non-dome catalog identities across the
  complete vendored catalog and authored shell abstractions.
- Pairs: 3570 = C(85,2); full closure, every pair carries
  an explicit state.
- States: compatible 101, incompatible 156,
  conditional 38, pending 43, unknown
  2804, not_applicable 428.

## Runtime-selectable coverage
The builder subset is derived from `catalog_overlay.json` `buildable_lists`,
not from a second hard-coded census. Library-only plate, PCB, and mod-tier
records remain in the full evidence closure but do not inflate these figures.
- Identities selectable by the current UI: 68.
- Pair closure over that subset: 2278.
- Applicable pairs: 1850.
- Resolved source-imported pairs: 264.
- Unresolved pairs (unknown, pending, owner_pending, or unadjudicated):
  1586.
- State census: compatible 101, conditional 38, incompatible 156, not_applicable 428, pending 43, unknown 1512.

## Current consumer-core reconciliation
The consumer core is derived from the present catalog rather than frozen to
the earlier 43-vertex review snapshot.
- Core vertices: 44; unordered pairs: 946.
- Same-slot exclusions: 121 (housings 10, keycaps 1, sliders 28, spacebars 15, springs 10, stab housings 21, stab sliders 36).
- Shell-model exclusions: 31 — RC1 shell x spacebar stabilizer (6); shell x housing (10); shell x shell (1); shell x stabilizer housing (14).
- Applicable pairs over the current core: 794. Every
  explicit `unknown` entry naming its evidence gap. Across the full evidence
  universe the applicable count is 3142.

## lib-6.1 consumer projection

The complete closure and counts above remain the audit authority. The
`lib-6.1` browser payload is a smaller consumer projection containing
**241 decision-changing pair edges**. It suppresses
97 source-imported or pending edges whose repeated
pair form is subsumed by a part-scoped conical-spring finding:
conical_spring::deskeys 31, conical_spring::klc_playground 31, conical_spring::metapulse 35.

This suppression changes presentation, not provenance. Deskeys and KLC are
shown once as part-scoped **Does not work** findings; MetaPulse is shown once
as a part-scoped **Not verified** finding. Only the culprit spring row is
flagged, the whole-build result inherits that issue, and unrelated component
rows are not blamed. Any genuine pair-specific finding that is not subsumed by
a part-scoped issue remains in the consumer projection and is evaluated
normally.

## r8 agreement and the 31 reverted promotions
- r8 part-scoped edges: 335; every `compatible` and
  `incompatible` r8 status is preserved verbatim (**source_imported** —
  imported statements are never recorded as owner-confirmed, and
  `last_reviewed` stays null until a real owner review).
- All r8 `exceptions` edges are conditional or pending; the 31
  edges that lib-5.0 had silently promoted to plain compatible are reverted
  to **conditional / owner_pending** carrying
  `note_dynacaps_conical_universal`, and the runtime renders “Owner
  adjudication pending — treat as unconfirmed.”
  - `ce2_2b639a42a53b163055b2a87112008b3a9eda6cf09613b9918c9c50a6013f6b30` conical_spring::dynacaps ↔ housing::deskeys
  - `ce2_412359ea1a0864c754e0ee3d3a97967eecd6a8ffcf0f2c2014c5dcaf6a6f6b53` conical_spring::dynacaps ↔ housing::dynacaps
  - `ce2_6e74c91cc776b14535ba41c57606ef772270dff3151d51e1363d2a7c3546a535` conical_spring::dynacaps ↔ housing::klc_playground
  - `ce2_010376dbed29733de16da5756301f5b283927ae33ffa005cf4a41d241f377443` conical_spring::dynacaps ↔ housing::topre
  - `ce2_378269ed236e0488610124f4f63e83923d81378ec2a4d195eb1f07f52ec40151` conical_spring::dynacaps ↔ keycap::mx
  - `ce2_447ffbeb49bcbf894b3864b96a1347633b61ac9812de0d5ef7aa9bfd996cb211` conical_spring::dynacaps ↔ keycap::topre
  - `ce2_c3c26755cdcb1bcabee55db5a50f1581bbc787bbc751b25aaf9b3cf68ca309c3` conical_spring::dynacaps ↔ slider::deskeys
  - `ce2_4b2c1e1c479453789bc368ac0efe60725a3f2ef6132f23a5d2042b18de3572c5` conical_spring::dynacaps ↔ slider::dynacaps
  - `ce2_60404c3304eb6c681d9dd1e89594a42878aa5f8a5ce0f195851adc5c2a3f65ca` conical_spring::dynacaps ↔ slider::hhkb_type_s
  - `ce2_059fc80d458115ddeb36925e97a5a8a78286aa03221cb6fe23c5537f788b2d89` conical_spring::dynacaps ↔ slider::klc_playground
  - `ce2_31e31611010f5488e6f32fda1e8fa87e3a9741a31118484747e168f83bd7a495` conical_spring::dynacaps ↔ slider::novatouch
  - `ce2_d3cc8f886121cc1b917fa9b32cdd848514211e4df96fc84cc19017924daa1e2c` conical_spring::dynacaps ↔ slider::topre
  - `ce2_71082d439a1f42e0fcba1269bf2eb2211b36dca5e9f485f523cca080bf95d75f` conical_spring::dynacaps ↔ slider::topre_silenced_purple
  - `ce2_af14d46e8ea43c8406ee1de88a812e5568aa1b4439009cc6cf2bc2dab9b847c5` conical_spring::dynacaps ↔ spacebar_stabilizer::deskeys
  - `ce2_663abde60da060e87ff6c63b783586a4c6413c11c70d70fc08cece9621d892df` conical_spring::dynacaps ↔ spacebar_stabilizer::dynacaps
  - `ce2_7caf15f8aa908206e81d8fa4a07127a4698cb139c06cb9db047ad8065ed4935c` conical_spring::dynacaps ↔ spacebar_stabilizer::klc_playground
  - `ce2_0b983582986f96b8ddcf0e97179fb7808c092801f33f1f4c70cdee889dca969f` conical_spring::dynacaps ↔ spacebar_stabilizer::topre
  - `ce2_0d91b0545769ef76537015d39cc7b1afeeed527a91d3f2ed0aa10e75938f2d31` conical_spring::dynacaps ↔ stabilizer_housing::deskeys
  - `ce2_bfb69b6022c9815ff7d7010d3634b33353e155624d4bd8e78a27ca16bbdafb27` conical_spring::dynacaps ↔ stabilizer_housing::dynacaps
  - `ce2_dac390df318e6deddeb3e7d46c306380c19a417bd35b0d4a60a5e5d3a1a32483` conical_spring::dynacaps ↔ stabilizer_housing::klc_playground
  - `ce2_f7e3818e433fda047a5467276b7eab32e098dc84188bf99c5d77937a1786bfdd` conical_spring::dynacaps ↔ stabilizer_housing::novatouch
  - `ce2_0d570c7418b91b93e9817fbc5907c53422fbfe1b4d2925201aa4a192692399d2` conical_spring::dynacaps ↔ stabilizer_housing::topre_silenced
  - `ce2_4da38f21775f1b04384a87485a96771cf15d6b54e542a9c15d1521d90e89104b` conical_spring::dynacaps ↔ stabilizer_housing::topre_standard
  - `ce2_04ea0c268ef4facfc5fde45e8b766943403109681bfd86b03439eebe6748240d` conical_spring::dynacaps ↔ stabilizer_slider::deskeys
  - `ce2_8a12eb0f133d61bcfdf2af381570fceafdab8611dca4f5587ba786b53d96aa66` conical_spring::dynacaps ↔ stabilizer_slider::dynacaps
  - `ce2_4e83d15ec131d4330bad7d60b43b92b4b9f1b5747c5ac7603e81dda3041b385a` conical_spring::dynacaps ↔ stabilizer_slider::hhkb_type_s
  - `ce2_4d606738bc23244a76dd22cc30ce1e1da0e845d41aa1a9f9dba41969e56d6884` conical_spring::dynacaps ↔ stabilizer_slider::klc_playground
  - `ce2_032cfde4a3409cd6908024f2002e9886b9ae36a250053525fc6ea9828660f2c2` conical_spring::dynacaps ↔ stabilizer_slider::novatouch
  - `ce2_5ad42c349f6a2387948b6aa64e13024e8a77a7ea485495ec8d75d82d17c15482` conical_spring::dynacaps ↔ stabilizer_slider::realforce_rc1_silenced_purple
  - `ce2_3d643eae75e10742f1e5c91b27820f18509a5ea3fe3b17fee47e7035e6c5e567` conical_spring::dynacaps ↔ stabilizer_slider::topre
  - `ce2_23a7d2a3e27e3d78a4765d9478af6aced1e5b728392b08e88f1caad12bf87275` conical_spring::dynacaps ↔ stabilizer_slider::topre_silenced

## Restored qualifiers
  - `ce2_748cd493fac1245d9e236107190d31d1592646ec270091d7bf402e757b017269` housing::dynacaps ↔ slider::hhkb_type_s
  - `ce2_b3cfb4e85b02511ea662e739c7230aaa21df14996c27350126663015d7d42bf9` housing::dynacaps ↔ slider::topre_silenced_purple
  — note `note_dynacaps_housing` + qualifier `(scratchy)`, rendered for
  both Topre Silent variants; the lib-5.0 inline-key convention that dropped
  the note at runtime is retired.

## Preserved rule
- `opening_vs_barrel` (r8 compat_rules.json): status **not_evaluable**
  — no part in the vendored r8 source carries dimensions; the rule is
  preserved, injected (`COMPAT_RULES`), and reported Not evaluable at
  runtime until dimensions exist.

## Sources
- Explicit evidence by source: lib50 3, r8 254, r8+lib50 81.
- Every pair carries `source_refs`; every referenced source artifact has a
  repository-relative path and SHA-256 in the top-level `source_artifacts`
  registry. Pair IDs are SHA-256-derived from their ordered endpoint IDs and
  therefore do not renumber when unrelated catalog items are added.
- The r8 keyboard-scoped MetaPulse statements are carried at the shell
  level as authored lib-5.0 refinements (3 edges: the two
  stabilizer-slider pairs and the HHKB-shell × spacebar-stabilizer
  pair, all attributed to `note_metapulse_stab_incompat`); the RC1 spacebar
  side is not_applicable because the RC1 shell integrates its spacebar
  stabilizer.
- Regenerated by `tools/generate_catalog_config.py`; `--check` is the
  determinism gate.
