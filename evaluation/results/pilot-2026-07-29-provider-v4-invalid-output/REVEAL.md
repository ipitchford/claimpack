# Provider-v4 allocation reveal and audit

The allocation seed and arm map were revealed only after commit
`80444421314f506cd0248b4052035d34e8684b76` locked all four RunReceipts and
all three applicable ScoreReceipts.

Post-reveal review found that the public, unkeyed bundle IDs already disclosed
the arms to anyone reconstructing both candidate bundles. The commit ordering
therefore establishes explicit-file reveal order, not enforced scorer masking.
See `evaluation/COMMITMENT_MASKING_ERRATUM.md`.

The revealed allocation was balanced:

| Trial | Arm | Termination | Descriptive metric results |
|---|---|---|---|
| `trial-0a290143b0c318ff` | ordinary plus ClaimPack | completed | 14 pass, 4 fail, 1 unknown |
| `trial-c9affe1fdb7b7eb1` | ordinary plus ClaimPack | invalid output | not scored |
| `trial-5fceea97ea462ccf` | ordinary release | completed | 12 pass, 6 fail, 1 unknown |
| `trial-743511f769fbdf09` | ordinary release | completed | 13 pass, 5 fail, 1 unknown |

The mechanical audit reports:

- `recording_complete: true`;
- `semantically_scorable: false`;
- `bundle_binding_verified: true`;
- `comparative_claim_allowed: false`;
- no missing RunReceipt or applicable ScoreReceipt.

All four supervisor traces show local bundle reads only. There was no observed
MCP call, web search, package execution, replay, compilation, or write. The
invalid answer repeated command strings in its self-report; its actual trace
did not repeat a prohibited action. These statements concern participant
command events. Client bootstrap stderr records attempted cache and skill-root
reads, and trace warnings say global skill descriptions remained visible;
bundle-only model context is therefore not claimed.

No arm comparison is warranted. One ClaimPack-arm outcome was invalid under
the trusted answer contract, leaving unequal scorable counts; the case set
contains one case whose gold decision is always `UNKNOWN`; the registered plan
disallows comparative claims; and there is no statistical power, independent
scoring, or replication. The per-dimension receipts are retained as
developmental harness evidence only and say nothing about the truth of the
underlying mathematical result.

Git history shows that the score-lock commit precedes this explicit reveal, and
the scorer is deterministic. Those facts do not repair the allocation leak in
the preregistered bundle commitment.
