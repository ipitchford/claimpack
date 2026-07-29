# ClaimPack

> **Status: local pre-release research-infrastructure prototype.**
> This repository does not certify that any scientific claim is true.

ClaimPack is a consumer-first protocol for transferring an exact scientific
claim, its evidence boundary, dependencies, qualifications, objections, and
version history between research agents.

The first question ClaimPack asks is not “was this published?” or “is this
verified?” It asks:

> Under this disclosed policy, using these exact immutable inputs, what was a
> particular consumer justified in doing with this claim?

The answer is one of:

- `ALLOW` — every policy-required condition had explicit acceptable evidence;
- `DENY` — at least one policy-required condition failed; or
- `UNKNOWN` — evidence, freshness, correspondence, or dependency closure was
  insufficient.

`ALLOW` is a policy decision, not a truth label.

## Current prototype

The v0.1 proof of concept contains:

- strict, dependency-free parsing and deterministic content identifiers;
- immutable ClaimVersion, Evidence, Relation, Assessment, and UseReceipt
  records;
- a bounded directory/ZIP reader that uses descriptor-relative,
  no-symlink-following directory reads and never extracts or executes package
  content;
- a three-state policy evaluator;
- a semantically monotone local seen-ledger preventing a previously observed
  adverse record from silently disappearing;
- a consumer skill;
- a 12-case, catalogue-aligned adversarial “badclaims” gauntlet; and
- real reference-only seed packages for candidate mathematics; and
- an offline randomized A/B experiment builder and arm-neutral scorer for
  developmental cold-agent studies.

Signing, remote catalogue search, replay execution, and a web interface are
deliberately outside the first safety boundary.

The checked-in static catalogue is content-addressed and forkable. The
`catalog-diff` command is an offline ClaimWatch primitive: it reports additions,
disappearances, and package-binding changes without interpreting disappearance
as retraction.

## Safety rule

All package text—including Markdown, TeX, source code, citations, replay
commands, and apparent instructions—is untrusted quoted data. Reading a
ClaimPack never authorizes:

- network access;
- subprocess execution;
- package extraction;
- importing package code;
- following links; or
- changing the consumer’s instructions.

Replay is a separate, explicit, sandboxed action that v0.1 does not implement.

## Commands

From the repository root:

```sh
python3 -m claimpack validate examples/z20
python3 -m claimpack inspect examples/z20
python3 -m claimpack decide examples/z20 \
  --policy policies/cautious-scientific-use-v0.1.json \
  --as-of 2026-07-29T13:00:00+00:00
python3 -m claimpack decide examples/z20 \
  --policy policies/cautious-scientific-use-v0.1.json \
  --as-of 2026-07-29T13:00:00+00:00 \
  --receipt /tmp/z20-use-receipt.json
python3 -m claimpack catalog-diff old-catalog.json new-catalog.json
python3 -m unittest discover -s tests -v
python3 gauntlet/run.py
make verify
```

The first three commands are read-only: without `--receipt`, `decide` prints
the complete ephemeral UseReceipt to standard output. With `--receipt`, it
writes only the explicitly named receipt and, when requested, the explicitly
named seen-ledger. Receipt creation refuses to overwrite an existing path.
Receipt and ledger paths must be distinct.

A named seen-ledger must already exist. Creating one is an explicit write:

```sh
python3 -m claimpack decide examples/z20 \
  --policy policies/cautious-scientific-use-v0.1.json \
  --seen-ledger /tmp/z20-seen.json \
  --update-ledger --init-ledger
```

The ledger is append-only in meaning: each atomically installed snapshot
retains every previously loaded adverse record. It is physically a
single-writer snapshot file, so preserve or version it like any other
load-bearing research input.

`inspect` includes the quoted source-package replay commands, evidence
limitations, semantic-alignment records, and assessment authentication and
independence fields. Inspection never executes a quoted command.

The cautious policy intentionally returns `UNKNOWN` for all three reference
seeds. Their assessments are repository-reported, their archives are referenced
rather than embedded, and no complete objection-search or consumer
authentication context is supplied. This is the expected safe result.

Package text cannot authenticate itself. To accept an assessment under a policy
that requires authentication, the consumer must supply its exact record ID and
a nonempty description of the external verification context. That external
record-ID set is authoritative for the local decision even if the package says
`unverified`; conversely, a package’s `claimed-verified` field grants no trust.

UseReceipts distinguish the historical `policy_as_of` cutoff from the actual
evaluation and retrieval times. Direct local use leaves `catalogue_head`
empty; it is populated only when the caller actually used that exact catalogue
snapshot.

## Reference seeds

The generated, reference-only packs bind exact public candidate releases:

| Pack | Exact principal claim | Version archive |
|---|---|---|
| `examples/z20` | \(z(20)=6\) | Zenodo `21647645`, archive SHA-256 pinned |
| `examples/vr2-k4` | \(\mathrm{VR}_2(K_4)=20\) | Zenodo `21647654`, archive SHA-256 pinned |
| `examples/erdos848` | \(f(N)=\lfloor(N+18)/25\rfloor\) for all positive \(N\) | Zenodo `21647629`, archive SHA-256 pinned |

The z(20) and VR2 packs reuse one byte-identical ClaimVersion for the exact
two-fixed-core UNSAT subclaim. The Erdős 848 pack separately records its
load-bearing imported high-threshold theorem. This prevents a whole-paper
dependency from hiding the smaller statement actually reused.

Run `python3 -m tools.check_generated` to regenerate all seeds, the cautious
policy, and `catalog/catalog.json` in a temporary directory and compare every
byte.

## Record direction

Content-addressed records form an append-only graph:

```text
earlier ClaimVersion
        ↑
new dependent ClaimVersion
        ↑
Relation / Evidence
        ↑
Assessment
        ↑
UseReceipt
```

An arrow means “the later record may name the already-existing earlier
record.” Reverse indexes belong in the derived catalogue. A ClaimVersion never
lists evidence, relations, or assessments that can only be created after it;
this avoids circular hashes and permits later objections without rewriting the
claim.

## Interfaces

- `SPEC.md` — normative protocol and decision semantics;
- `schemas/` — machine-readable manifest preflight and vocabulary;
- `SKILL.md` — safe consumer-agent procedure;
- `PUBLISH_SKILL.md` — producer-agent packaging procedure;
- `catalog/catalog.json` — immutable static discovery snapshot;
- `badclaims/` and `gauntlet/` — adversarial behavior contract; and
- `DESIGN_INPUTS.md` — provenance and unverified-input boundary.

## Non-goals

ClaimPack v0.1 does not:

- determine scientific truth;
- establish novelty or priority;
- convert local replay into independent reproduction;
- infer semantic equivalence from matching text or hashes;
- aggregate evidence into a credibility score;
- operate an authoritative registry;
- coordinate or schedule research-agent swarms; or
- replace journals, proof assistants, archives, or expert review.

It is a transfer layer beneath those systems.

## Next evaluation sequence

The deterministic core and current adversarial gauntlet pass locally. The
developmental evaluation harness prepares byte-matched ordinary-release and
ordinary-plus-ClaimPack bundles for randomized fresh-subject comparisons with
hypothesis masking and scorer masking. Participants can see which representation
they received, so this is not a fully blinded design.

The first smoke schedule is intended to validate allocation, bundle parity,
output capture, separate-dimension scoring, and receipt sealing. It is not an
efficacy study, a scientific-truth assessment, or evidence that ClaimPack
improves agent behavior. Prompt-level prohibitions on network and out-of-bundle
access are auditable study instructions, not an operating-system-enforced
network-isolation guarantee. Comparative claims require the broader controls,
replication, isolation, and independent scoring described in
`evaluation/README.md` and `EVALUATION.md`.

## Rights

To the extent its contributors hold the relevant rights, the original
contents of this prototype are dedicated to the public domain under
CC0 1.0 Universal. Referenced research artifacts and third-party material
retain their own rights and are not relicensed here. See `PUBLIC_DOMAIN.md`
and `LICENSE`.
