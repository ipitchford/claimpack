# Roadmap

## v0.1 candidate gate

- retain the completed developmental smoke lineage described in
  `evaluation/README.md`; its failed and invalid outcomes are part of the
  protocol record, not discardable pretests;
- align every provider-compatible output constraint with the trusted validator,
  or remove non-load-bearing participant self-report fields that the provider
  cannot enforce;
- derive action evidence from supervisor traces, or compare participant command
  self-reports set-semantically, rather than using duplicate prose entries as a
  transport-level exclusion;
- replace unkeyed bundle IDs in preregistration and score-lock records with a
  specified hiding commitment, such as a salted hash or HMAC whose reveal can
  be verified after scores are locked;
- make the audit rehash raw answers and traces, bind the registered
  client/reasoning/sandbox/runtime fields, and reject a ScoreReceipt for every
  non-completed run rather than merely making the study non-scorable;
- before making a comparative efficacy claim, add genuine `ALLOW` and `DENY`
  controls, wrong-encoding and retraction cases, replicated fresh subjects,
  hard runtime isolation, and independent scorers;
- add full descriptive JSON Schemas without weakening the Python validator;
- expand badclaims with retraction races, duplicate routes, and empirical
  estimand/data cases;
- have independent agents implement the consumer from `SPEC.md` alone;
- record every observed false `ALLOW`, qualifier loss, unsafe tool action, and
  interoperability failure; and
- revise identifiers and schemas only through explicit version lineage.

The developmental smoke is a harness-validation gate, not a ClaimPack
effectiveness study, a scientific-truth assessment, or a fully blinded
experiment. Participant network prohibitions do not count as operating-system
network isolation unless the runtime enforces and records them.

The current four smoke iterations exercised the full commit-before-reveal
workflow but did not produce a semantically scorable complete comparison.
That is a recorded gate result, not a reason to weaken exclusions or replace
failed trials. They also exposed that withholding the seed does not hide arms
when public bundle IDs are reconstructable. The next comparative schedule
begins only after the hiding-commitment, output-contract, multi-case controls,
hard-isolation, and independent-scoring requirements above are met.

## Optional profiles after the gate

- DSSE/in-toto or Sigstore envelopes for byte authentication;
- Software Heritage, RO-Crate, PROV-O, CodeMeta, CITATION.cff, SPDX, DataCite,
  and arXiv projections;
- proof-assistant, SAT/SMT, computer-algebra, and empirical-science adapters;
- restricted-data and privacy-aware evidence records;
- a networked ClaimWatch that consumes signed append-only events; and
- a static GitHub-hosted catalogue with mirrors and independent forks.

These profiles may authenticate, discover, or add evidence. None may convert
structural validity into a global truth status.

## Infrastructure preference

Prefer ordinary Git repositories, static files, version DOIs, Software
Heritage, and optional CI. Do not introduce a database, central authority, paid
service, or always-on server until measured use demonstrates that static,
forkable infrastructure is insufficient.
