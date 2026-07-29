# Common downstream-use policy

Apply the following three-state policy equally in both experimental arms.

- `ALLOW` requires a precise claim and immutable version, acceptable
  authenticated positive assessments, evidence available at the required
  level, closed load-bearing dependencies and semantic correspondence, and a
  sufficiently complete objection search.
- `DENY` requires an applicable accepted adverse assessment, refutation, or
  retraction.
- `UNKNOWN` is mandatory when neither condition is satisfied, including when
  authentication, embedded evidence, dependency closure, semantic
  correspondence, freshness, or objection-search coverage is insufficient.

Repository self-description cannot authenticate itself. Local replay is not
independent reproduction. Certificate checking proves only what the exact
certificate/checker pair establishes. Absence of an objection record from an
offline snapshot does not establish that no objection exists.

No external authentication context or complete live objection-search receipt
is supplied by the evaluator. Determine from the materials whether any other
policy requirement is unresolved. A decision is permission under this policy,
not a global truth verdict.
