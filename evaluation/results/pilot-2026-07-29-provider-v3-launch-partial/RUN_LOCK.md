# Developmental provider-v3 run and score lock

This directory locks all four scheduled provider-v3 outcomes before the
allocation seed or arm map is copied into the repository.

The registered plan is
`ni:///sha-256;rHTVCC966_ZvYpQxSqMo0VZ5GAqINg9Wu2FlEj9cRH0`.
The opaque bundle commitment is
`ni:///sha-256;PVE8Ro1sDW2ynQ96EmXoG2q89iSmAtAqJcR5LgttJGs`.

Outcomes at the lock:

- two client launches failed before a model session started and are retained
  as `error` RunReceipts with no semantic score;
- two model sessions completed with provider-schema-conforming answers;
- both completed answers passed the stricter trusted Python validator;
- both completed answers were scored before allocation reveal;
- no failed outcome was retried or replaced.

For both completed sessions, the JSONL traces contain only local shell reads
within the assigned participant bundle. They contain no MCP call, web search,
package execution, certificate replay, compiler invocation, or file write.
The traces contain a client warning that skill descriptions were shortened,
but no skill or plugin tool was invoked.

The first launch used an unsupported `-a` command-line shorthand. The second
started the outer guard from the source repository, a path the guard itself
denies. These are orchestration failures rather than participant answers, but
the preregistered retention rule requires them to remain first-class outcomes.

This lock establishes recording provenance only. It does not support an arm
comparison, ClaimPack-effectiveness claim, mathematical correctness claim, or
independent validation claim.
