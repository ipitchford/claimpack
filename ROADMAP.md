# Roadmap

## v0.1 candidate gate

- run blinded cold-agent comparisons described in `EVALUATION.md`;
- add full descriptive JSON Schemas without weakening the Python validator;
- expand badclaims with retraction races, duplicate routes, and empirical
  estimand/data cases;
- have independent agents implement the consumer from `SPEC.md` alone;
- record every observed false `ALLOW`, qualifier loss, unsafe tool action, and
  interoperability failure; and
- revise identifiers and schemas only through explicit version lineage.

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
