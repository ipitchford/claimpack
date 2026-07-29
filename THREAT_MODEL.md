# Threat model

## Protected properties

ClaimPack aims to preserve:

- exact statement and version identity;
- source and artifact integrity;
- scope, conditions, exclusions, and non-implications;
- evidence coverage and limitations;
- dependency and semantic-correspondence boundaries;
- adverse events and unresolved objections;
- issuer and coordination lineage;
- consumer policy, checks, unknowns, and termination reason; and
- qualification fidelity across downstream handoffs.

## Trust boundaries

The core parser trusts only its own implementation and the caller-selected
policy and local inputs. Package authors control all package content.

A digest proves byte identity. A signature, when later supported, proves only
that a signing identity authenticated particular bytes. Neither establishes
scientific meaning or truth.

## Threats and required responses

| Threat | Required response |
|---|---|
| Prompt injection in prose, code, citations, or metadata | Treat all fields as inert data; no network, execution, imports, or instruction changes |
| Path traversal, symlink, device entry, or archive bomb | Reject before reading content; never extract |
| Duplicate JSON keys or ambiguous serialization | Reject |
| Stale mirror or suppressed objection | Freshness and route receipts; retained adverse seen-ledger; no improved decision |
| Version washing with the same statement and new record metadata | Carry adverse assessments by stable `claim_id`, not only by the old record ID |
| Lineage washing through a changed statement fingerprint | Traverse bounded explicit lineage and retain predecessor adverse state until explicitly resolved |
| Adverse event targets a positive Assessment, Evidence, Relation, or withdrawal | Traverse the causal support overlay; a challenge does not erase the event it challenges |
| Future-dated support or caller-selected future cutoff | Enforce causal ordering and separate historical cutoff from actual process times |
| Retraction race | Exact actual retrieval time and an actual catalogue head, if used; later event monitoring is a separate extension |
| Package self-asserts a valid signature or trusted issuer ID | Treat authentication fields as claims; require a consumer-supplied authenticated record-ID set and context |
| False-green verifier or status-zero failure | Bind evidence to exact subject and expected semantic output; process status alone is insufficient |
| Certificate verifies the wrong formula | Require an explicit correspondence relation and assessment |
| Supporting Evidence is objected to or retracted | Traverse exact Evidence-targeted adverse assessments and retain them as decision inputs |
| External evidence locator is present but bytes were not consumed | Permit discovery, but do not satisfy an embedded-evidence policy |
| Statement-only formalisation presented as proof | Separate formal role, proof status, axiom footprint, and semantic correspondence |
| Undeclared axiom or external hypothesis | `DENY` or `UNKNOWN` under policy; never silently discharge |
| Qualifier laundering through summaries | Compare claim, scope, dependency, objection, and assurance fields at every handoff |
| Correlated attestation ring | Record actor, model/provider, code, data, environment, parent run, and communication exposure; never count names as independence |
| Novelty flooding and vague near-duplicates | Keep existence separate from maturity and scope match; use bounded retrieval and attributed novelty-search assessments |
| Dependency cycle or graph bomb | Enforce depth, node, event, and time budgets; terminate `UNKNOWN` |
| Positive-evidence budget hides an explicit retraction | Scan supplied applicable adverse records first; preserve `DENY` across positive-budget exhaustion |
| Concurrent directory member swap | Descriptor-relative `O_NOFOLLOW` opens and post-open regular-file checks |
| Receipt path aliases the seen-ledger | Reject resolved-path equality before any write; install ledger snapshot and new receipt atomically |
| Coordinator compromise or context saturation | Immutable handoff receipts and bounded local verification; do not treat orchestration history as correctness |
| Mutable URL or concept DOI drift | Pin exact version DOI, commit/SWHID, archive hash, and retrieval time |
| Package disappearance | Preserve immutable archives where rights permit; distinguish archive availability from correctness |
| Catalogue entry disappears | Emit a disappearance event; never infer withdrawal or retraction and never improve the decision |
| Interface reintroduces a green tick | Display policy, issuer, date, freshness, qualifications, and unknowns adjacent to every status |

## Non-threats the protocol does not solve

ClaimPack cannot guarantee:

- complete discovery of all prior art or objections;
- honest issuers;
- semantic correctness of an assessment;
- independent reproduction merely because actors have different names;
- permanent availability of every external service;
- absence of defects in the consumer itself; or
- eventual community adoption.

The gauntlet tests bounded consumer behavior, not universal epistemic safety.
