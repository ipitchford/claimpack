# Roadmap

## v0.1 candidate gate

- complete the developmental randomized A/B smoke described in
  `evaluation/README.md`, retaining invalid outputs, timeouts, and contamination
  attempts as outcomes;
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
