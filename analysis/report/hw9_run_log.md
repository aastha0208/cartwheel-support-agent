# HW9 run log: reducing cost

Every paid run for Homework 9, in order, with the decisions made along the way. Development cases only (9 cases, 21 evaluated case runs). Baseline: the HW8 final run, `development-final-gpt-4o-mini-20261023-141310.json` (commit `116bad6`).

## Part A: cost profile (2026-10-26, offline, no model calls)

- `profile/scripts/build_costs.py` writes `profile/results/costs.csv`, one row per call site and run group.
- Customer conversation calls about $28.26 in total, judge calls about $0.20. All of the most expensive rows are `claude-opus-4-6` agent runs: HW3 scenarios through `server/app.py:215` ($11.96), HW6 Harbor runs ($10.17).
- Judge token counts were not saved by the HW5/HW6/HW7 runs, so judge rows are tiktoken estimates (lower bounds).

## Part B: fewer tokens

Offline look at the HW3 traces and the HW6 Harbor transcripts of the 9 development cases: tool results are sent to the model as Python `str(dict)`. Compact JSON carries the same fields in 18% fewer tokens (74,561 to 61,141 over the saved dev-case tool results). The student chose to stack two single changes: G (compact JSON) first, then A1 (drop `product_id` and `shipped_at` from the model-facing `find_order` result).

### Run 1: fewer-tokens (G, compact JSON tool results) (2026-10-26, live model)

- Commit `c1706ea`. `_call` and the `search_products` wrapper return `_CompactResult`, a dict whose `str()` is compact JSON. Tracing, replay checks, and `tools.find_order` (HW1 contract) unchanged.
- Offline before the run: 154 passed, 2 failed (the known Windows execute-bit test and the HW4 annotations schema test), 17 skipped.
- `gpt-4o-mini`, 21 evaluated case runs, 1 judge call (e-009).
- Result: `optimize/results/development-fewer-tokens-gpt-4o-mini-20261026-094045.json`.

| | HW8 final | fewer-tokens |
|---|---|---|
| score | 0.666667 | 0.466667 |
| write_pass_5 | 0 | 0 |
| input tokens | 91,212 | 88,065 |
| cached input tokens | 56,192 (0.616) | 54,528 (0.619) |
| output tokens | 4,882 | 4,525 |
| cost per 100 conversations | $0.0791 | $0.075832 |
| median latency | 5.32 s | 5.85 s |

| Case | HW8 final | fewer-tokens |
|---|---|---|
| e-001 | 1/1 | 0/1 (looked up #6097, asked what the discrepancy is; no `escalate_to_human`) |
| e-004 | 1/1 | 1/1 |
| e-006 | 0/1 | 0/1 |
| e-008 | 1/1 | 1/1 |
| e-009 | 1/1 | 0/1 (judge text ends "Result: Pass"; parsed as fail) |
| e-012 | 3/5 | 4/5 |
| e-013 | 3/5 | 3/5 |
| e-014 | 4/5 | 4/5 |
| e-015 | 0/1 | 0/1 |

- Student decision after run 1: rerun the same commit once to see whether the drop repeats (the e-009 fail is the verdict-parser artefact from HW8: the fallback finds "fail" in "no failure regarding escalation"; the e-001 miss matches the HW8 harness_change miss).

### Run 2: fewer-tokens-rerun (same commit `c1706ea`) (2026-10-26, live model)

- `gpt-4o-mini`, 21 evaluated case runs, 1 judge call (e-009).
- Result: `optimize/results/development-fewer-tokens-rerun-gpt-4o-mini-20261026-101312.json`.

| | HW8 final | fewer-tokens | fewer-tokens-rerun |
|---|---|---|---|
| score | 0.666667 | 0.466667 | 0.555556 |
| write_pass_5 | 0 | 0 | 0 |
| input tokens | 91,212 | 88,065 | 92,215 |
| cached input tokens | 56,192 (0.616) | 54,528 (0.619) | 57,472 (0.623) |
| output tokens | 4,882 | 4,525 | 4,901 |
| cost per 100 conversations | $0.0791 | $0.075832 | $0.079871 |
| median latency | 5.32 s | 5.85 s | 6.19 s |

| Case | HW8 final | fewer-tokens | rerun |
|---|---|---|---|
| e-001 | 1/1 | 0/1 | 1/1 |
| e-004 | 1/1 | 1/1 | 1/1 |
| e-006 | 0/1 | 0/1 | 0/1 |
| e-008 | 1/1 | 1/1 | 1/1 |
| e-009 | 1/1 | 0/1 | 0/1 (judge text "...the failure is absent. Result: Pass"; parsed as fail again) |
| e-012 | 3/5 | 4/5 | 4/5 |
| e-013 | 3/5 | 3/5 | 4/5 |
| e-014 | 4/5 | 4/5 | 2/5 |
| e-015 | 0/1 | 0/1 | 0/1 |

- Decision (student): **revert G**. Neither run met the keep rule (run 1: cost lower, score lower; run 2: cost, latency higher, score lower). Same code moved 0.467 to 0.556 and input tokens by 4,150, so G's offline saving (about 2,000 to 3,000 tokens over 21 runs) is below the run-to-run swing. `agent/agent.py` restored to the HW8 final agent, commit `63d0d80`.

### Run 3: fewer-tokens-a1 (A1, drop `product_id` and `shipped_at` from the model-facing `find_order` result) (2026-10-26, live model)

- Commit `e8b4380` on top of the revert. Trimmed in the `find_order` SDK wrapper in `agent/agent.py`; `tools.find_order` keeps the HW1 contract.
- Offline before the run: 154 passed, 2 failed (same known tests). Saved dev-case `find_order` results: 221 to 175 tokens per result (21%), 7.5% of all tool-result tokens.
- `gpt-4o-mini`, 21 evaluated case runs, 1 judge call (e-009). Compared with the HW8 final run.
- Result: `optimize/results/development-fewer-tokens-a1-gpt-4o-mini-20261026-102420.json`.

| | HW8 final | fewer-tokens-a1 |
|---|---|---|
| score | 0.666667 | 0.733333 |
| write_pass_5 | 0 | 0.333333 |
| input tokens | 91,212 | 103,893 |
| cached input tokens | 56,192 (0.616) | 69,120 (0.665) |
| output tokens | 4,882 | 5,613 |
| cost per 100 conversations | $0.0791 | $0.090246 |
| median latency | 5.32 s | 6.67 s |

| Case | HW8 final | fewer-tokens-a1 |
|---|---|---|
| e-001 | 1/1 | 1/1 |
| e-004 | 1/1 | 1/1 |
| e-006 | 0/1 | 0/1 (found no "stationery" order, asked for details; no escalation) |
| e-008 | 1/1 | 1/1 |
| e-009 | 1/1 | 0/1 (judge text ends "Result: Pass"; parsed as fail, third run in a row) |
| e-012 | 3/5 | 4/5 |
| e-013 | 3/5 | 5/5 |
| e-014 | 4/5 | 4/5 |
| e-015 | 0/1 | 1/1 |

- Why input tokens rose although each `find_order` result shrank: A1 removes about 2,000 tokens per 21 runs, but more runs completed their write or escalation (e-013 3/5 to 5/5, e-012 3/5 to 4/5, e-015 now escalates). Each extra tool call is one more model call that re-reads 3,000 to 4,000 tokens. Estimate only: per-case token counts are not saved, and run-to-run noise is about 4,000 input tokens.
- Decision (student): **revert A1**, because the cost did not go down (cost and latency both rose; score and write_pass_5 rose, likely by chance). `agent/agent.py` restored to the HW8 final agent, commit `fc3c32c`.
- Part B outcome: both single changes were reverted; the agent is the HW8 final agent.

## Part C: prompt order for caching

- Model `gpt-4o-mini` (OpenAI, caches automatically from a 1,024-token prefix; also the HW8 development model). Added `"cached_input": 0.075` to its prices in `optimize/config.json` (OpenAI's cached input price; student to confirm on the pricing page).
- Starting order: tool definitions (~840 tokens), then the system prompt, whose `## Session context` block (role, user id, store id) sits after the two intro lines. Prefix shared across different users ≈ 880 tokens, under 1,024.

### Run 4: cache-before (unchanged HW8 agent) (2026-10-26, live model)

- Commit `6aee53c` (agent identical to `116bad6`, prompt `bb3e84972af0`). `gpt-4o-mini`, 21 evaluated case runs, 1 judge call.
- Result: `optimize/results/development-cache-before-gpt-4o-mini-20261026-104758.json`.
- **score 0.955556, write_pass_5 0.333333, input 105,204, cached 67,072 (cached_fraction 0.637542), output 5,275, cost $0.013915, $0.066263 per 100 conversations, median latency 6.82 s.**
- Cases: all single-run cases passed (e-006 and e-015 for the first time in HW9; e-009 parsed as Pass); e-012 4/5, e-013 5/5, e-014 4/5.
- The same agent scored 0.666667 in the HW8 final run: the run-to-run spread of the unchanged agent on these 9 cases is at least 0.29.

### Run 5: cache-after (Session context moved to the end, no wording change) (2026-10-26, live model)

- Commit `a73dd52`, prompt `e7aa81a7f464` (same lines as `bb3e84972af0`, reordered; checked offline). Offline tests: 154 passed, 2 failed (same known tests).
- Offline estimate of the prefix shared by different users after the move: tool definitions (~938 tokens shopper/merchant, ~862 support) + static prompt (~603) ≈ 1,465 to 1,541 tokens, above OpenAI's 1,024 minimum. Before the move the shared part of the system prompt was ~36 tokens.
- `gpt-4o-mini`, 21 evaluated case runs, 1 judge call.
- Result: `optimize/results/development-cache-after-gpt-4o-mini-20261026-112248.json`.

| | cache-before | cache-after |
|---|---|---|
| score | 0.955556 | 0.822222 |
| write_pass_5 | 0.333333 | 0.333333 |
| input tokens | 105,204 | 107,457 |
| cached input tokens | 67,072 | 67,968 |
| cached_fraction | 0.637542 | 0.632513 |
| output tokens | 5,275 | 4,915 |
| cost per 100 conversations | $0.066263 | $0.066524 |
| median latency | 6.82 s | 6.47 s |

- Cases: e-014 4/5 to 3/5, e-015 1/1 to 0/1; all others unchanged.
- Why cached_fraction did not rise: most cached tokens already came from repeats of the same user (later calls in one conversation, and the five runs of each write case), which the move does not change. The move only helps the first call after the user changes, about 8 times in 21 runs (at most ~11,000 tokens, cached_fraction ~0.73); those calls were not cached either, likely because OpenAI caching is best effort and a small, low-traffic run rarely reaches the same cache server.
- Decision (student): **revert** by the handout rule (score dropped, 0.955556 to 0.822222), and cached_fraction and cost did not improve. The drop is probably noise (the unchanged agent varied by 0.29). `agent/agent.py` restored to the HW8 final agent.
