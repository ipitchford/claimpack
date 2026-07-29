# Allocation reveal

The provider-v2 allocation and seed were revealed only after commit `fa5fbc3`
locked all four raw answers, traces, and RunReceipts.

The revealed seed regenerates the preregistered commitment, opaque trial
identifiers, and exact balanced assignment. The audit reports:

- `recording_complete: true`;
- `bundle_binding_verified: true`;
- `semantically_scorable: false`; and
- `comparative_claim_allowed: false`.

All four answers remain invalid outputs. No semantic scores or arm comparison
are reported.
