---
name: publish-claimpack
description: Package an exact scientific claim for safe discovery and qualified downstream use by autonomous research agents.
version: 0.1.0-dev
---

# Publish a ClaimPack

## Objective

Make one exact claim discoverable, inspectable, and safely reusable without
representing publication, hashing, replay, model agreement, or structural
validity as scientific truth.

## Producer workflow

1. **Choose the unit of record**

   Package the smallest statement likely to be cited or imported. Split a
   paper into exact subclaims when different evidence or dependencies support
   them.

2. **Write exact statement and scope**

   Include natural language, LaTeX, definitions, quantifiers, conditions,
   exclusions, non-implications, claim kind, and structured scope. Record
   canonical problem IDs and aliases separately. Put only mathematical content
   in these identity-bearing fields: candidate, verification, replay, review,
   and reproduction status belong in source metadata, Evidence, or Assessment
   records. Use a non-implication here only when it delimits the proposition
   itself.

3. **Pin the source version**

   Prefer an exact commit, release tag, version DOI, archive digest, arXiv
   version, or SWHID. A concept DOI or mutable branch is a discovery locator,
   not an immutable version.

4. **Declare earlier dependency targets**

   A ClaimVersion may identify exact earlier ClaimVersion records on which it
   depends. Do not place future Relation, Evidence, or Assessment IDs inside
   the claim. Add those as later overlays.

5. **Bind evidence honestly**

   State what each artifact covers and does not cover. Distinguish manuscript,
   formal object, certificate, source, output, and replay receipt. Replay
   commands are display-only metadata; package consumption never executes
   them.

6. **Separate status dimensions**

   Emit dated Assessment records for statement precision, canonical
   correspondence, proof completeness, formal/certificate checking,
   reproducibility, independence, dependency closure, objections, provenance,
   novelty, version stability, and semantic scope. Keep author, registry,
   system, reproduction, and human-review issuers separate.

7. **Preserve adverse events**

   Add objections, responses, corrections, retractions, and withdrawals as
   append-only records. A response does not erase an objection. Only a
   consumer-authenticated, same-issuer, later withdrawal changes its derived
   state. A changed statement with explicit lineage does not itself discharge
   an objection, and qualifications on a withdrawal remain load-bearing.

8. **Apply the rights boundary**

   License or dedicate only material for which the relevant rights are held.
   Name third-party exclusions explicitly. Never infer a source’s reuse rights
   from public availability.

9. **Validate and attack the pack**

   Run the trusted local validator, deterministic tests, resource-limit cases,
   prompt-injection case, stale-evidence case, semantic-bridge case,
   qualification relay, and suppression-ledger cases. A hash mismatch is a
   rejection; missing scientific evidence is `UNKNOWN`.

10. **Publish immutable bytes and a static catalogue entry**

    Deposit the exact archive where practical, record its digest and version
    DOI, and add the exact ClaimVersion and package root to a forkable static
    catalogue. A catalogue reports existence and version, not correctness.

11. **Hand off with a UseReceipt**

    Downstream consumers record their own policy, external authentication and
    objection-search contexts, exact inputs, qualifications, decision, limits,
    and parent run. Do not copy an upstream `ALLOW` as a truth label.

## Release language

Use status language that matches the strongest actual evidence, such as:

> Unrefereed candidate result with a local deterministic replay. No independent
> external reproduction, complete human verification, peer review, or
> end-to-end formalization is claimed.

Change that sentence only when a new exact Assessment record supports the
change.
