# HW5 judge run log: `dispute_not_escalated`

Every judge run, in order. Labels: 1 = Pass (failure absent), 0 = Fail. Pass is the positive class: TPR is measured on human Pass labels, TNR on human Fail labels. Intervals are Wilson 95%. All runs used `gpt-4o-mini` through DocETL on the saved inputs in `analysis/state/hw5_trace_inputs.json`.

Split (seed 7): train 26 (20 Pass, 6 Fail), dev 51 (39 Pass, 12 Fail), test 52 (39 Pass, 13 Fail). Test is locked until a version is frozen.

## Summary

| # | Date (UTC) | Run | Prompt (hash) | Traces | TPR | TNR | Disagreements | Saved in |
|---|---|---|---|---|---|---|---|---|
| 1 | 2026-10-01 | v0 dev (official) | `dispute_not_escalated-v0.txt` (`e9c84f22bf7b`) | 51 dev | 39/39 = 1.00 [0.91, 1.00] | 12/12 = 1.00 [0.76, 1.00] | 0 | `dev-dispute_not_escalated-v0.json`, `state/judges/dispute_not_escalated-v0.json` |
| 2 | 2026-10-01 | v1 dev (official, revision 1 of 2) | `dispute_not_escalated-v1.txt` (`2277c810236e`) | 51 dev | 37/39 = 0.95 [0.83, 0.99] | 11/12 = 0.92 [0.65, 0.99] | 3 | `dev-dispute_not_escalated-v1.json`, `state/judges/dispute_not_escalated-v1.json` |
| 3 | 2026-10-01 | v0 stability rerun (not an official version) | same v0 prompt (`e9c84f22bf7b`) | 51 dev | 37/39 = 0.95 [0.83, 0.99] | 12/12 = 1.00 [0.76, 1.00] | 2 | `dev-dispute_not_escalated-v0-stability.json` |

## Run 1: v0 on dev

- Setup issues before scoring (no model charges for these): `OPENAI_API_KEY` was empty in `.env`; a Windows console encoding error in DocETL's syntax check (fixed with UTF-8 output); OpenAI free tier limit of 50 requests per day (student added credit; Tier 1 applied after about 30 minutes). 10 traces were scored before the limit and kept.
- Output glitch: trace `37501858` (merchant dispute, escalated) came back with result "Not found". The critique was correct but pasted tool-call JSON and was cut off, so DocETL filled the missing result. A plain retry returned DocETL's cached copy of the bad answer; a retry with an empty cache folder gave a valid Pass.
- Result: 0 disagreements.
- Critique review (student and assistant): support-0092 (cancellation request) and support-0177r (policy question about the dispute window) reasoned correctly. **hw5-0034** got the right verdict (Pass) for the wrong reason: "no explicit dispute raised", although hedged wording ("one of the charges seems off") is a dispute under the definition.
- Dev mix noted: most dev traces are easy (no complaint, or `escalate_to_human` plainly present). Only hw5-0034 (Pass) and one queued-refund Fail (hw5-0026) exercise a boundary rule.

## Decision after run 1

- Student clarified the rule for an unidentified order (recorded in `hw5_failure_definition.md`): a dispute; the agent may ask at most one clarifying question and must not triage; after the user replies it escalates (with the order if identified, anyway if not). A trace that ends right after the one question is Pass; what happens after the trace ends is not evaluated.
- No labels changed (hw5-0034 is the only labeled trace this rule covers; it stays Pass).
- v1 written: three lines changed from v0 (hedged disputes count even when the order is unknown; the clarifying-question Pass rule; a Fail line for a second question, triage, or no escalation after the reply). A phrase first copied from hw5-0034 was replaced with generic wording to keep dev text out of the prompt.

## Run 2: v1 on dev

- Output glitch again on trace `2fc380d8` (critique pasted tool-call JSON, result "Not found"); fixed by a retry with an empty cache folder.
- Disagreements:
  - **hw5-0034** (human Pass, judge Fail): now recognises the dispute, but fails the agent for not escalating; it did not apply the new one-question Pass rule.
  - **hw5-0036** (human Fail, judge Pass): merchant relays "thinks they were overcharged"; judge says "the user did not raise a specific dispute". Judge error; v0 got it right.
  - **support-0057** (human Pass, judge Fail): merchant refund question on an order outside their store (`permission_denied`); judge calls it a contested order. Judge error; v0 got it right. The evidence shown for this label is a HW4 note about other modes; student to confirm the HW5 Pass label.
- Observation: a three-line change flipped two unrelated traces and did not fix hw5-0034.

## Run 3: v0 stability rerun

- Purpose: check whether v0's perfect score repeats. Run outside the judge registry (the helper caches results per version, so an official rerun would make no calls); the official v0 record is unchanged.
- One batch hit the output glitch (trace `3a70d592`) and was retried in a new process.
- Verified: same prompt text and hash as run 1.
- Verdicts differing from run 1: 2.
  - **hw5-0034** (human Pass, judge Fail): same error as v1.
  - **support-0056** (human Pass, judge Fail): merchant asks about another store's order. The critique says "does not directly constitute a dispute", yet the verdict is Fail (critique and verdict contradict).

## Findings so far

- `gpt-4o-mini` is not deterministic here: the same prompt on the same traces changed about 2 of 51 verdicts between runs. The v0 vs v1 difference is mostly within this noise.
- hw5-0034 (dispute with an unidentified order, one clarifying question, trace ends) is unstable under both prompts.
- The output glitch (critique pastes tool-call JSON and is cut off) happened once in each of the three runs; retrying with an empty DocETL cache fixed it each time.
- Possible improvement not applied: setting the judge's temperature to 0 would require changing the course helper code.

## Label follow-up after run 3

- support-0057: student confirmed Pass (refund request on another store's order, `permission_denied`; no dispute raised). Appended a HW5 evidence record (`label_id` `#1`, label unchanged at 1); the HW4-seeded record stays in the history. Metrics unaffected.

## Freeze

- 2026-10-01 16:37 UTC: student froze **v0** (`e9c84f22bf7b`, `gpt-4o-mini`). Reason: best official dev result; v1 did not fix hw5-0034 and flipped two unrelated traces; the v0 stability rerun showed run-to-run variation of about 2/51, so further wording changes were unlikely to help. Revision 2 left unused. A third v0 dev run was skipped: it would not change the decision.

## Run 4: frozen v0 on test (the single test run)

- 2026-10-01, `gpt-4o-mini`, 52 test traces (39 Pass, 13 Fail). Saved in `test-dispute_not_escalated-v0.json` and `state/judges/dispute_not_escalated-v0.json`.
- Output glitch twice (traces `2ed56ad1`, then `45123bc6`); each failed batch was retried with the same frozen prompt and an empty cache folder. Completed batches were kept, so no trace was scored twice. Technical retries only; the judge was not changed.
- **Result: TPR 34/39 = 0.87 [0.73, 0.94]; TNR 13/13 = 1.00 [0.77, 1.00]; agreement 47/52.** Confusion: TP 34, FN 5, TN 13, FP 0.
- All 5 disagreements are false Fails (human Pass, judge Fail), and all are refund requests, not disputes, where the agent mentioned disputes or offered to escalate:
  - **support-0139**: merchant relays a refund request on an ineligible order; agent explains the dispute option and offers escalation. Judge applied the "only offers to escalate" Fail rule although no dispute was raised.
  - **support-0124**: shopper wants a refund; order ineligible; agent offers to escalate. Judge calls the refund request "the dispute raised".
  - **support-0081**: shopper confused, asks for a $500 refund on a $186.50 order. Judge reads "something off about the price" as a dispute. Closest to a genuine boundary case.
  - **support-0135**: merchant refund question on a shipped order. Critique says the agent "does not identify any dispute", yet the verdict is Fail (critique and verdict contradict).
  - **support-0037**: merchant refund request, ineligible order. Critique says it "does not constitute a clear dispute", yet the verdict is Fail (critique and verdict contradict).
- Pattern: the judge never missed a real failure on test, but over-flags refund requests where the agent offers escalation or mentions the dispute policy. This is the boundary training Example 4 (support-0122) was meant to teach; it did not hold on test. Two of five verdicts contradict their own critiques.
- No prompt changes after this run (test is used once).

## Decision: would I use the judge?

**Yes, to flag conversations, with a person reviewing its verdicts and critiques.** It shouldn't make final decisions on its own.

**Evidence (frozen v0 on test, 52 traces: 39 Pass, 13 Fail):**
- **TNR 13/13 = 1.00 [0.77, 1.00].** It caught every real failure. But with only 13 Fail traces, the true rate could be as low as about 0.77, so a reviewer should also spot-check some conversations it passed.
- **TPR 34/39 = 0.87 [0.73, 0.94].** It wrongly failed 5 good conversations. All 5 were refund requests, not disputes, where the agent mentioned the dispute policy or offered to escalate. Example: in support-0139 the agent correctly offered escalation and waited for the merchant's answer, and the judge failed it.
- In 2 of those 5 (support-0135, support-0037), the critique says no dispute was raised, yet the verdict is Fail. A reviewer needs to read both the critique and the verdict.
- Run-to-run variation: the same prompt changed about 2 of 51 dev verdicts between runs, so any single verdict is somewhat noisy.

**Why a reviewer makes this usable:**
- The false alarms follow one recognizable pattern, so a reviewer can dismiss them quickly.
- No real failure got through on test.
- Using the judge's raw Fail count as a failure rate would overstate failures. Any rate reported from it should be corrected with the test TPR and TNR.

## Why I stopped revising

- v1 (three clarified lines) did not fix hw5-0034 and flipped two unrelated traces.
- The v0 stability rerun showed that the difference between v0 and v1 was mostly within run-to-run noise. Further wording changes were unlikely to help.
- The prompt already states the rule the judge broke on test ("the agent mentioning the word 'dispute' does not make it one", plus training Example 4). The judge had the guidance and didn't apply it consistently.
- Test was used once, as required. No changes were made after seeing the results.

## What I would do next

1. Check `escalate_to_human` with code instead of asking the model; it's an exact yes/no fact in the trace.
2. Ask the judge only one question: did the user raise a dispute (a wrong charge, a wrong item, or a delivered order that never arrived)?
3. Try a more capable judge model to reduce flips and critique/verdict contradictions.
4. Label more refund requests and more Fail cases, so this weakness shows up during development and the intervals narrow.
5. Measure the new version on freshly labeled traces, not on this test set.

## Limitations

- Traces sometimes end mid-conversation, so the judge can't see failures that would have happened afterward.
- The late-shipment rule was never tested: the data has no overdue orders.
- Dev had few boundary cases (mainly hw5-0034 and hw5-0026), so dev results looked better than test.
- The temperature setting was not changed; it would require editing the course helper.

## Recalculating the test metrics

`uv run python -m analysis.run_judges recalc` recomputes the test result from the saved predictions and labels (offline, no model call, writes nothing). Checked 2026-10-02: TP 34, FN 5, TN 13, FP 0; TPR 34/39 = 0.87 [0.73, 0.94]; TNR 13/13 = 1.00 [0.77, 1.00].

## Pending
- Student: the video.

## Committed
- 2026-10-02: Part E files committed (`972cdf8`).
