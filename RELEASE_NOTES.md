# Release notes

## v0.1.0-candidate.1 — 2026-08-01

First public candidate release of ClaimPack, a consumer-first protocol and
reference implementation for transferring exact, evidence-bounded scientific
claims between research agents.

The tag and skill version `0.1.0-candidate.1` maps to the PEP 440 Python
distribution version `0.1.0rc1`; UseReceipts report the Python spelling.

This release provides:

- separate standards-conformant `consume-claimpack` and `publish-claimpack`
  Agent Skills;
- a dependency-free Python validator, inspector, policy evaluator, UseReceipt
  generator, and suppression-monotone seen-ledger;
- immutable claim, evidence, relation, assessment, and receipt records;
- a bounded offline directory/ZIP reader that never extracts or executes
  package content;
- a static, content-addressed, forkable catalogue;
- reference-only candidate-mathematics seed packages;
- 113 unit and security regression tests and a 12-case adversarial gauntlet;
- ordinary and optimized-Python verification gates; and
- an optional AgentMail release-notice helper, separated from claim trust.

### Assurance boundary

ClaimPack structural validation establishes format conformance and exact local
integrity only. It does not establish scientific truth, proof completeness,
semantic correspondence, novelty, priority, independent reproduction, peer
review, or safe use under every policy. `ALLOW` is a disclosed consumer-policy
decision over exact inputs, not a global truth label.

The bundled evaluation runs are developmental harness evidence. The documented
commitment-masking defect prevents comparative efficacy claims from those runs.

### Rights

To the extent contributors hold the relevant rights, original repository
contents are dedicated to the public domain under CC0 1.0 Universal.
Referenced third-party research artifacts retain their own rights.
