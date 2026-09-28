# Homework 4 review summary

## Sample size and composition

108 distinct traces reviewed (100 required), across the four required batches. No trace counted toward more than one batch.

| Batch | Purpose | n | Selection |
|---|---|---|---|
| 1 | Broad baseline | 30 | 15 uniform random + 15 cluster representatives |
| 2 | Cross-cutting balance | 31 | Stratified by role, distributed across values |
| 3 | Depth search | 30 | Targeted retrieval for candidate modes and close negatives |
| 4 | Stability check | 17 | 15 true uniform random + 2 replacement traces (see below) |

Overall composition: 48 clean (no failure observed), 52 failed (at least one confirmed or candidate mode present), 8 excluded (scenario-generation bug, not gradable — see `scenarios/support_scenarios.KNOWN_ISSUES.md`).

Two of batch 4's uniform draw (support-0178, support-0184) hit a known scenario-generation bug (a topic-blind fallback `opening_message` that never mentions the policy topic being graded). Both were marked `excluded` and replaced with a corrected scenario (support-0178r, support-0184r) carrying the same underlying facts, per the established exclude-and-replace workflow.

## Batch 4: taxonomy stability check

Per the handout, batch 4's sole purpose was checking whether new failure modes keep appearing under a fair, unsteered uniform sample — not finding more evidence.

- 5 of 17 failed. All 5 matched already-confirmed modes: `order_metadata_not_exposed` (3 instances) and `find_order_cap_excludes_target` (2 instances).
- **0 new failure modes appeared.**
- 1 new close negative found (`incomplete_write_left_undone`, support-0012).

The taxonomy is stable under this check.

## Final taxonomy

**9 confirmed modes** (each with ≥3 positive instances):

| Mode | n | Close negatives | Fix type |
|---|---|---|---|
| `find_order_cap_excludes_target` | 16 | 2 | Tool/schema |
| `dispute_not_escalated` | 7 | 2 | Prompt |
| `return_refund_query_excludes_cw_returns` | 7 | 1 | Retrieval |
| `order_metadata_not_exposed` | 6 | 0 | Tool/schema |
| `store_identity_not_resolved` | 5 | 0 | Prompt |
| `incomplete_write_left_undone` | 5 | 1 | Prompt |
| `store_override_not_detected` | 4 | 2 | Prompt |
| `unnecessary_tool_call` | 4 | 1 | Prompt |
| `unsound_order_pick` | 4 | 1 | Prompt |

**6 candidate modes** (insufficient instances to confirm, kept as documented hypotheses): `policy_citation_missing` (n=2), `missing_data_not_disclosed` (n=2), `stale_option_offered` (n=2), `policy_miscitation` (n=1), `unreliable_record_trusted` (n=1), `unconfirmed_write` (n=0, 2 close negatives only).

### Why 9 confirmed modes, not 5-8

The handout's own merge rule is: merge two observations when one product fix would correct both; split them when they need different fixes. We tested every plausible-looking pair against that rule, including the two closest candidates:

- `order_metadata_not_exposed` vs. `unsound_order_pick` — initially looked mergeable from one annotation's wording alone; re-checking the raw trace and the scenario's ground truth showed the two candidates the agent picked between were not actually in eligibility-vs-recency conflict, and the real defect was a missing `get_order` call, not a bad selection rule. Kept split.
- `unsound_order_pick` vs. `stale_option_offered` — looked related via a shared `requirement_source` (RESP-3) and similar definition wording; checking the actual annotation notes showed genuinely different mechanisms (multi-candidate order disambiguation vs. single-item date-arithmetic verification). Kept split.
- `store_identity_not_resolved` vs. `unsound_order_pick` — the strongest remaining candidate, since both are about resolving order/store identity among candidates. But one mode is a *missing* tool call (agent never resolves at all) and the other is a *wrong* selection over data the agent already has (tool call made, reasoning broken). A fix for one wouldn't touch the other. Kept split.

No valid merge exists in this taxonomy. Forcing one to hit the 5-8 target would violate the handout's own splitting rule. 9 is treated as the honest, defensible count.

One additional caveat worth recording: `return_refund_query_excludes_cw_returns` is a retrieval/ranking defect (BM25 crowds out `cw-returns` whenever a query combines "return" and "refund"), confirmed at 7 instances — but 0 of those 7 occur in isolation. Every instance co-occurs with a separate confirmed mode (`store_override_not_detected` ×3, `unnecessary_tool_call` ×3, `store_identity_not_resolved` ×1, `order_metadata_not_exposed` ×1). The co-occurrence isn't causal — refund/return scenarios simply tend to need both a policy-text search (hitting the retrieval bug) and a store/order resolution step (where the other modes live) in the same turn. It still fails the same-fix test against every mode it co-occurs with, so it stays a separate mode, but the write-up should note its evidence is never independently confirmed on its own.

## Comparison against the AgentDebug taxonomy

[AgentDebug](https://arxiv.org/abs/2509.25370) (`AgentErrorTaxonomy`) classifies generic agent-loop failures into 5 domains: Memory (recall/retrieval), Reflection (misjudging an action's outcome), Planning (a flawed plan), Action (a malformed or misaligned action), and System-level (not the agent's fault). Our 9 modes were checked against it for a possible omission or an unclear name.

**Rough mapping.** Most of our modes cluster under Memory-style retrieval failures ("relevant info exists but isn't retrieved"): `find_order_cap_excludes_target`, `order_metadata_not_exposed`, `store_override_not_detected`, `return_refund_query_excludes_cw_returns`. `unsound_order_pick` and `incomplete_write_left_undone` resemble Reflection failures (misreading a result / misjudging that more confirmation is needed). `unnecessary_tool_call` maps directly to their "Inefficient Planning."

**Omission check.** AgentDebug has a "Hallucination" category (fabricating information to fill a gap) that our taxonomy has no mode for. Searching our own annotations for this pattern found exactly one flagged instance: support-0126, where the agent asserts "the window has passed" based on an implicit "today" date it was never given anywhere in the system prompt or a tool result. The instance was non-consequential (a 374-day-old order against a 30-day window — no boundary case to flip) and is the only one found across all 108 reviewed traces. This doesn't meet the same evidentiary bar every other mode was held to (≥3 confirmed instances), so it is recorded here as an observed watch-item, not added as a new mode. It should be looked for again if candidate-mode search in a future pass turns up more instances.

**Unclear name check.** None of our 9 names were found to be unclear against AgentDebug's terminology — if anything, ours are more specific, since each is grounded in a concrete Cartwheel tool/requirement rather than a generic agent-loop concept. No renames made.

## One taxonomy revision

Initial read of trace `302a2ca584e060ee3cb51c8706d85fed`'s annotation note (support-0090) suggested `order_metadata_not_exposed` should be downgraded to a candidate: the note's wording implied the agent's real error was picking between two "eligible" candidates using the wrong criterion — an `unsound_order_pick` mechanism, with the schema gap as secondary.

Pulling the raw trace and the scenario's ground truth (target: order #3, "Pocket Arcade") overturned this: the two candidates the agent weighed were not actually in eligibility-vs-recency conflict (both were the two most recent deliveries), and the agent had never attempted a `get_order` call to resolve the customer's explicitly-named store at all — the clean, primary `order_metadata_not_exposed` mechanism. The downgrade was reversed; the mode stayed confirmed. This is a concrete instance of the handout's own warning: an open code's *wording* can imply a different mechanism than the trace actually shows, so a proposed revision must be checked against the raw trace and ground truth, not just the note text.

## Rejected search suggestions

Batch 3's depth search (`scripts/select_batch3_depth_search.py`) retrieved 25 candidate traces via bag-of-words/cosine similarity over trace text, targeting 3 modes that were stuck at 2 confirmed instances:

| Targeted mode | Candidates pulled | Accepted |
|---|---|---|
| `store_identity_not_resolved` | 9 | **0** |
| `policy_citation_missing` | 8 | **0** |
| `unsound_order_pick` | 8 | 1 (support-0068) |

Overall: **1 accepted, 24 rejected**. This is recorded in `analysis/state/suggestions.json`.

Why the retrieval whiffed on 2 of 3 targets: `store_identity_not_resolved` and `policy_citation_missing` are both defined by something *missing* from the trace (a tool call that never happened; a policy citation that never appears) — two traces can use nearly identical vocabulary whether or not that absence occurred, since the missing element leaves no lexical trace for a word-overlap metric to match on. `unsound_order_pick`'s failure shows up as explicit comparison language in the reply ("the most likely match"), which bag-of-words can partially latch onto — hence its nonzero, if still low, hit rate. The boundary excluding the 24 rejects is each mode's own definition, not the retrieval score: a trace scoring high on lexical similarity to "order lookup" or "refund eligibility" text is not the same as a trace containing the specific failure mechanism.

## Sample fractions by mode (Part E)

Every one of the 9 confirmed modes was applied as an explicit present/absent judgment to all 100 gradable traces (108 reviewed minus 8 excluded scenario-bug traces). Labels are recorded per mode under `analysis/state/labels/`. These are **sample fractions**, not prevalence estimates — batches 2 and 3 deliberately stratified and targeted the sample, so the composition doesn't reflect the full trace population. Homework 5 estimates true prevalence from the complete Module 1 trace store.

| Mode | Present | Fraction |
|---|---|---|
| `find_order_cap_excludes_target` | 16 | 16% |
| `dispute_not_escalated` | 7 | 7% |
| `return_refund_query_excludes_cw_returns` | 7 | 7% |
| `order_metadata_not_exposed` | 6 | 6% |
| `store_identity_not_resolved` | 5 | 5% |
| `incomplete_write_left_undone` | 5 | 5% |
| `store_override_not_detected` | 4 | 4% |
| `unnecessary_tool_call` | 4 | 4% |
| `unsound_order_pick` | 4 | 4% |

A trace may carry more than one present mode (e.g. `find_order_cap_excludes_target` and `unsound_order_pick` co-occur once), so fractions do not sum to the overall fail rate.
