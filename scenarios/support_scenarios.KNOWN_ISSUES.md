# Known issues in support_scenarios.jsonl

## Topic-blind opening_message for 14 policy_question scenarios

**Found**: 2026-09-26, during HW4 (Module 2) trace review.

**Root cause**: `scenarios/results/stage_b_situations.py:306-307`. For
`policy_question` scenarios not covered by a hand-written entry in that
script's `BESPOKE` dict, the situation builder falls through to a generic,
topic-blind placeholder:

```python
if intent == "policy_question":
    return "You have a general question about Cartwheel's return, refund, or shipping policies."
```

Every scenario's `tuple.record_state` field ("Policy topic: X") and its
`expected` field are generated correctly and independently reference a
specific topic (`return_window`, `restocking_fee`, `dispute_window`,
`cancel_cutoff`, or `shipping`) -- but the `opening_message` text is this
same static sentence regardless of which topic was assigned, whenever the
scenario fell through to the fallback. Downstream paraphrasing into varied
natural-language phrasings inherits the same topic-blindness, since its
input was already generic.

`return_window` and `shipping` scenarios happen to escape visibly broken
because "return" and "shipping" are both literally present in the fallback
sentence. `restocking_fee`, `dispute_window`, and `cancel_cutoff` do not
share any word with it, so those scenarios end up asking a generic
return/refund/shipping question while being graded on a completely
different, unmentioned fact.

**Affected scenario ids** (14 total, `support-0171` through `support-0192`,
rotating through the three broken topics):

| id | topic |
|---|---|
| support-0171 | restocking_fee |
| support-0172 | dispute_window |
| support-0173 | cancel_cutoff |
| support-0176 | restocking_fee |
| support-0177 | dispute_window |
| support-0178 | cancel_cutoff |
| support-0181 | restocking_fee |
| support-0182 | dispute_window |
| support-0183 | cancel_cutoff |
| support-0186 | restocking_fee |
| support-0187 | dispute_window |
| support-0188 | cancel_cutoff |
| support-0191 | restocking_fee |
| support-0192 | dispute_window |

**Why these weren't edited in place**: `support_scenarios.jsonl` is a
committed HW3 deliverable. Rather than mutate it, the 3 of these 14 that
fell into the HW4 review sample were left untouched and replaced with new
records instead (see below), preserving an honest record of what HW3 as
originally generated actually contains.

**Update 2026-09-27: the bug's true footprint is 17 scenarios, not 14.**
The original list was built by exact-string-matching the raw fallback
sentence. A content-based re-scan (does the opening_message actually mention
its own `record_state` topic's keyword, not just string-match the fallback)
found 3 more, all `shipping`-topic: `support-0179`, `support-0184`,
`support-0189`. `shipping` and `return_window` topics were wrongly assumed
safe because their keyword literally appears in the raw fallback sentence --
but paraphrasing can still drop it. `support-0184` was later drawn into
batch 4's uniform random sample (see below) and addressed there.

**HW4 review sample impact**: 7 known-broken scenarios were sampled into the
HW4 review set (`support-0177`, `support-0183`, `support-0191`, `support-0179`,
`support-0189` -- the last two found via the content-based re-scan above --
and `support-0178`/`support-0184`, both from the original 14, which landed in
batch 4's uniform random draw). Each is marked `kind: "excluded"` in
`analysis/state/annotations.json` (not pass/fail, since the agent can't be
fairly graded against an expected outcome its own prompt never referenced)
and replaced by a corrected scenario in `scenarios/replacement_scenarios.jsonl`:

| broken | replacement | topic |
|---|---|---|
| support-0177 | support-0177r | dispute_window |
| support-0183 | support-0183r | cancel_cutoff |
| support-0191 | support-0191r | restocking_fee |
| support-0179 | support-0179r | shipping |
| support-0189 | support-0189r | shipping |
| support-0178 | support-0178r | cancel_cutoff |
| support-0184 | support-0184r | shipping |

Each replacement carries the exact same `tuple`/`expected` data as the
scenario it replaces (same role, store, facts, grading criterion) with only
`opening_message` corrected to actually reference the graded topic. Traces
for the replacements were collected by running them live against the
Module 1 endpoint (`uv run python -m scenarios.runner
scenarios/replacement_scenarios.jsonl --model claude-opus-4-6 --base-url
http://localhost:8010 --output scenarios/results/replacement-run.jsonl
--resume --ids <new_id>`) and are in the HW4 review sample as normal traces.

**The other 9 originally-flagged scenarios** (not in the HW4 sample) are
still untouched, and an unknown number of `return_window`/`shipping`-topic
scenarios outside the original 14 may share the same paraphrase-drift issue
(see the 2026-09-27 update above) -- not yet scanned for. If the full
`support_scenarios.jsonl` dataset is reused later (e.g. for Homework 5's
judge training/validation), a content-based re-scan should run first.

**Fixing the generator itself**: not yet done. `stage_b_situations.py`'s
fallback would need to become topic-aware (branching on
`tuple.record_state`'s topic the same way `build_coverage_tuples.py`
already branches on it when computing `outcome`/`ref`) before regenerating
would avoid reproducing this bug.
