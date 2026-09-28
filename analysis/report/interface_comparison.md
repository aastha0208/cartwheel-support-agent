# Interface comparison

## One design retained from the reference interface

The annotation mechanics: selecting text in a trace opens a popover, the note
saves as a quote-anchored highlight, and a margin note links back to it on
hover (`applyHighlights()`, `analysis/review_app/ui/index.html`). None of
that logic is specific to Cartwheel's trace shape, so there was nothing to
adapt.

## One design changed after inspecting real traces

Two changes made *before* writing interface code, both driven by concrete
friction hit reviewing real traces in the stock Langfuse UI:

1. **Automatic session-level grouping.** Cartwheel records one Langfuse
   trace per user turn, and `cartwheel.session_id` — the field linking a
   conversation's turns together — is a custom metadata attribute the stock
   UI's search can't use at all. Confirming a multi-turn conversation's
   other turns required a direct API/DB query and reassembling them by
   hand. The review interface now does that join server-side
   (`analysis/helpers/normalization.py::_merge_multi_turn`) and renders one
   continuous transcript per conversation.

2. **A computed status strip.** Reading a trace in the stock UI meant
   digging into a nested generation span's raw JSON to find out what
   happened. The new interface surfaces role, scenario id, and prompt
   version, plus one badge per tool call computed from that tool's actual
   result, before reading the conversation itself.

A third, larger change came later, *after* using the interface on real
data rather than just inspecting traces up front: the reference's map view
(a 2D canvas scatter of trace-similarity clusters) and its interactive
accept/reject buttons on AI suggestions were both initially carried over
unchanged, then removed. The map view's similarity clustering was tested
against every one of its top-scored predictions once enough annotations
existed to check them, and every prediction was a false positive (grouping
traces by topic, not by failure mechanism) — so it was cut entirely rather
than kept as a decoration. The accept/reject buttons were replaced with a
read-only computed summary, since "accepted" already has an unambiguous
answer — whether the trace's saved annotation tags match the suggestion's
mode — making a separate click redundant with the annotation itself. Both
removals only became obvious once real review data existed to test the
features against; neither was visible from the first 5-10 traces alone.

The map view later came back, but rebuilt on a different, more defensible
basis: `scripts/build_trace_graph.py` projects each reviewed trace's own
numeric features (turn count, tool-call count, distinct tools, retrieval
presence, token count — the same axis batch 1's cluster sampling already
used) into 2D via PCA, with k-means assigning each trace a cluster. Unlike
the removed version, this one is populated with real data and used for a
narrower, defensible purpose: spotting which *kind* of conversation hasn't
been reviewed yet, not predicting failure similarity (the same limitation
that sank the original map and the mode-similarity matrix still applies to
anything claiming trace proximity implies shared failure mechanism). It
ships with two views — a plain annotated/not-annotated read, and a
cluster-colored one with an annotation ring — toggled without losing either.

The tab layout also changed twice after real use. A "Taxonomy" tab was
split out from Progress mid-session to separate review-status information
from failure-mode findings, then folded back into Progress once it became
clear the reference interface's original single-Progress-view design (open
coding results and suggestions together) was the better call — splitting
them had been a deviation worth trying, not a deviation worth keeping. The
"Batch Ledger" tab was renamed to "Coverage" for the same reason: its actual
content (coverage across scenario dimensions) didn't match what its name
emphasized (which batch touched what).

## One limitation remaining

The Progress tab's fix-type table (`FIX_TYPES` in
`analysis/review_app/ui/index.html`) is a hand-written lookup mapping each
confirmed mode name to a fix category and description — it is not derived
from `patterns.json`. Adding a new confirmed mode without also updating
this lookup silently renders "Needs classification" instead of failing
loudly, so the table can go stale if the taxonomy changes and the UI code
isn't updated alongside it.
