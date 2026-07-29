# Provider schema preflight

Before sealing the corrected provider-v2 plan, a non-scientific transport
preflight was run in an empty temporary directory with no research materials
or gold answer.

- client: `codex-cli 0.144.1`
- model: `gpt-5.6-sol`
- reasoning effort: `low`
- session: ephemeral
- schema SHA-256:
  `f117c27eec609e7c81eac1356eb17a34b1b648108ce00880224d5e00e82b6aff`
- provider result: accepted; exit status 0

An earlier projection was rejected because enum and constant properties lacked
explicit `type` fields. The checked-in generator now removes the provider’s
unsupported length, item-count, uniqueness, and pattern keywords and adds
explicit string types to enum and constant nodes.

The preflight establishes only that the provider accepted the structured-output
schema and returned a schema-conforming object. It does not validate the
scientific task, the trusted Python validator, ClaimPack effectiveness, or any
research claim.
