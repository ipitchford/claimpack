# Developmental smoke run lock: response-schema failure

This directory locks every raw outcome from the four trials scheduled by
`evaluation/preregistration/plan.json` before the private allocation is
revealed.

All four invocations terminated with an infrastructure error before a model
answer was produced. The provider rejected `uniqueItems` in
`RESPONSE_SCHEMA.json` as unsupported by its structured-output schema. The
empty `answer.raw` files therefore represent absence of a model answer, not an
empty scientific assessment.

No semantic ScoreReceipt was created. Each error has a RunReceipt, raw JSONL
trace, standard error, timestamps, and exit code. The four failures are
retained as scheduled outcomes and will not be replaced.

## Invocation profile

- client: `codex-cli 0.144.1`
- model: `gpt-5.6-sol`
- reasoning effort: `high`
- session: ephemeral, user configuration and repository rules ignored
- client sandbox: read-only
- participant root: one opaque committed bundle
- output: provider-validated JSON requested with `--output-schema`
- outer profile: denied reads of the ClaimPack repository, Codex memory and
  session stores, history, and the local agent-skills tree

The outer process still required outbound access to the model service. This is
not evidence of complete operating-system network isolation.

## Interpretation

This is a successful detection of a harness incompatibility, not evidence
about ClaimPack effectiveness, the behavior of a scientific consumer, or the
truth of the VR2(K4) candidate claim. A corrected run requires a new
preregistered plan and new trial identifiers.
