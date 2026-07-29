# ClaimPack protocol v0.1 — prototype specification

## 1. Assurance statement

Structural validity means only that a package conforms to this protocol and
its integrity checks pass. It does not mean that the contained scientific
claim is correct, novel, complete, reproduced, peer reviewed, or safe to use
under every policy.

## 2. Immutable record types

The core profile defines five records:

1. `claim-version` — an exact statement and scope at one released version;
2. `evidence` — an artifact or observation bearing on a record;
3. `relation` — an attributed link between exact record versions;
4. `assessment` — a dated issuer’s judgment on one dimension; and
5. `use-receipt` — a consumer’s disclosed policy decision and handoff record.

Later assessments never mutate the original claim record. Overlay packages may
add objections, responses, reproduction reports, corrections, or retractions.

Records are append-only edges: a newly created record may target an existing
record, but an existing record never lists records that can only be created
later. In particular, ClaimVersion does not contain evidence, assessment, or
relation record IDs. Consumers discover those overlays by their exact
`subject`, `target`, or `source` fields.

## 3. Identity

### 3.1 Claim identity

`claim_id` is the SHA-256 `ni` URI of a restricted-canonical-JSON projection:

```text
{
  "protocol_version": ...,
  "record_type": "claim-version",
  "statement": ...,
  "scope": ...
}
```

The projection contains the exact natural-language statement, mathematical
notation, definitions, quantifiers, conditions, exclusions, non-implications,
and structured scope.

Statement and scope are the proposition's identity-bearing mathematical
content. Producer status and assurance language—such as candidate,
verification, replay, review, or reproduction status—MUST instead be carried
by source-version metadata, Evidence, or Assessment records. Otherwise an
unchanged proposition would acquire a different `claim_id` merely because its
assurance state changed. A non-implication belongs in scope only when it
delimits the proposition itself, not when it reports the state of its proof.

### 3.2 Record identity

`record_id` is the SHA-256 `ni` URI of the entire record except its own
`record_id` field. A provenance correction or new evidence binding can
therefore create a new record while retaining the same `claim_id`.

### 3.3 Package identity

`package_root` is the SHA-256 `ni` URI of `claimpack.json` with the
`package_root` field omitted. The manifest binds every embedded record and
artifact by SHA-256.

### 3.4 What identity does not mean

Hashes certify exact bytes under the declared canonical profile. They do not
certify paraphrase equivalence, mathematical equivalence, problem
correspondence, or relative strength. Those are attributed relation or
assessment records.

## 4. Restricted canonical JSON profile

Identity-bearing records use UTF-8 JSON with:

- ASCII object keys;
- no duplicate keys;
- no floating-point or integer JSON values;
- no lone Unicode surrogates;
- no Unicode normalization;
- only objects, arrays, strings, booleans, and `null`;
- lexically sorted object keys and compact separators; and
- preserved array order.

Quantities, sizes, dates, and versions are strings. This deliberately
restricted profile makes deterministic standard-library serialization
possible without claiming that unrestricted `json.dumps` implements all of
RFC 8785.

Whitespace inside strings is significant. Thus `\ge` and `\geq`, NFC and
decomposed Unicode, and differently spaced statements have different
identities. Retrieval systems may create a separately versioned
`search_fingerprint`; it is never a content identifier.

## 5. Assessments and objections

An assessment records:

- exact target;
- issuer and package-declared authentication state;
- issue date and optional validity limit;
- dimension and method;
- `stance`: `supports`, `challenges`, `neutral`, or `withdraws-prior`;
- `outcome`: `pass`, `fail`, `unknown`, or `not-applicable`;
- qualifications and evidence references;
- response, supersession, or withdrawal links; and
- a structured independence profile.

Objection state is derived from append-only events:

- a response does not automatically resolve an objection;
- only a consumer-authenticated same-issuer withdrawal can withdraw it;
- a third party may assess an objection as answered, sustained, or
  inconclusive but cannot erase it; and
- a mathematical counterexample or refutation may also be its own
  `claim-version`, connected by a relation.

`authentication.status` is only the producer's statement
(`claimed-verified` or `unverified`). It is never sufficient on its own.
Policies that require authentication receive an explicit set of assessment
record IDs verified by the consumer's external trust process; a UseReceipt
records that set and its verification context. This consumer-supplied set is
authoritative for that decision: an externally authenticated record remains
eligible when the package says `unverified`, while `claimed-verified` grants
no trust without external authentication.

An assessment of a ClaimVersion also carries the stable `target_claim_id`.
Adverse assessments therefore survive a provenance-only or packaging-only
record revision with the same exact statement and scope. A new record version
cannot become more usable merely by omitting an objection to its predecessor.
They also follow bounded, explicit `lineage` links across a changed
`claim_id`. A revision, correction, narrowing, strengthening, or supersession
does not silently discharge predecessor objections merely because the
statement fingerprint changed.

Objections, corrections, or retractions targeting a positive Assessment, its
supporting Evidence, or a withdrawal are also decision inputs. An
objection-to-objection does not erase the first objection. Every causally
effective withdrawal contributes its qualifications to the UseReceipt.

## 6. Relations and semantic alignment

Relations target exact record versions. Load-bearing dependency and
correspondence edges include:

- alignment status: `checked`, `partial`, `unchecked`, or `contested`;
- an inline definition map;
- explicit limitations.

A ClaimVersion lists the exact earlier ClaimVersion records on which it
declares a dependency in `dependency_targets`. A corresponding `depends-on`
Relation, created after the source claim, supplies the attributed semantic
alignment. Missing targets or missing relation overlays produce `UNKNOWN`;
they are not interpreted as evidence of closure. Assessments of a Relation
target that Relation as later overlay records.

The same structure covers:

- natural statement ↔ formal declaration;
- theorem ↔ SAT/SMT encoding;
- scientific claim ↔ estimand;
- historical problem ↔ modern formulation; and
- downstream claim ↔ imported theorem.

## 7. Policy decisions

A policy evaluates named evidence dimensions independently:

- a required `fail` yields `DENY`;
- all required dimensions must have acceptable positive evidence for `ALLOW`;
- otherwise the result is `UNKNOWN`.

Missing evidence, stale evidence, failed retrieval, incomplete dependency
closure, unverified semantic alignment, and budget exhaustion never count as
positive evidence.

Structural traversal can show that every declared dependency edge is present,
but author-declared emptiness does not prove the declaration complete.
`dependency-closure` therefore needs both a successful structural traversal
and a fresh, policy-accepted, evidence-backed Assessment when the policy
requires positive evidence.

Policies are declarative JSON using a fixed vocabulary. They contain no code,
expressions, templates, or evaluation language.

When `require_evidence_for_positive` is enabled, a positive assessment is
usable only if every cited Evidence record is present, targets the same exact
record, and passes package integrity validation. Evidence limitations are
copied into the resulting UseReceipt.

`require_embedded_evidence_for_positive` additionally prevents a reference-only
record from satisfying a use policy: at least one artifact in each supporting
Evidence record must be embedded and hash-bound to the package. External
locators remain useful for discovery but are unavailable evidence in offline
core evaluation.

Positive support is causal: a ClaimVersion, supporting Evidence, load-bearing
Relation, and Assessment must not postdate the policy cutoff; Evidence must
not postdate its Assessment; and later overlay records must not predate their
targets. The cutoff itself cannot be in the future relative to actual
evaluation. Violations fail closed rather than producing `ALLOW`.

Assessment budgets suppress positive conclusions, not adverse precedence.
An already supplied applicable retraction or accepted failure remains `DENY`
even when the positive-assessment budget is exhausted.

## 8. Suppression monotonicity

A conformant consumer must not improve `DENY` or `UNKNOWN` to `ALLOW` merely
because a record, retrieval route, field, or failed lookup disappeared.

Because no stateless consumer can know every objection in an open network,
v0.1 supports a semantically monotone local seen-ledger. Previously observed
adverse records remain policy inputs unless a valid later event changes their
derived state. A named missing ledger is an error; initialization is explicit.
Each update atomically installs a whole-file snapshot guarded by the prior
digest. This is not a multi-writer event database, so the file itself remains
a load-bearing input that must be preserved and backed up.

The protocol cannot prove universal objection absence. Coverage, freshness,
retrieval routes, and unavailable sources remain explicit.

## 9. Safe consumption

Core consumer commands:

- perform no network requests;
- invoke no subprocesses;
- import no package code;
- render no package HTML;
- follow no package links;
- extract no archive; and
- execute no replay command.

Directory and ZIP readers enforce path, type, file-count, size, compression,
and JSON-depth limits. Directory members are opened component-by-component
relative to a pinned directory descriptor with `O_NOFOLLOW`; the opened
descriptor is type-checked before reading. A ZIP is read selectively without
`extractall`, and malformed or unsupported member failures are normalized to
typed validation errors.

Replay metadata is quoted evidence. Replay requires a separate explicit
sandboxed workflow not defined by core v0.1.

## 10. Use receipts

A UseReceipt pins:

- exact package, claim, policy, records, and catalogue/retrieval snapshot;
- the historical `policy_as_of` cutoff separately from actual `evaluated_at`
  and `retrieved_at` process times;
- consuming tool/run and parent handoff;
- per-dimension results;
- decision and termination reason;
- qualifications and unresolved unknowns;
- unavailable sources and ignored records; and
- executed commands.

In core safe mode, `executed_commands` must be empty.

For direct local retrieval, `catalogue_head` is empty. A nonempty value may be
recorded only when the consumer actually used that exact catalogue snapshot;
the package root is never relabelled as a catalogue head.

Each `inputs[].sha256` value uses the `sha256:<lowercase-hex>` form. For an
embedded record it is the digest of the exact record-file bytes named by the
package manifest. For a record supplied from an external seen ledger it is the
digest of that record's RFC 8785 canonical JSON bytes. This distinction is
normative because a pretty-printed embedded file need not have the same byte
digest as its canonical JSON form.

Structural validation of a UseReceipt checks internal decision coherence
(`ALLOW` has only passing dimensions, `DENY` includes a failure, referenced
assessments are pinned inputs). It does not independently recompute the
decision. Reverification requires the pinned source package, policy, external
authentication context, objection-search context, and the core evaluator.

## 11. Extension boundary

Optional future profiles may add:

- RO-Crate and W3C PROV projections;
- in-toto/DSSE or Sigstore authentication envelopes;
- static catalogue discovery;
- ClaimWatch status-event monitoring;
- proof-assistant and certificate adapters;
- empirical-science profiles;
- restricted-data handling; and
- sandboxed replay.

These extensions may authenticate or add evidence. They may not redefine
structural validity as scientific truth.
