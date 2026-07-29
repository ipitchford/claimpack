# Erratum: unkeyed bundle commitments reveal the arm

## Finding

The provider-v3 and provider-v4 preregistrations call their bundle commitments
opaque. They are not arm-hiding commitments.

Each published `bundle_id` is an unkeyed content-derived identifier. Given the
public plan, case, source tree, and bundle commitment, a repository-aware
consumer can materialize both candidate arms for each trial and compare their
bundle IDs with the published ID. A read-only post-reveal review performed
that reconstruction for provider-v3 and provider-v4 and recovered both
complete allocations without using either seed or allocation-reveal file.

## Consequence

The Git history still proves that raw outputs and applicable scores were
committed before the seed and explicit allocation file entered the repository.
The reference scorer is deterministic and receives no explicit condition
field, although answer content can itself reveal representation-specific
evidence.

Those facts do **not** establish scorer masking. The public commitment itself
leaked the arm to anyone willing to reconstruct the candidate bundles, and
private operator knowledge is not externally auditable. No current
developmental result may be described as blinded, cryptographically masked, or
evidence that scorer masking worked.

This does not alter the already-failing efficacy gate: every recorded smoke
audit already has `comparative_claim_allowed: false`.

## Required correction for future experiments

A future experiment must separate bundle binding from arm disclosure. One
acceptable design is:

1. generate a fresh high-entropy per-trial salt or HMAC key;
2. preregister only a hiding commitment to the bundle descriptor;
3. give the condition-field-free scorer answers without raw bundle IDs or
   salts;
4. lock raw answers and scores;
5. reveal the allocation, bundle descriptors, and salts or verification key;
6. verify every hiding commitment and RunReceipt binding after reveal.

The commitment scheme, salt/key handling, receipt fields, and reveal verifier
must be specified and tested before another comparative schedule. Merely
withholding the randomization seed is insufficient.
