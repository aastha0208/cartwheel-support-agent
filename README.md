# Cartwheel Support Agent — Evaluating and Improving an AI Agent Before Customers Trust It

> **Product case study.** Built during *AI Evals for Engineers & PMs* (Hamel Husain & Shreya Shankar, Sept–Oct 2026). The course provides the Cartwheel platform and the starter agent; the analysis, decisions and tooling described below are mine. The course's own setup guide is in [COURSE_README.md](COURSE_README.md).

## The product

Cartwheel is a fictional commerce platform that hosts independent stores. Its AI support agent helps shoppers with orders, returns and refunds. It looks up orders, searches store policies, queues refunds, and hands off to a person when it shouldn't act alone.

That last part is the product problem. A support agent that is helpful but wrong about a refund, or confident about an account change it has no business touching, costs more customer trust than it saves in support time.

**The question I worked on:** where should this agent act on its own, where must it escalate to a person, and how do you know whether it's actually behaving that way?

## What I did

| Stage | What I did | Where |
|---|---|---|
| Find the first failures | Built the agent's support tools, ran real conversations, and found 6 failures against the agent's spec. Grouped them by cause and ranked them by severity. | [`hw1-failure-analysis.md`](hw1-failure-analysis.md) |
| Fix what matters most first | Fixed the two highest-severity gaps (disputes and account changes weren't reliably escalated) with minimal prompt changes, then re-ran the same conversations to confirm the before-and-after. | [`hw1-failure-analysis.md`](hw1-failure-analysis.md) |
| Make behaviour observable | Instrumented the agent so every conversation is recorded as a trace that can be reviewed later. | `observability/`, [`hw2-traces.json`](hw2-traces.json) |
| Build realistic test conditions | Generated 250 support scenarios across customer roles and situations, plus pilot rounds, and documented a defect I found in the scenario generator. | `scenarios/`, [`KNOWN_ISSUES`](scenarios/support_scenarios.KNOWN_ISSUES.md) |
| Systematic error analysis | Reviewed 108 conversations in four deliberately designed batches and built a taxonomy of 9 confirmed failure modes, each tied to the kind of fix it needs. | [`review_summary.md`](analysis/report/review_summary.md) |
| Better review tooling | Built a review interface that reassembles multi-turn conversations and shows what each tool call actually returned, after the stock tracing UI made review slow. | `analysis/review_app/`, [`interface_comparison.md`](analysis/report/interface_comparison.md) |
| Automate the judgement call | Wrote a precise failure definition for missed dispute escalations, built an LLM judge for it, and validated it against my own labels on a held-out test set before trusting it. | [`hw5_failure_definition.md`](analysis/report/hw5_failure_definition.md), [`hw5_run_log.md`](analysis/report/hw5_run_log.md) |
| Gate releases on evidence | Turned confirmed failures into 15 eval cases with code-based checks, ran each case 5 times to separate reliable behaviour from luck (pass@k), and wired them into a CI quality gate on every pull request. | `eval_cases/`, [`.github/workflows/evals.yml`](.github/workflows/evals.yml), [`hw6_run_log.md`](analysis/report/hw6_run_log.md) |
| Watch for drift | Built a monitor that samples conversations, scores them with the judge, corrects the raw rate for the judge's known error, and alerts above a threshold. Reviewed every flag by hand. | [`monitoring/`](monitoring/README.md), [`hw7_run_log.md`](analysis/report/hw7_run_log.md) |

## What I found

**9 confirmed failure modes**, each seen at least 3 times, grouped by the fix each one needs:

| Fix needed | Failure modes | Instances in sample |
|---|---|---|
| **Tool or data schema** | The order search caps results and drops the order the customer means (16); order details the agent needs aren't exposed (6) | 22 |
| **Prompt / agent instructions** | Disputes not escalated (7); store identity not resolved (5); a write action left incomplete (5); store-specific policy override missed (4); unnecessary tool calls (4); unsound choice between candidate orders (4) | 29 |
| **Retrieval** | Searches combining "return" and "refund" crowd out the returns policy (7) | 7 |

Counts are from a deliberately stratified sample, so they show what exists, not how often it happens in production.

## What the evaluation system showed

- **The gate works.** I deliberately shipped a one-line prompt change telling the agent not to escalate merchant-reported disputes. CI blocked it: the two regression cases dropped from 5/5 to zero passes. After the revert, both returned to 5/5 and the gate passed.
- **The judge is trustworthy for flagging, not for final calls.** On 52 held-out conversations it caught all 13 real failures, but wrongly failed 5 of 39 good ones (all refund requests where the agent offered escalation). So it flags conversations for a person to review; it doesn't decide alone.
- **Explicit disputes escalate; hedged ones don't.** "My customer has a dispute" escalated 5/5. "I think I was charged wrong" escalated 0/5 across five cases: the agent checked the price, declared the charge correct and moved on. That gap was invisible in the original handful of test conversations.
- **One passing run proves little.** A cancellation case that passed once in review passed only 8 of 15 runs. I now classify every case from repeated runs, and it took 10 runs before the pass rate stabilised.
- **A monitor alert isn't a finding until someone reads it.** The monitor crossed its 15% threshold in the second period. Reading the three flagged conversations showed two judge false alarms and the same one real failure as before, so the agent hadn't regressed. The custom risk group I added caught a real failure the random sample missed, which became a new eval case.

## The product judgements behind it

- **Classify failures by the fix, not the symptom.** The single most frequent failure wasn't a prompt problem: the order-search tool capped its results and silently dropped the customer's order. A "just improve the prompt" reflex would have missed the largest issue.
- **Severity sets the order of work.** I fixed dispute escalation first. A missed dispute can delay fraud or unauthorised-charge cases, which costs far more than a missing policy citation.
- **Draw autonomy boundaries explicitly.** Disputes and account changes always go to a person. These are trust and security decisions, so they're written into the agent's instructions rather than left to its judgement.
- **Hold an evidence bar.** A mode is confirmed only with 3 or more instances. Six further patterns stay documented as hypotheses, and one possible hallucination is recorded as a watch-item rather than promoted on a single example.
- **Don't let a target shape the answer.** The guidance suggested 5–8 modes. I tested every plausible merge against the rule "would one fix correct both?" and none qualified, so 9 is the honest count.
- **Check the raw evidence, not the summary.** I nearly downgraded one mode based on how a note was worded. Re-reading the actual conversation and its ground truth reversed that decision.
- **Know what your search tools can't see.** Similarity search found 1 useful example out of 25. Failures defined by something *missing*, like a tool call that never happened, leave no words to match on, so they have to be found by review rather than search.

## Status and roadmap

The evaluation loop is built end to end for the highest-severity failure mode, missed dispute escalation, with a second mode (write actions left incomplete) covered in the eval suite.

- [x] **Error analysis:** 9 failure modes identified, confirmed and tied to the fix each needs
- [x] **First fixes:** dispute and account-change escalation corrected for the conversations reviewed
- [x] **Automated evaluators:** 15 eval cases with code-based checks (was the escalation tool called, were any write tools used), each classified from repeated runs as a regression or capability case
- [x] **LLM-as-judge:** a judge for missed dispute escalations, validated against my human labels on a held-out test set ([results](analysis/report/hw5_run_log.md))
- [x] **CI/CD quality gate:** offline checks on every push and the full eval suite on every pull request, blocking changes that break regression cases, the same release-gate idea as my [Prompt Eval Gate](https://github.com/aastha0208/prompt-eval-gate)
- [x] **Monitoring:** sampling, judge scoring, error-corrected failure rates, a threshold alert and a dashboard, run across two periods of simulated traffic ([results](monitoring/README.md))

**Next**

- Close the hedged-dispute gap: the agent should escalate "I think I was charged wrong" as reliably as an explicit dispute. The capability cases (0–2 of 5 passing today) measure the fix.
- Fix the order-search cap and expose the missing order details, which together account for the largest share of failures in the error analysis.
- Extend evaluators to the remaining failure modes, starting with the retrieval issue.

## Running it

Setup, tooling and the course structure are in [COURSE_README.md](COURSE_README.md).
