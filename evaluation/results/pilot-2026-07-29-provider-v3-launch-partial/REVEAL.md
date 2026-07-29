# Provider-v3 allocation reveal and audit

The allocation seed and arm map were revealed only after commit
`557f7474c06915f56a2898140fca6b0782b4d722` locked all four RunReceipts and
both applicable ScoreReceipts.

Post-reveal review found that the public, unkeyed bundle IDs already disclosed
the arms to anyone reconstructing both candidate bundles. The commit ordering
therefore establishes explicit-file reveal order, not enforced scorer masking.
See `evaluation/COMMITMENT_MASKING_ERRATUM.md`.

The revealed allocation was balanced:

| Trial | Arm | Termination |
|---|---|---|
| `trial-04d2735488a6c3c7` | ordinary plus ClaimPack | error before model session |
| `trial-f6e33577480b3d5f` | ordinary release | error before model session |
| `trial-6935f9db9ccad2da` | ordinary plus ClaimPack | completed and scored |
| `trial-879218e7901dc480` | ordinary release | completed and scored |

The mechanical audit reports:

- `recording_complete: true`;
- `semantically_scorable: false`;
- `bundle_binding_verified: true`;
- `comparative_claim_allowed: false`;
- no missing RunReceipt or applicable ScoreReceipt.

The completed ClaimPack-arm response passed 16 dimensions, failed 2, and
received 1 `unknown`. The completed ordinary-arm response passed 12
dimensions, failed 6, and received 1 `unknown`. These are unaggregated
descriptive counts for one completed response per arm, not an effect estimate.
The full per-dimension judgments remain in the ScoreReceipts.

No comparison is warranted: half the scheduled trials failed at orchestration,
the case set contains one case whose gold decision is always `UNKNOWN`, the
plan disallows comparative claims, and there is no statistical power or
independent replication. The pilot says nothing about the truth of the
underlying mathematical result.
