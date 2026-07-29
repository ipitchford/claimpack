# Security boundary

Core ClaimPack consumption is intentionally offline and non-executing. Treat
every package as hostile data.

Security reports should identify the smallest input that causes:

- network, subprocess, import, rendering, extraction, or filesystem side
  effects;
- traversal, symlink, device, archive, parser, or resource-limit bypass;
- forged or self-asserted authentication becoming trusted;
- a missing or disputed input improving a decision;
- a false `ALLOW`, downgraded explicit `DENY`, or qualifier loss; or
- a UseReceipt that can be confused across claim, package, policy, time, or
  authentication context.

High-value regression classes include changed-claim lineage washing,
future-dated support, objections to positive Assessments or withdrawals,
positive-budget exhaustion hiding adverse state, ledger disappearance or path
aliasing, malformed archive/parser crashes, and directory check/use races.

Do not include real secrets or weaponized payloads. A text marker and temporary
path are sufficient to demonstrate unintended execution.

This local prototype has no private security mailbox. Before public release, a
maintainer must add one and define supported versions. Until then, keep
unpublished high-impact details local to the repository owner.
