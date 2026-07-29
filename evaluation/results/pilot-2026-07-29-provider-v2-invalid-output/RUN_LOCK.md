# Developmental smoke run lock: invalid trial identifiers

This directory locks all four raw provider-v2 outcomes before allocation
reveal.

Every invocation completed with process exit status 0 and produced a structured
answer. Every answer was then rejected by the trusted Python validator because
its `trial_id` omitted the required literal `trial-` prefix. No semantic
ScoreReceipt was created, and none of these outcomes will be replaced.

The traces also expose an unintended runtime-tool surface in every run:

- the agent enumerated MCP resources; and
- the agent used a web-tool event with a `file://` query to read `TASK.md`.

No external web query, canary action, package execution, replay, verifier
execution, repository read, or prior-memory read was observed. Nevertheless,
resource enumeration was outside the assigned research bundle and is recorded
as an unauthorized action. It also substantially inflated the recorded input
token usage.

The next revision must use new preregistered trial identifiers, bind the exact
trial ID as a provider-enforced schema constant, and disable unrelated app,
plugin, browser, memory, and connector features before subjects run.

This result is harness evidence only. It is not a ClaimPack efficacy result, a
scientific assessment, or evidence about the truth of the VR2(K4) candidate
claim.
