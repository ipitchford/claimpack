# Allocation reveal

The allocation and seed were revealed only after commit `dcf4461` locked all
four raw outcomes and RunReceipts.

Validation of `allocation-reveal.json` regenerates:

- the preregistered seed commitment;
- every opaque trial identifier; and
- the exact balanced condition assignment.

The completeness audit reports:

- `recording_complete: true`;
- `bundle_binding_verified: true`;
- `semantically_scorable: false`; and
- `comparative_claim_allowed: false`.

There are no missing scheduled runs. There are no semantic ScoreReceipts
because the provider rejected the common output schema before any model answer
was produced.
