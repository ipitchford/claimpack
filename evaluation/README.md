# Cold-agent A/B evaluation

This directory contains a developmental, reproducible harness for a future
evaluation of whether ClaimPack improves an agent's transfer of an exact
scientific claim and its qualifications.

The defensible design name is:

> **Randomized A/B comparison with fresh subjects, hypothesis masking, and
> scorer masking.**

Participants necessarily see whether a ClaimPack supplement is present, so
they are not blind to the representation. They are not told which
representation is expected to perform better. Gold answers are withheld from
subjects. The allocation is also withheld from the arm-neutral scorer until
outputs and scores are locked.

## Arms

- `ordinary-release`: an exact Git archive plus a neutral source-identity card,
  common decision policy, matched safety canary, task, and response schema.
- `ordinary-plus-claimpack`: byte-identical ordinary material plus the
  ClaimPack records, consumer skill, cautious policy, and static catalogue.

Condition B is additive. Every fact-bearing ClaimPack record is mapped to
source prose available in the ordinary release. This first case therefore
tests the complete structured-transfer workflow against an already
AI-optimized ordinary release; it is not a comparison against a deliberately
weak README.

## Receipt chain

1. `PlanReceipt` pins the case, gold hash, prompt, schema, model/tool budgets,
   exclusion rules, scheduled trials, and a commitment to the secret
   allocation seed.
2. `RunReceipt` pins one opaque bundle, raw answer, supervisor trace, runtime
   identity, termination, and observed unauthorized actions.
3. `ScoreReceipt` scores the arm-neutral answer against the frozen gold on
   separate dimensions. It contains no aggregate credibility score.

Allocation is revealed only after every scheduled raw output and score is
locked. Errors and timeouts remain outcomes; retries never replace them.

## Safety boundary

The experiment builder and scorer are offline. They do not invoke models,
execute package code, replay certificates, render PDFs, or access the network.
Model invocation is an explicit external operator action.

A scored subject should receive only a materialized participant bundle in a
disposable workspace with no repository, gold, sibling arm, prior memory,
credentials, or network. The task prohibits those accesses and records observed
attempts, but a prompt-level prohibition is not an operating-system-enforced
network or filesystem guarantee. The first local smoke run cannot enforce every
part of that boundary and must remain labelled developmental rather than
efficacy evidence.

## Current case and limits

`C001-vr2-k4-candidate` uses the exact public Git tree for the unrefereed
candidate claim \(\mathrm{VR}_2(K_4)=20\). It was selected because the earlier
context-free trial used z(20), not this companion claim.

The first schedule contains two fresh runs per arm on one case. It validates
bundle construction, output capture, scorer masking, and receipt handling
only. It cannot detect an always-`UNKNOWN` strategy, assess the truth of the
underlying mathematical claim, or support a population-level ClaimPack
effectiveness claim.

Before comparative publication, add genuine `ALLOW` and `DENY` controls,
wrong-encoding and retraction cases, at least three fresh runs per
case/condition, hard filesystem and network isolation, and independent
scorers.
