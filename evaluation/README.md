# Cold-agent A/B evaluation

This directory contains a developmental, reproducible harness for a future
evaluation of whether ClaimPack improves an agent's transfer of an exact
scientific claim and its qualifications.

The defensible design name is:

> **Randomized A/B comparison with fresh subjects, hypothesis masking, and
> intended scorer masking.**

Participants necessarily see whether a ClaimPack supplement is present, so
they are not blind to the representation. They are not told which
representation is expected to perform better. Gold answers are withheld from
subjects. The target design withholds the allocation from the scorer until
outputs and scores are locked. The current smoke implementation does not
enforce that property: its unkeyed bundle IDs reveal the arm by reconstruction.

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
2. `RunReceipt` pins one condition-unlabelled bundle, raw answer, supervisor
   trace, runtime identity, termination, and observed unauthorized actions.
3. `ScoreReceipt` scores the answer without an explicit condition field against
   the frozen gold on separate dimensions. It contains no aggregate
   credibility score.

The explicit allocation file is added only after every scheduled raw output
and applicable score is locked. Errors and timeouts remain outcomes; retries
never replace them. That Git order does not mask the allocation because the
public, unkeyed bundle IDs can be matched against reconstructed candidate
bundles. See `COMMITMENT_MASKING_ERRATUM.md`.

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

The current provider-bound encoding,
`C001-vr2-k4-candidate-provider-v3`, and its historical
`C001-vr2-k4-candidate` predecessor use the exact public Git tree for the
unrefereed candidate claim \(\mathrm{VR}_2(K_4)=20\). It was selected because
the earlier context-free trial used z(20), not this companion claim.

Each four-run schedule assigned two fresh runs per arm on one case. The
schedules exercise bundle construction, output capture, the
score-before-repository-reveal path, and receipt handling only. They do not
validate scorer masking, cannot detect an always-`UNKNOWN` strategy, cannot
assess the truth of the underlying mathematical claim, and cannot support a
population-level ClaimPack effectiveness claim.

Before comparative publication, add genuine `ALLOW` and `DENY` controls,
wrong-encoding and retraction cases, at least three fresh runs per
case/condition, hard filesystem and network isolation, and independent
scorers.

## Recorded smoke outcomes

The repository preserves four iterations under `evaluation/results/`:

| Iteration | Locked outcome | Mechanical interpretation |
|---|---|---|
| initial | four provider schema rejections | recording complete; not semantically scorable |
| provider-v2 | four trusted-contract failures | recording complete; not semantically scorable |
| provider-v3 | two launch errors, two valid scored answers | recording complete; receipt/commitment join succeeds; not semantically scorable |
| provider-v4 | three valid scored answers, one invalid answer | recording complete; receipt/commitment join succeeds; not semantically scorable |

Provider-v3 introduced a response schema whose `trial_id` constant is bound to
the condition-unlabelled ID before the bundle manifest is sealed. Provider-v4
added an exact-invocation preflight and reached all four model sessions. Its
remaining invalid output duplicated self-reported command strings: the
provider rejected the schema's `uniqueItems` keyword, while the trusted Python
contract intentionally still enforces uniqueness.

In provider-v3 and provider-v4, applicable scores were committed before the
private allocation was copied into the repository. The reveal documents name
the exact score-lock commits. Full answers, traces, validation results,
RunReceipts, ScoreReceipts, allocation reveals, and audits are retained.
Post-reveal review also demonstrated that the public bundle commitments
themselves disclose the arms; these iterations are not scorer-masked evidence.

No efficacy inference follows. The latest run has unequal scorable counts,
only one always-`UNKNOWN` case, no independent scorer, and no statistical
power. Its traces are evidence of observed tool behavior in these sessions,
not proof of complete filesystem, network, or model-context isolation. Client
bootstrap stderr includes attempted cache and skill-root reads even though the
participant command traces remained bundle-relative.
