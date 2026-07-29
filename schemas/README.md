# Machine-readable interface

`manifest-v0.1.schema.json` and `policy-v0.1.schema.json` are JSON Schema
preflights. `vocabulary-v0.1.json` is the stable enum and identity registry
used by agents that need to negotiate the protocol without importing Python.

The strict, normative behavioral validator is `claimpack/records.py` together
with `claimpack/validate.py`. JSON Schema alone cannot verify content-derived
IDs, manifest hashes, cross-record types, append-only objection semantics,
consumer authentication, evidence correspondence, or three-state policy
behavior.

This split is deliberate: schema-valid means “shaped like a ClaimPack,” not
“safe to use” and certainly not “scientifically true.”
