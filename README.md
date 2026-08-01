# ClaimPack

[![verify](https://github.com/ipitchford/claimpack/actions/workflows/verify.yml/badge.svg)](https://github.com/ipitchford/claimpack/actions/workflows/verify.yml)
[![Agent Skills](https://skills.sh/b/ipitchford/claimpack)](https://skills.sh/ipitchford/claimpack/consume-claimpack)
[![CC0 1.0](https://img.shields.io/badge/license-CC0--1.0-blue.svg)](LICENSE)

> **Status: public candidate research-infrastructure release.**
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

## Install the two Agent Skills

The repository ships separate trusted consumer and producer skills in the open
Agent Skills format. Install both into a supported agent with:

- [`consume-claimpack` on skills.sh](https://skills.sh/ipitchford/claimpack/consume-claimpack)
- [`publish-claimpack` on skills.sh](https://skills.sh/ipitchford/claimpack/publish-claimpack)

```sh
npx skills add ipitchford/claimpack \
  --skill consume-claimpack \
  --skill publish-claimpack
```

Install only the fail-closed consumer when publication support is unnecessary:

```sh
npx skills add ipitchford/claimpack --skill consume-claimpack
```

Review skill contents before installation and pin a release or commit when the
workflow is load-bearing. Installing a skill makes instructions available to
an agent; it does not authenticate any ClaimPack or certify a scientific
claim.

For an immutable installation, clone the candidate tag and install the two
skills from that checkout:

```sh
git clone --depth 1 --branch v0.1.0-candidate.1 \
  https://github.com/ipitchford/claimpack.git
npx skills add ./claimpack \
  --skill consume-claimpack \
  --skill publish-claimpack
```

## Install the CLI

The dependency-free Python consumer requires Python 3.11 or newer. Clone the
immutable candidate tag and install the CLI locally:

```sh
git clone --depth 1 --branch v0.1.0-candidate.1 \
  https://github.com/ipitchford/claimpack.git
python3 -m pip install ./claimpack
```

The release and skill version `0.1.0-candidate.1` corresponds exactly to the
PEP 440 Python distribution version `0.1.0rc1`; UseReceipts report the latter.

Then validate and inspect one reference pack:

```sh
claimpack validate claimpack/examples/z20
claimpack inspect claimpack/examples/z20
```

When using the CLI outside a repository checkout, pass a local ClaimPack path.
The `examples/` and top-level `policies/` directories are repository resources
rather than installed Python package data; the consumer skill separately
bundles its cautious example policy.

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
- separate installable consumer and producer Agent Skills;
- a 12-case, catalogue-aligned adversarial “badclaims” gauntlet;
- real reference-only seed packages for candidate mathematics;
- an offline randomized A/B experiment builder and deterministic scorer that
  receives no explicit condition field, with a documented commitment-masking
  defect that must be fixed before comparative use.

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

The cautious policy intentionally returns `UNKNOWN` for all six reference
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
| `examples/degree-difference-affine-slices` | Product-resultant degree-difference theorem and complete cubic classification | Zenodo `21647593`, archive SHA-256 pinned |
| `examples/exotic-affine-spheres-quadratic-cubic` | Transverse exotic three-sphere identification and universal quadratic-cubic exclusion | Zenodo `21653108`, archive SHA-256 pinned |
| `examples/reducible-incidence-divisors-affine-slices` | Incidence-divisor classification, adjacent Hodge defects, and conditional isolation theorem | Zenodo `21653119`, archive SHA-256 pinned |

The z(20) and VR2 packs reuse one byte-identical ClaimVersion for the exact
two-fixed-core UNSAT subclaim. The Erdős 848 pack separately records its
load-bearing imported high-threshold theorem. The exotic and reducible packs
likewise name the precise degree-difference and cubic-classification claims
they reuse. This prevents a whole-paper dependency from hiding the smaller
statement actually imported.

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
- `skills/consume-claimpack/` — installable safe consumer-agent procedure;
- `skills/publish-claimpack/` — installable producer-agent procedure;
- `tools/send_press_notice_email.py` — optional external email-notice helper;
- `DISTRIBUTION.md` — public dissemination and channel guidance;
- `catalog/catalog.json` — immutable static discovery snapshot;
- `badclaims/` and `gauntlet/` — adversarial behavior contract;
- `evaluation/COMMITMENT_MASKING_ERRATUM.md` — known experiment commitment
  leak and required correction;
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
hypothesis masking and intended scorer masking. Participants can see which
representation they received, so this is not a fully blinded design. The
current unkeyed bundle commitments also allow a repository-aware scorer to
reconstruct the arm before seed reveal; current runs therefore did not enforce
scorer masking.

Four developmental smoke iterations are now preserved under
`evaluation/results/`. They exposed, in sequence, a provider-schema rejection,
an exact-identifier/output mismatch, two operator-launch failures, and a
provider-versus-trusted-validator uniqueness mismatch. The latest iteration
reached four fresh model sessions; three outputs were strictly valid and one
was retained as invalid. Every explicit allocation file entered the repository
only after the applicable raw outputs and scores were committed, but the
published bundle IDs already leaked the arms by candidate reconstruction.

These runs exercise important failure-retention, receipt-to-commitment binding,
output capture, separate-dimension scoring, and receipt-sealing paths. None is
semantically scorable as a complete A/B study, and none is an efficacy study,
a scientific-truth assessment, or evidence that ClaimPack improves agent
behavior. Comparative claims require the broader controls, cases, replication,
isolation, and independent scoring described in `evaluation/README.md` and
`EVALUATION.md`. See `evaluation/COMMITMENT_MASKING_ERRATUM.md`.

## Rights

To the extent its contributors hold the relevant rights, the original
contents of this prototype are dedicated to the public domain under
CC0 1.0 Universal. Referenced research artifacts and third-party material
retain their own rights and are not relicensed here. See `PUBLIC_DOMAIN.md`
and `LICENSE`.
