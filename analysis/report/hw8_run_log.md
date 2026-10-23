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
