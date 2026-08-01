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

## Supported versions

The latest tagged candidate release receives security fixes. Earlier
developmental snapshots are unsupported.

## Reporting

Use GitHub private vulnerability reporting for sensitive reports. If that is
unavailable, open a GitHub issue containing no exploit, credential, private
data, or weaponized payload and ask the maintainer to establish a private
channel. Public issues are appropriate for non-sensitive hardening proposals.

If a release has an external disclosure channel, use it only for public-facing
summaries and only through environment-provided credentials. Never place keys
in tracked files, command examples, receipts, or package artifacts.
