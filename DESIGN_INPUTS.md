# Design inputs and provenance

This prototype synthesizes a July 2026 discussion among Ian Pitchford and
multiple AI systems about agent-to-agent scientific knowledge transfer.

## Primary local input

`AI_Researchers.md`, supplied by Ian Pitchford, records a conversation with
Grok about the scale of human and future AI research and multi-agent
coordination.

- Source basename: `AI_Researchers.md` (held outside this repository)
- SHA-256:
  `1e9fae2fc17bb5f04302fe42b519e13517085c98a542bcd93e24b45f685c88eb`
- Read on: 29 July 2026
- Bundled here: no
- Rights: not inferred or altered

The document’s stable design contribution is conditional:

> If autonomous research output grows much faster than independent scrutiny,
> exact claim identity, evidence boundaries, bounded verification, and
> reliable handoffs become critical infrastructure.

Its specific researcher totals, national counts, deployment forecasts, cost
ratios, coordination-failure percentages, amplification factors, and optimal
team sizes are not treated as verified ClaimPack premises because the supplied
document does not embed sufficient source bindings for them.

## Design-review inputs

The prototype also incorporates:

- the consumer-first inversion and adversarial-gauntlet proposal from an
  Anthropic Fable review supplied in the working conversation;
- the separation of claim, evidence, assessment, activity, and use receipt;
- optional rather than mandatory in-toto/Sigstore authentication;
- strict separation of exact identity from semantic equivalence;
- append-only objection handling;
- definitional-alignment and correspondence assessments;
- suppression-monotonic three-state policy evaluation; and
- the assurance vocabulary already used by the candidate-mathematics
  repositories selected as seed material.

These are design decisions, not evidence that the protocol succeeds. Success
must be measured by adversarial and cold-agent trials.
