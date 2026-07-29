# Provider-v3 tool-surface preflight

Before sealing the provider-v3 plan, two non-scientific transport preflights
were run in temporary directories containing only a `TASK.md` instruction to
return `LOCAL_ONLY_OK`. No research materials, case metadata, allocation, or
gold answer were present.

The first attempt used both an outer macOS `sandbox-exec` profile and the
client's `read-only` sandbox. The nested sandbox could not initialize
(`sandbox_apply: Operation not permitted`), so the agent could not read its
task. This attempt is retained as an execution-design failure.

The corrected preflight used the same outer profile and the client's
`danger-full-access` setting solely to avoid applying a second nested sandbox.
The outer profile remained the effective operating-system guard. The session
was ephemeral, user configuration and repository rules were ignored, and these
features were explicitly disabled:

- apps and plugins;
- remote plugins and plugin sharing;
- browser and external-browser tools;
- in-app browser and computer use;
- tool suggestion;
- workspace dependencies;
- memories and Chronicle;
- image generation;
- skill dependency installation.

Observed corrected-preflight events were exactly:

1. one local command execution, `pwd && sed -n '1,240p' TASK.md`;
2. the final response `LOCAL_ONLY_OK`.

No MCP enumeration, web search, or other tool call appeared in the JSONL trace.
The client exited with status 0.

- date: 2026-07-29
- client: `codex-cli 0.144.1`
- model: `gpt-5.6-sol`
- reasoning effort: `low`
- session: ephemeral

This establishes only the observed tool surface for the corrected empty-task
preflight. It does not prove exclusive filesystem visibility, network
isolation, the behavior of later scientific trials, ClaimPack effectiveness,
or the truth of any research claim.
