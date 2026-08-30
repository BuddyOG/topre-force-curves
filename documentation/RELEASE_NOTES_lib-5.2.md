# EC Parts Library lib-5.2 historical candidate

`lib-5.2` records the generator and evidence-integration work that preceded the
EC Parts Builder redesign. It established stable catalog identities, explicit
record mappings, source-backed keyboard records, six-state compatibility
evidence, conservative unknown handling, and deterministic release checks.

Its consumer architecture was superseded before the lib-6.0 release: the
in-tool Dome Lab home, separate Parts Library tab, cross-tool navigation, live
switch model, and duplicated force-record presentation are not part of the
standalone EC Parts Builder.

The underlying data and validation work was retained. See
[RELEASE_NOTES_lib-6.0.md](RELEASE_NOTES_lib-6.0.md) for the replacement
interface and [EC_PARTS_LIBRARY.md](EC_PARTS_LIBRARY.md) for current behavior.
