# HW8 run log

Every paid HW8 run, in order. Models and prices: `optimize/config.json` (development `gpt-4o-mini`; comparison `gpt-5.5`, `claude-opus-4-6`, `gpt-4o-mini`; prices checked 2026-10-22 on the OpenAI and Anthropic pricing pages, input and output only).

## Preparation

### 2026-10-23: `optimize.check_models` (live models, no search budget)

- Case e-001, 1 run per model, 3 evaluated case runs, 0 judge calls.
- gpt-5.5: finished, passed. claude-opus-4-6: finished, failed. gpt-4o-mini: finished, failed.
- Every selected model can finish a case, so no model was replaced.

### 2026-10-23: `optimize.prepare` (offline)

- Development (9): e-001, e-004, e-006, e-008 (regression), e-009, e-012, e-013, e-014, e-015. One run of all 9 is 21 evaluated case runs and 1 judge call (e-009, frozen `dispute_not_escalated` v0, `gpt-4o-mini`).
- Test (6): e-002, e-003, e-005, e-007 (regression), e-010, e-011. 14 evaluated case runs per configuration, 0 judge calls.
- Search budget: 150 evaluated case runs, 0 used.

## Part B: starting result

### 2026-10-23: `optimize.runner --split development --candidate starting` (live model, no search budget)

- Commit `2c8a034`, prompt `811782eba4b5`, model `gpt-4o-mini`. 21 evaluated case runs, 1 judge call.
- **score 0.377778, write_pass_5 0.0, cost per 100 conversations $0.05896, median latency 4.55 s.**
- Result: `optimize/results/development-starting-gpt-4o-mini-20261023-075143.json`.

| Case | Mode | Passed | Failed check |
|---|---|---|---|
| e-001 | dispute | 0/1 | no `escalate_to_human` |
| e-004 | dispute | 0/1 | no `escalate_to_human` |
| e-006 | dispute | 0/1 | no `escalate_to_human` |
| e-008 | dispute (regression) | 1/1 | |
| e-009 | dispute (judge) | 1/1 | |
| e-012 | incomplete write | 3/5 | `cancel_order` not called |
| e-013 | incomplete write | 2/5 | `issue_refund` not called |
| e-014 | incomplete write | 2/5 | `cancel_order` not called |
| e-015 | dispute | 0/1 | no `escalate_to_human` |

- Target mode on development: 2 of 6 dispute cases passed. The 4 failures all lack the `escalate_to_human` call.
- Observation on e-009: it passed, but the judge's reason says "the user did not raise a dispute." The case is the 61-day boundary (support-0059), where declining is a Pass. So the verdict may be right for the wrong reason. This matches the HW5 note that the v0 judge is noisy. Nothing was changed.
- `optimize.save_version starting` (offline) wrote `optimize/state/starting_version.json`.

## Part C: manual changes

### 2026-10-23: prompt_change (live model, no search budget)

- Commit `b0d1207`, prompt `e7558ab00320`, model `gpt-4o-mini`. 21 evaluated case runs, 1 judge call.
- Change: the Escalation section of `SYSTEM_PROMPT_TEMPLATE` now defines a dispute (a contested charge, a wrong item, delivered but not received). It says to look up the order, then escalate in the same turn without triage. It allows one clarifying question when the order is unknown, and keeps the 60-day `cw-disputes` exception.
- **score 0.755556 (starting 0.377778), write_pass_5 0.333333 (starting 0), cost per 100 conversations $0.063271 (starting $0.05896), median latency 5.75 s.**
- Result: `optimize/results/development-prompt_change-gpt-4o-mini-20261023-091904.json`.

| Case | Starting | prompt_change | Note |
|---|---|---|---|
| e-001 | 0/1 | 1/1 | escalated |
| e-004 | 0/1 | 1/1 | escalated |
| e-006 | 0/1 | 0/1 | asked for the order ID instead of using `list_my_orders`; single-turn case, so the conversation ended without escalation |
| e-008 | 1/1 | 1/1 | regression case still passes |
| e-009 | 1/1 | 1/1 | judge reason again says "no dispute raised" (the same noise as at the start) |
| e-012 | 3/5 | 2/5 | write case, untouched by the change |
| e-013 | 2/5 | 2/5 | write case, untouched |
| e-014 | 2/5 | 5/5 | write case, untouched; this alone moves write_pass_5 from 0 to 1/3 |
| e-015 | 0/1 | 1/1 | escalated |

- Target mode: dispute cases went from 2/6 to 5/6.
- The write-case changes (e-012 down by 1, e-014 up by 3) come from a change that doesn't mention cancellations or refunds, so they are most likely run-to-run noise. The write_pass_5 gain should not be credited to the prompt change.

### 2026-10-23: tool_change (live model, no search budget)

- Commit `e6a7fa9` (on top of the kept prompt change), prompt `e7558ab00320`, model `gpt-4o-mini`. 21 evaluated case runs, 1 judge call.
- Change: the `escalate_to_human` description now names disputes, says an order id is not required, and says to call the tool rather than offer it.
- **score 0.644444, write_pass_5 0.0, cost per 100 conversations $0.076439, median latency 6.45 s.**
- Result: `optimize/results/development-tool_change-gpt-4o-mini-20261023-093427.json`.

| Case | prompt_change | tool_change | Note |
|---|---|---|---|
| e-001 | 1/1 | 1/1 | |
| e-004 | 1/1 | 1/1 | |
| e-006 | 0/1 | 0/1 | found order 1085, then asked "please confirm if this is the correct order" and promised to escalate afterwards; no tool call. Not fixed |
| e-008 | 1/1 | 1/1 | |
| e-009 | 1/1 | **0/1** | scoring artefact, see below |
| e-012 | 2/5 | 3/5 | write case, noise |
| e-013 | 2/5 | 4/5 | write case, noise |
| e-014 | 5/5 | 2/5 | write case, noise; write_pass_5 back to 0 |
| e-015 | 1/1 | 1/1 | |

- **e-009 is a parser artefact, not an agent failure.**
  - The agent escalated the 61-day dispute. Under the HW5 definition, escalating past the window is a Pass for this mode (the over-escalation decision for hw5-0030).
  - The judge's own text ends "the failure is absent. Result: Pass".
  - The verdict parser (`judge_reply_with_text` in `replay/rollout.py`) looks for a JSON `"answer"` field first. This reply had none, so the fallback returns "fail" whenever the substring "fail" appears, and "failure is absent" contains it.
  - The judge also sees only the reply text and retrieved documents, not the tool calls ("the specific tool call is not shown").
  - The scoring code was not changed: every candidate must be scored the same way, and the evaluator is off-limits during the experiment. With e-009 counted as the judge intended, the score would be 0.755556, the same as prompt_change.
- Cost rose about 21% over prompt_change ($0.0633 to $0.0764), with longer conversations.
- Decision (student): **revert**. The score fell and the cost rose, and e-006, the change's target, was still not fixed. `git checkout b0d1207 -- agent/`, so `agent/` matches the prompt_change version.

### 2026-10-23: harness_change (live model, no search budget)

- Commit `27425a6` (on top of the kept prompt change; tool change reverted), prompt `e7558ab00320`, model `gpt-4o-mini`. 21 evaluated case runs, 1 judge call.
- Change: a verification step around each model call (`_EscalationCheck` in `agent/agent.py`). If a final reply contains "escalat" and `escalate_to_human` was never called in the conversation, the model gets one more call with a reminder. The draft is dropped, both calls' usage is counted, and there is one retry at most.
- Offline before the run: 5 stub-model scenarios passed. Test suite: 154 passed, 2 failed (the known Windows execute-bit test and the HW4 annotations schema test).
- **score 0.777778, write_pass_5 0.333333, cost per 100 conversations $0.081526, median latency 7.03 s.**
- Result: `optimize/results/development-harness_change-gpt-4o-mini-20261023-101704.json`.

| Case | Starting | prompt_change | harness_change | Note |
|---|---|---|---|---|
| e-001 | 0/1 | 1/1 | **0/1** | reply asks "what do you believe was incorrect?" and mentions a refund; no "escalat", so the check could not fire. A prompt-layer miss (run-to-run variation), not caused by the harness |
| e-004 | 0/1 | 1/1 | 1/1 | |
| e-006 | 0/1 | 0/1 | **1/1** | found #1085 and called `escalate_to_human` in the same turn. This is the change's target; e-006 had failed in all three earlier runs |
| e-008 | 1/1 | 1/1 | 1/1 | |
| e-009 | 1/1 | 1/1 | 1/1 | escalated; the judge text ends "Result: Pass" and parsed as a pass this time |
| e-012 | 3/5 | 2/5 | 5/5 | write case, noise |
| e-013 | 2/5 | 2/5 | 2/5 | write case |
| e-014 | 2/5 | 5/5 | 3/5 | write case, noise |
| e-015 | 0/1 | 1/1 | 1/1 | |

- Target mode: 5/6 dispute cases, the same count as prompt_change, but a different case fails (e-001 instead of e-006).
- Cost is 29% above prompt_change ($0.0633 to $0.0815). The result does not record how often the check fired, so the share caused by retries versus longer conversations is unknown.
- Decision (student): **keep**. e-006, the target pattern, flipped after failing in all three earlier runs. The check cannot change a reply that does not mention escalation, so the e-001 miss is run-to-run variation in the prompt layer. The cost rise is about $0.02 per 100 conversations.

### Part C summary

The kept agent is commit `27425a6`: the prompt change plus the harness change, with the tool change reverted. The development score went from 0.378 to 0.778, and dispute cases from 2/6 to 5/6. Single runs per dispute case mean a one-case difference between candidates is within noise. The write cases moved by up to 3 of 5 runs between candidates with no related change.

## Part D: improve loop (`.agents/skills/improve-loop/SKILL.md` with `optimize/program.md`)

The student chose the improve loop. One method only, as the handout asks. The student approves every attempt before it runs.

### 2026-10-23: loop-baseline (live model, **search budget 21**, used 21/150)

- Commit `7ecc180` (agent identical to `27425a6`), prompt `e7558ab00320`, `gpt-4o-mini`. 21 evaluated case runs, 1 judge call.
- **score 0.688889, write_pass_5 0.333333, cost per 100 conversations $0.067529.** The same agent scored 0.777778 in Part C, so two runs of an unchanged agent differ by about 0.09, roughly one case.
- Failures: e-001 0/1, e-015 0/1, e-012 2/5, e-013 4/5. e-004, e-006, e-008, e-009 and e-014 passed (e-014 5/5).
- **A shared pattern across both modes:** in every failed run the agent asks the user for the order ID ("Could you please provide me with the order ID…?") instead of searching with `find_order` or `list_my_orders`. This happened in e-001 and e-015 (disputes) and in 3 runs of e-012 and 1 run of e-013 (writes).

### 2026-10-23: loop-1-lookup-before-asking (live model, **search budget 21**, used 42/150)

- Commit `baf8aa1`, prompt `bb3e84972af0`, `gpt-4o-mini`. 21 evaluated case runs, 1 judge call.
- Change (prompt, Tool guidance): "Never ask the user for an order id before searching. Look the order up with find_order using the product, store, or other details the user gives (shoppers and merchants can also use list_my_orders). Ask only when the lookup finds no match or several equally likely matches."
- **score 0.822222 (baseline 0.688889), write_pass_5 0.333333 (unchanged), cost per 100 conversations $0.084458.**
- e-001 1/1, e-004 1/1, e-006 **0/1**, e-008 1/1, e-009 1/1, e-012 **5/5**, e-013 3/5, e-014 4/5, e-015 1/1.
- Keep rule (score up, write_pass_5 not down): **keep**.
  - The gain (+0.13, about 1.2 cases) is only a little above the 0.09 run-to-run spread seen for the unchanged agent, so it is treated with caution.
  - The supporting evidence is in the replies: no run asked for an order id before searching. e-001 and e-015 looked the order up and escalated, and e-012 went from 2/5 to 5/5.
- Remaining failures:
  - e-006: `find_order("stationery")` found nothing, because product titles do not contain "stationery". The agent then asked the user instead of trying `list_my_orders`. It had written "I will escalate" earlier in the turn, but the final model response did not contain the word, so the harness check (which reads only the final response) did not fire.
  - e-013: 2 runs asked the user for a return reason instead of issuing the refund. That is the `incomplete_write_left_undone` pattern, not the target.

### 2026-10-23: loop-2-list-orders-fallback (live model, **search budget 21**, used 63/150)

- Commit `119579f`, prompt `459400f4eca3`, `gpt-4o-mini`. 21 evaluated case runs, 1 judge call.
- Change (prompt, Tool guidance): "If find_order finds no match, shoppers and merchants call list_my_orders and look for the order there before asking the user."
- **score 0.8 (best 0.822222), write_pass_5 0.333333, cost per 100 conversations $0.091718.**
- e-001 1/1, e-004 1/1, e-006 **0/1**, e-008 1/1, e-009 1/1, e-012 2/5, e-013 4/5, e-014 5/5, e-015 1/1.
- Keep rule: the score did not improve, so **revert**. `git checkout baf8aa1 -- agent/`.
- e-006, the target, still failed. The reply says "I couldn't find any order for stationery under your account". `list_my_orders` results carry product ids, not product names, so a lookup by product type cannot match even when the agent tries it. That makes this the wrong layer for the fix. e-012 fell from 5/5 to 2/5: in 3 runs it found order 4137 (placed) and described it without calling `cancel_order`. That pattern is unrelated to this change and most likely noise.
- First consecutive non-improving attempt. Under `program.md` (via the skill), one more non-improving attempt stops the loop.
