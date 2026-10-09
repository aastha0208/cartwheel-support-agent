# Monitoring dispute_not_escalated

> **Draft for review.** Written by Claude from Aastha's review of the flagged conversations. To be checked and rewritten by Aastha before submission.

The monitor compares two runs of the same 50 scenarios on `claude-opus-4-6`: the Homework 3 run (before) and a new run (after). The agent did not change between them. The frozen judge is `dispute_not_escalated-v0` (`gpt-4o-mini`). A random 20% sample (10 conversations) estimates the failure rate; the risk groups are judged for inspection only. Details are in `analysis/report/hw7_run_log.md`.

| Period | Random sample flagged | Raw | Corrected | 95% interval | Threshold 0.15 | After my review |
|---|---|---|---|---|---|---|
| before | 1 / 10 | 0.10 | 0.00 | 0.00 to 0.24 | not crossed | 1 / 10 = 0.10 |
| after | 3 / 10 | 0.30 | 0.20 | 0.00 to 0.55 | crossed | 1 / 10 = 0.10 |

The first six columns are what the monitor produced. The last column counts the flags I confirmed as real failures after reading each flagged conversation. The judge caught every real failure in its Homework 5 test, so the conversations it passed are counted as passes.

## 1. Did the corrected failure estimate move between the two periods?

On paper, yes: from 0% to about 20%, which crossed the 15% threshold. On review, no real change. Both periods have the same real failure, support-0220, where a customer disputed a charge and the agent did not escalate it. The two extra flags in the after period, support-0014 (a cancellation) and support-0072 (a return), are not disputes, so they are judge false alarms. The judge passed both of them in the before period and again when the after period was re-judged.

After review, both periods have 1 real failure in 10 (10%), below the threshold. The correction could not know which flags were false: it removed about one expected false alarm in the after period (giving 20%), and in the before period it removed the only flag even though that flag was real (giving 0%). It is right on average, not for each small sample, which is why flagged conversations need a human review.

## 2. Do the intervals support a conclusion, or is the result uncertain?

The result is uncertain. With only 10 conversations per period, the intervals are wide (0% to 24% before, 0% to 55% after). They overlap, and both include 0% and the 15% threshold. So the numbers alone cannot show that the failure rate changed; the review of the flagged conversations shows that it did not. The reviewed rate is still uncertain: 1 in 10 has a 95% interval of about 0.3% to 45%.

## 3. What did the risk groups reveal that the random estimate did not?

- Every flagged risk-group conversation, in both periods, came from my custom group `order_lookup_no_escalation` (the agent found an order but never escalated). The course groups flagged one conversation in total (support-0072 in `policy_lookup`, a false alarm).
- They found a real failure the random sample missed: support-0035, flagged in both periods and outside the random sample. The customer said they were charged the wrong amount, which is a dispute; the agent checked the price, said the charge was correct, and never called `escalate_to_human`. I added it to the Homework 6 eval suite as `e-015`; in its five baseline runs the agent escalated 2 times out of 5, so it is a capability case (pass rate 0.4).
- They also flagged support-0004 and 0005 in the before period. These are not reviewed yet.
- The flagged share in the risk groups stayed the same (4 of 27 before, 4 of 26 after), which agrees with the review: no sign that the agent got worse. This share is not a failure rate, because the groups are chosen on purpose.

## 4. What action should happen if the estimate crosses the threshold?

Start error analysis on the flagged conversations, as I did here:

1. Read each flagged random-sample conversation and decide whether it is a real failure or a judge false alarm.
2. Add each confirmed failure to the Homework 6 eval suite, unless it is already there. support-0220 is already case `e-002` (capability, 0 of 5 passes at baseline). support-0035, found through the risk groups, was not covered, so it became case `e-015` (capability, 2 of 5 passes at baseline).
3. Record false alarms against the judge. If they keep appearing, re-check the judge's accuracy on new labeled data.
4. Read the risk-group flags for failures the random sample missed.
5. Because 10 conversations give a wide interval, a larger sample would make the next estimate more precise.
