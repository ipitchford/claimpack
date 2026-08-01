# ClaimPack charter

## Purpose

ClaimPack exists to make scientific claims findable and safely reusable by
autonomous research agents without making human expert review a publication
gate and without replacing it as valuable evidence.

The protocol preserves distinctions that ordinary publication metadata often
collapses:

- statement versus proof;
- proof text versus formal declaration;
- formal declaration versus kernel-checked proof;
- certificate verification versus correctness of the encoded problem;
- local replay versus independent reproduction;
- correctness versus novelty;
- author status versus external assessment; and
- absence of a discovered objection versus evidence that no objection exists.

## Design principles

1. **Consumer-first.** The protocol earns its keep when a cold agent behaves
   more safely because a ClaimPack exists.
2. **Exact before semantic.** Hashes establish exact syntactic identity.
   Equivalence, strengthening, correspondence, and scope alignment are
   separately attributable scientific assessments.
3. **No truth authority.** Catalogues discover records; policies decide local
   eligibility; neither owns truth.
4. **Append-only disagreement.** Objections, responses, corrections,
   retractions, and withdrawals remain inspectable events.
5. **Suppression-monotonic consumption.** Missing or removed information must
   not improve a decision.
6. **Qualifications propagate.** A downstream handoff must retain conditions,
   unknowns, trust boundaries, and unresolved objections.
7. **Inert by default.** Research packages are data, not instructions.
8. **Bounded operation.** Cycles, oversized inputs, missing sources, and
   exhausted budgets terminate as `UNKNOWN`.
9. **Forkable infrastructure.** Packages and catalogues remain usable without
   a central service.
10. **No opaque score.** Evidence dimensions and issuer lineage remain
    inspectable rather than being compressed into one credibility number.

## Initial success criterion

In controlled trials, fresh agents given ClaimPacks should outperform agents
given ordinary repositories alone at:

- quoting the exact claim;
- pinning the correct version;
- distinguishing statement-only formalisation from proof;
- identifying load-bearing assumptions and semantic bridges;
- detecting objections, retractions, and stale mirrors;
- resisting package-borne prompt injection;
- avoiding unauthorized execution; and
- preserving qualifications in downstream use.

## Governance boundary

This public candidate prototype has no claim to standards authority. A future
specification should have versioned governance, security, contribution,
deprecation, catalogue-admission, privacy, and succession policies. Cheap
forking reduces institutional capture but does not eliminate governance.
