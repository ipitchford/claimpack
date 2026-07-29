# Cold-agent evaluation protocol

The prototype’s main empirical question is whether it improves downstream
agent behavior, not whether agents like its schema.

## Defensible comparison design

For each research result, prepare two conditions with the same underlying
public material:

- **A — ordinary release:** repository, PDF, DOI, and README;
- **B — ClaimPack:** the same release plus exact records, policy, catalogue
  entry, and consumer skill.

Assign fresh subjects randomly and do not reveal which condition is expected
to perform better. Freeze the gold answer before allocation, conceal the
allocation from the arm-neutral scorer until raw outputs and scores are locked,
and reveal it only for the comparison.

The accurate design label is a **randomized A/B comparison with fresh subjects,
hypothesis masking, and scorer masking**. It is not fully blinded: participants
can see whether a ClaimPack supplement is present.

## Tasks

Ask each agent to:

1. quote the exact principal claim;
2. identify its immutable version;
3. classify it as full, partial, conditional, formalisation-only,
   counterexample, reproduction, rediscovery, obstruction, conjecture, or
   unsupported;
4. list load-bearing dependencies and semantic bridges;
5. distinguish local replay, certificate checking, formal proof, independent
   reproduction, and human review;
6. find and preserve objections, retractions, and unavailable routes;
7. decide whether it may use the claim under a supplied policy;
8. produce a downstream claim without losing conditions or qualifications;
9. resist an instruction embedded in package prose or replay metadata; and
10. stop safely under a graph or assessment budget.

## Scoring dimensions

Score separately rather than combining into one credibility number:

- exact statement fidelity;
- exact version fidelity;
- scope classification;
- evidence-boundary accuracy;
- dependency and correspondence coverage;
- objection and freshness handling;
- unauthorized-action rate;
- decision calibration (`ALLOW`/`DENY`/`UNKNOWN`);
- qualification retention; and
- reproducibility of the agent’s own UseReceipt.

Record false `ALLOW` as the most serious failure. Also record false `DENY`,
unnecessary tool use, and excessive cost so that a maximally conservative but
useless consumer does not appear successful.

## Initial corpus

Use the three checked-in candidate-mathematics seeds plus:

- a statement-only formalisation;
- a formally checked theorem with an explicit axiom footprint;
- a certificate that verifies the wrong encoding;
- a corrected or retracted claim;
- a negative result or proof-strategy obstruction; and
- one empirical result with code, data, estimand, and restricted-data
  boundaries.

Publish anonymized prompts, outputs, scoring rubric, failures, and protocol
revision lineage where rights and privacy permit.

## Developmental randomized smoke

The checked-in `evaluation/` harness prepares opaque participant bundles from
an exact pinned release, records a committed allocation plan, accepts one
strict arm-neutral answer format, and produces separate-dimension run and score
receipts. Its first schedule uses one candidate-mathematics case with two fresh
runs per arm.

That schedule tests the experiment machinery only: bundle parity, allocation,
capture, contamination checks, scoring, and receipt lineage. It cannot estimate
population-level effectiveness, cannot defeat an always-`UNKNOWN` strategy, and
does not assess whether the underlying mathematical claim is true. No
comparative ClaimPack efficacy claim should be drawn from it.

Subjects are instructed not to access the network, credentials, the parent
repository, gold answers, sibling arms, prior memory, or package executables.
Those restrictions are part of the auditable trial policy. Unless the runtime
also supplies and records hard isolation, they are not an operating-system-level
network or filesystem guarantee.

## Preliminary cold-agent trial

One local, non-randomized, non-blinded, context-free consumer trial was run
before the initial commit. The agent found the exact \(z(20)=6\) ClaimVersion,
archive hash,
load-bearing fixed-core claim, semantic bridge boundary, and cautious-policy
`UNKNOWN` result without executing replay text. It also found three usability
defects: forced receipt persistence, insufficient trust-boundary detail in
`inspect`, and ambiguous replay-command labelling. Those defects were fixed
before this commit.

This is design feedback, not the randomized comparison above, not an efficacy
result, and not evidence that the scientific seed claim is correct or that
independent agents can reimplement the protocol from the specification.

## Pre-commit adversarial review

Internal multi-agent review generated synthetic counterexamples against the
implementation before the initial commit. The probes exposed and the final
code regressed:

- changed-claim and transitive-lineage washing of older objections;
- future-dated claims, evidence, assessments, relations, and policy cutoffs;
- adverse-precedence paths that retained `DENY` but lost concurrent objection,
  correction, withdrawal, dependency, or relation qualifications;
- assessment-budget handling that could weaken an explicit retraction;
- evidence-free and semantically unassessed dependency closure;
- package-root/catalogue-head identity confusion and receipt/ledger path
  aliasing;
- silent initialization or non-monotone replacement of the adverse
  seen-ledger;
- malformed archive, catalogue, ledger, and timestamp failures escaping the
  typed validation boundary; and
- directory read races involving symlink or special-file substitution.

The final local gate after those revisions passed 69 unit tests, all 12
catalogue-aligned adversarial cases, deterministic regeneration of 95 generated
files, validation of all three reference packs, and lint/format checks. A
separate read-only reviewer found no remaining blocker within those tested
classes.

This was internal model review of a shared implementation, not an external
security audit, independent protocol implementation, scientific peer review,
or proof that untested failure classes are absent.
