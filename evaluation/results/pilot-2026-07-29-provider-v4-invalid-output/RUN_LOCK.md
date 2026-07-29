# Developmental provider-v4 run and score lock

This directory locks all four scheduled provider-v4 outcomes before the
allocation seed or arm map is copied into the repository.

The registered plan is
`ni:///sha-256;QPgGL_ZYHsQLAvhBOPfoqaSaxuAfimx_8yeAtXt0NzU`.
The opaque bundle commitment is
`ni:///sha-256;BpWGfETiCpLw_9oIzRKSjOSBmFMxnE5FIwY6fxvZ-1Y`.

Outcomes at the lock:

- all four client invocations reached a fresh model session and exited 0;
- all four answers satisfied the provider-compatible response schema,
  including its exact per-bundle trial-ID constant;
- three answers passed the stricter trusted Python validator and were scored;
- one answer duplicated two entries in `actions.commands`, failed the trusted
  uniqueness rule, and is retained as `invalid-output` with no semantic score;
- no outcome was retried or replaced.

All JSONL traces contain only local shell reads within the assigned participant
bundle. They contain no MCP call, web search, package execution, certificate
replay, compiler invocation, or file write. Each trace contains a client
warning that skill descriptions were shortened, but no skill or plugin tool
was invoked.

The provider projection deliberately omits `uniqueItems` because the provider
rejects that JSON Schema keyword. Provider conformance therefore remains a
transport check; the stricter trusted validator is the scoring gate.

This lock establishes recording provenance only. It does not support an arm
comparison, ClaimPack-effectiveness claim, mathematical correctness claim, or
independent validation claim.
