# Cartwheel Support Agent — Evaluating an AI Agent Before Customers Trust It

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

## What I found

**9 confirmed failure modes**, each seen at least 3 times, grouped by the fix each one needs:

| Fix needed | Failure modes | Instances in sample |
|---|---|---|
| **Tool or data schema** | The order search caps results and drops the order the customer means (16); order details the agent needs aren't exposed (6) | 22 |
| **Prompt / agent instructions** | Disputes not escalated (7); store identity not resolved (5); a write action left incomplete (5); store-specific policy override missed (4); unnecessary tool calls (4); unsound choice between candidate orders (4) | 29 |
| **Retrieval** | Searches combining "return" and "refund" crowd out the returns policy (7) | 7 |

Counts are from a deliberately stratified sample, so they show what exists, not how often it happens in production.

## The product judgements behind it

- **Classify failures by the fix, not the symptom.** The single most frequent failure wasn't a prompt problem: the order-search tool capped its results and silently dropped the customer's order. A "just improve the prompt" reflex would have missed the largest issue.
- **Severity sets the order of work.** I fixed dispute escalation first. A missed dispute can delay fraud or unauthorised-charge cases, which costs far more than a missing policy citation.
- **Draw autonomy boundaries explicitly.** Disputes and account changes always go to a person. These are trust and security decisions, so they're written into the agent's instructions rather than left to its judgement.
- **Hold an evidence bar.** A mode is confirmed only with 3 or more instances. Six further patterns stay documented as hypotheses, and one possible hallucination is recorded as a watch-item rather than promoted on a single example.
- **Don't let a target shape the answer.** The guidance suggested 5–8 modes. I tested every plausible merge against the rule "would one fix correct both?" and none qualified, so 9 is the honest count.
- **Check the raw evidence, not the summary.** I nearly downgraded one mode based on how a note was worded. Re-reading the actual conversation and its ground truth reversed that decision.
- **Know what your search tools can't see.** Similarity search found 1 useful example out of 25. Failures defined by something *missing*, like a tool call that never happened, leave no words to match on, so they have to be found by review rather than search.

## What's next

- Fix the order-search cap and expose missing order details first, since together they account for the largest share of failures.
- Build automated judges for the confirmed modes, and check each judge against human labels before trusting it (the course's next modules).
- Re-run the scenario set after each fix to confirm improvements without new regressions, the same release-gate idea as my [Prompt Eval Gate](https://github.com/aastha0208/prompt-eval-gate).

## Running it

Setup, tooling and the course structure are in [COURSE_README.md](COURSE_README.md).
