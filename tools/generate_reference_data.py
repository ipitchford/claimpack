#!/usr/bin/env python3
"""Generate deterministic policies, seed packs, and the static catalogue."""

from __future__ import annotations

import argparse
import re
import unicodedata
from pathlib import Path
from typing import Any

from claimpack.build import seal_record, write_pack
from claimpack.canonical import canonical_bytes, pretty_bytes
from claimpack.ids import ni_sha256, policy_digest_for, sha256_label
from claimpack.records import DIMENSIONS
from claimpack.validate import validate_pack

CREATED = "2026-07-29T12:00:00+00:00"
ISSUED = CREATED


def actor(
    actor_id: str,
    display_name: str,
    kind: str,
    **optional: str,
) -> dict[str, str]:
    return {
        "display_name": display_name,
        "id": actor_id,
        "kind": kind,
        **optional,
    }


def provenance(
    actors: list[dict[str, str]],
    roles: list[tuple[str, str, str]],
) -> dict[str, Any]:
    return {
        "actors": actors,
        "roles": [
            {"actor_id": actor_id, "date": date, "role": role}
            for actor_id, role, date in roles
        ],
    }


def source(
    *,
    kind: str,
    locator: str,
    immutable: bool,
    rights: str,
    version: str = "",
    digest: str = "",
) -> dict[str, Any]:
    value: dict[str, Any] = {
        "immutable": immutable,
        "kind": kind,
        "locator": locator,
        "rights": rights,
    }
    if version:
        value["version"] = version
    if digest:
        value["digest"] = digest
    return value


def claim(
    *,
    natural: str,
    latex: str,
    definitions: list[tuple[str, str]],
    quantifiers: list[str],
    claim_kind: str,
    conditions: list[str],
    exclusions: list[str],
    non_implications: list[str],
    targets: list[str],
    structured_scope: dict[str, Any],
    aliases: list[str],
    problem_refs: list[dict[str, str]],
    sources: list[dict[str, Any]],
    claim_provenance: dict[str, Any],
    dependency_targets: list[dict[str, str]] | None = None,
    claim_version: str = "0.1-candidate",
    issued_at: str = ISSUED,
    rights_exclusions: list[str] | None = None,
) -> dict[str, Any]:
    return seal_record(
        {
            "aliases": aliases,
            "claim_version": claim_version,
            "dependency_targets": dependency_targets or [],
            "formal_statements": [],
            "issued_at": issued_at,
            "lineage": [],
            "problem_refs": problem_refs,
            "protocol_version": "0.1.0",
            "provenance": claim_provenance,
            "record_type": "claim-version",
            "rights": {
                "exclusions": rights_exclusions or [],
                "license": "CC0-1.0",
                "scope": (
                    "This ClaimPack record and original source-repository "
                    "content only to the extent the rights holder may dedicate it."
                ),
            },
            "scope": {
                "claim_kind": claim_kind,
                "conditions": conditions,
                "exclusions": exclusions,
                "non_implications": non_implications,
                "scope_note": "",
                "structured_scope": structured_scope,
                "targets": targets,
            },
            "sources": sources,
            "statement": {
                "definitions": [
                    {"meaning": meaning, "term": term} for term, meaning in definitions
                ],
                "language": "en",
                "latex": latex,
                "natural": natural,
                "quantifiers": quantifiers,
            },
        }
    )


def external_evidence(
    *,
    subject: dict[str, Any],
    issuer_id: str,
    issuer_name: str,
    locator: str,
    digest: str,
    name: str,
    coverage: list[str],
    limitations: list[str],
    replay_command: str,
    expected_outputs: list[str],
    rights: str,
    media_type: str = "application/zip",
) -> dict[str, Any]:
    return seal_record(
        {
            "artifacts": [
                {
                    "digest": digest,
                    "embedded": False,
                    "locator": locator,
                    "media_type": media_type,
                    "name": name,
                    "rights": rights,
                }
            ],
            "coverage": coverage,
            "evidence_kind": "manuscript",
            "issued_at": ISSUED,
            "issuer": {
                "display_name": issuer_name,
                "id": issuer_id,
                "kind": "organization",
            },
            "limitations": limitations
            + ["Referenced archive is not embedded in this seed ClaimPack."],
            "method": (
                "Reference-only binding to the exact public release archive "
                "and its repository-reported assurance boundary."
            ),
            "protocol_version": "0.1.0",
            "record_type": "evidence",
            "replay": {
                "command": replay_command,
                "display_only": True,
                "environment_digest": "",
                "expected_outputs": expected_outputs,
                "resource_budget": {
                    "cpu": "source-repository dependent",
                    "disk": "source-repository dependent",
                    "network": "forbidden in core ClaimPack consumption",
                    "wall_time": "source-repository dependent",
                },
            },
            "subject": {
                "record_id": subject["record_id"],
                "record_type": subject["record_type"],
            },
        }
    )


def assessment(
    *,
    target: dict[str, Any],
    issuer_id: str,
    issuer_name: str,
    dimension: str,
    outcome: str,
    summary: str,
    qualifications: list[str],
    evidence_refs: list[str],
    kind: str = "author-status",
) -> dict[str, Any]:
    return seal_record(
        {
            "assessment_kind": kind,
            "authentication": {"status": "unverified"},
            "dimension": dimension,
            "evidence_refs": evidence_refs,
            "independence": {
                "actor": "same as repository-reported producer",
                "code": "not independently reimplemented",
                "communication_exposure": "shared release materials",
                "coordination_parent": "repository publication workflow",
                "data": "same release artifacts",
                "environment": "repository-reported local environment",
                "method": "repository self-report",
                "model_provider": "not an independence claim",
                "organization": "not independent",
            },
            "issued_at": ISSUED,
            "issuer": {
                "display_name": issuer_name,
                "id": issuer_id,
                "kind": "organization",
            },
            "method": "Repository-reported status; not independent verification.",
            "outcome": outcome,
            "protocol_version": "0.1.0",
            "qualifications": qualifications,
            "record_type": "assessment",
            "responds_to": [],
            "stance": "supports" if outcome == "pass" else "neutral",
            "summary": summary,
            "supersedes": [],
            "target": {
                "record_id": target["record_id"],
                "record_type": target["record_type"],
            },
            "target_claim_id": (
                target["claim_id"] if target["record_type"] == "claim-version" else ""
            ),
            "withdraws": [],
        }
    )


def status_vector(
    target: dict[str, Any],
    evidence: dict[str, Any],
    *,
    issuer_id: str,
    issuer_name: str,
    passing: set[str],
    notes: dict[str, str],
) -> list[dict[str, Any]]:
    records = []
    for dimension in sorted(DIMENSIONS):
        outcome = "pass" if dimension in passing else "unknown"
        kind = (
            "automated-check"
            if dimension
            in {
                "formal-or-certificate-verification",
                "reproducibility",
                "version-stability",
            }
            else "author-status"
        )
        records.append(
            assessment(
                target=target,
                issuer_id=issuer_id,
                issuer_name=issuer_name,
                dimension=dimension,
                outcome=outcome,
                summary=notes.get(
                    dimension,
                    f"Repository-reported {dimension} status is {outcome}.",
                ),
                qualifications=[
                    "Repository-reported assessment; no external authentication.",
                    "A passing self-assessment is not an independent verification.",
                ],
                evidence_refs=[evidence["record_id"]],
                kind=kind,
            )
        )
    return records


def depends_on(
    source_claim: dict[str, Any],
    target_claim: dict[str, Any],
    *,
    issuer_id: str,
    issuer_name: str,
    limitation: str,
) -> dict[str, Any]:
    return seal_record(
        {
            "issued_at": ISSUED,
            "issuer": {
                "display_name": issuer_name,
                "id": issuer_id,
                "kind": "organization",
            },
            "load_bearing": True,
            "protocol_version": "0.1.0",
            "record_type": "relation",
            "relation": "depends-on",
            "semantic_alignment": {
                "definition_map": [
                    {
                        "note": "Repository-reported dependency mapping.",
                        "source_term": "imported result",
                        "target_term": "exact dependency ClaimVersion",
                    }
                ],
                "limitations": [limitation],
                "status": "partial",
            },
            "source": {
                "record_id": source_claim["record_id"],
                "record_type": "claim-version",
            },
            "target": {
                "record_id": target_claim["record_id"],
                "record_type": "claim-version",
            },
        }
    )


def relation_status(
    relation: dict[str, Any],
    *,
    issuer_id: str,
    issuer_name: str,
) -> dict[str, Any]:
    return assessment(
        target=relation,
        issuer_id=issuer_id,
        issuer_name=issuer_name,
        dimension="semantic-scope-match",
        outcome="unknown",
        summary=(
            "The dependency mapping is repository-reported and has not been "
            "independently audited."
        ),
        qualifications=[
            "No independent semantic-correspondence assessment is supplied."
        ],
        evidence_refs=[],
        kind="correspondence",
    )


def cautious_policy() -> dict[str, Any]:
    policy: dict[str, Any] = {
        "adverse_issuers": ["*"],
        "dimensions": {
            dimension: {
                "accepted_issuers": ["independent-reviewer"],
                "required": True,
            }
            for dimension in sorted(DIMENSIONS)
        },
        "limits": {
            "assessment_count": "512",
            "dependency_depth": "16",
            "dependency_nodes": "128",
        },
        "max_assessment_age_days": "3650",
        "open_objection_effect": "unknown",
        "policy_digest": "",
        "policy_id": "claimpack:cautious-scientific-use:v0.1",
        "policy_version": "0.1",
        "require_authenticated_positive": True,
        "require_complete_objection_search": True,
        "require_embedded_evidence_for_positive": True,
        "require_evidence_for_positive": True,
    }
    policy["policy_digest"] = policy_digest_for(policy)
    return policy


def search_fingerprint(statement: str) -> str:
    normalized = unicodedata.normalize("NFKC", statement).casefold()
    normalized = re.sub(r"\s+", " ", normalized).strip()
    return sha256_label(normalized.encode("utf-8"))


def build(root: Path) -> None:
    examples = root / "examples"
    policies = root / "policies"
    catalog_dir = root / "catalog"
    for target in {examples, policies, catalog_dir}:
        if target.exists():
            raise SystemExit(f"refusing to overwrite generated path: {target}")
    policies.mkdir(parents=True)
    catalog_dir.mkdir(parents=True)
    (policies / "cautious-scientific-use-v0.1.json").write_bytes(
        pretty_bytes(cautious_policy())
    )

    z20_actors = [
        actor("human:ian-pitchford", "Ian Pitchford", "human"),
        actor(
            "ai:gpt-5.6-sol",
            "GPT-5.6 Sol",
            "ai-system",
            model_family="GPT-5.6 Sol",
            model_provider="OpenAI",
        ),
        actor(
            "ai:claude-opus-5",
            "Claude Opus 5",
            "ai-system",
            model_family="Claude Opus 5",
            model_provider="Anthropic",
        ),
        actor("software:openai-codex", "OpenAI Codex", "software"),
    ]
    z20_provenance = provenance(
        z20_actors,
        [
            (
                "human:ian-pitchford",
                "problem selection and research mediation",
                "2026-07-26T00:00:00+00:00",
            ),
            (
                "ai:gpt-5.6-sol",
                "two-core reduction, CNF generator, solver, and certificates",
                "2026-07-26T00:00:00+00:00",
            ),
            (
                "ai:claude-opus-5",
                "verification, enumeration, lower bound, and exposition",
                "2026-07-26T00:00:00+00:00",
            ),
            ("software:openai-codex", "release audit and ClaimPack encoding", CREATED),
        ],
    )
    z20_repo = "https://github.com/ipitchford/z20-cochromatic"
    z20_commit = "3c7e520fdc0615f5c700761c2b1e5108dcc836e7"
    z20_digest = (
        "sha256:2b92e5febf5deaeb86db96ef37ddd7df33ac4022453090291c72633fda0310e5"
    )
    z20_sources = [
        source(
            kind="doi-version",
            locator="https://doi.org/10.5281/zenodo.21647645",
            immutable=True,
            version="candidate-2026-07-26",
            digest=z20_digest,
            rights="Repository original content is CC0-1.0; third-party inputs excluded.",
        ),
        source(
            kind="git-commit",
            locator=f"{z20_repo}/commit/{z20_commit}",
            immutable=True,
            version=z20_commit,
            rights="Repository original content is CC0-1.0; third-party inputs excluded.",
        ),
    ]
    fixed_core = claim(
        natural=(
            "For each of the two order-16 (4,4)-Ramsey cores used in the "
            "pinned z(20) release, the exact fixed-core CNF over the 64 cross "
            "edges is unsatisfiable."
        ),
        latex=(
            r"\operatorname{UNSAT}(F_{\mathrm{core}\,0})\ \land\ "
            r"\operatorname{UNSAT}(F_{\mathrm{core}\,1})"
        ),
        definitions=[
            (
                "fixed-core CNF",
                "The exact core-specific formula generated and hash-pinned by the z(20) release.",
            ),
            (
                "(4,4)-Ramsey core",
                "A graph on 16 vertices with neither a 4-clique nor an independent 4-set.",
            ),
        ],
        quantifiers=["for each core index i in {0,1}"],
        claim_kind="finite-case",
        conditions=["The claim concerns only the exact pinned CNF bytes."],
        exclusions=[
            "No end-to-end graph-theoretic semantic equivalence is asserted by this subclaim."
        ],
        non_implications=[],
        targets=["two exact finite SAT instances"],
        structured_scope={
            "core_count": "2",
            "cross_edge_variables": "64 per core",
            "domain": "finite SAT",
        },
        aliases=["z20 fixed-core UNSAT pair", "two Ramsey-core refutations"],
        problem_refs=[],
        sources=z20_sources,
        claim_provenance=z20_provenance,
    )
    fixed_evidence = external_evidence(
        subject=fixed_core,
        issuer_id="repository:ipitchford/z20-cochromatic",
        issuer_name="ipitchford/z20-cochromatic",
        locator="https://doi.org/10.5281/zenodo.21647645",
        digest=z20_digest,
        name="z20-candidate-2026-07-26.zip",
        coverage=["exact CNFs", "DRUP and LRAT refutations", "local replay receipt"],
        limitations=[
            "Replay was local, not independent external reproduction.",
            "Certificate checking establishes the exact SAT layer only.",
        ],
        replay_command="make verify",
        expected_outputs=[
            "drat-trim reports s VERIFIED for both cores",
            "cake_lpr prints exact text s VERIFIED UNSAT for both cores",
        ],
        rights="CC0-1.0 for original repository content; see source exclusions.",
    )
    fixed_vector = status_vector(
        fixed_core,
        fixed_evidence,
        issuer_id="repository:ipitchford/z20-cochromatic",
        issuer_name="ipitchford/z20-cochromatic",
        passing={
            "formal-or-certificate-verification",
            "provenance-quality",
            "reproducibility",
            "statement-precision",
            "version-stability",
        },
        notes={
            "formal-or-certificate-verification": (
                "Repository reports exact CNFs accepted by multiple checkers, "
                "including a formally verified checking core."
            ),
            "independent-reproduction": "No independent external reproduction is claimed.",
            "semantic-scope-match": "The graph-to-CNF semantic bridge is a separate assurance layer.",
        },
    )

    z20_claim = claim(
        natural=("The maximum cochromatic number among graphs on 20 vertices is 6."),
        latex=r"z(20)=6",
        definitions=[
            (
                "z(G)",
                "The least number of vertex classes partitioning V(G), each inducing a clique or an independent set.",
            ),
            ("z(n)", "The maximum of z(G) over all graphs G with n vertices."),
        ],
        quantifiers=["maximum over every finite simple graph G with |V(G)|=20"],
        claim_kind="full-result",
        conditions=["Finite simple undirected graphs."],
        exclusions=[
            "No uniqueness assertion is made for extremal graphs or partitions."
        ],
        non_implications=[],
        targets=["exact value at n=20"],
        structured_scope={"n": "20", "value": "6", "domain": "graph theory"},
        aliases=["z(20)=6", "20-vertex cochromatic number"],
        problem_refs=[
            {
                "id": "758",
                "locator": "https://www.erdosproblems.com/758",
                "scheme": "erdos-problems",
            }
        ],
        sources=z20_sources,
        claim_provenance=z20_provenance,
        dependency_targets=[
            {"record_id": fixed_core["record_id"], "record_type": "claim-version"}
        ],
    )
    z20_evidence = external_evidence(
        subject=z20_claim,
        issuer_id="repository:ipitchford/z20-cochromatic",
        issuer_name="ipitchford/z20-cochromatic",
        locator="https://doi.org/10.5281/zenodo.21647645",
        digest=z20_digest,
        name="z20-candidate-2026-07-26.zip",
        coverage=["candidate paper", "hand-checkable lower bound", "local full replay"],
        limitations=[
            "The complete result has no documented external human verification.",
            "No independent external reproduction or end-to-end formalization is claimed.",
        ],
        replay_command="make verify",
        expected_outputs=["source repository verification target completes"],
        rights="CC0-1.0 for original repository content; see source exclusions.",
    )
    z20_vector = status_vector(
        z20_claim,
        z20_evidence,
        issuer_id="repository:ipitchford/z20-cochromatic",
        issuer_name="ipitchford/z20-cochromatic",
        passing={
            "canonical-problem-correspondence",
            "formal-or-certificate-verification",
            "provenance-quality",
            "reproducibility",
            "statement-precision",
            "version-stability",
        },
        notes={
            "proof-completeness": "Unrefereed candidate proof; complete correctness remains unestablished.",
            "independent-reproduction": "No independent external reproduction is claimed.",
            "known-objections": "No complete global objection search is claimed.",
            "semantic-scope-match": "The graph-to-CNF semantic bridge is not end-to-end formalized.",
        },
    )
    z20_relation = depends_on(
        z20_claim,
        fixed_core,
        issuer_id="repository:ipitchford/z20-cochromatic",
        issuer_name="ipitchford/z20-cochromatic",
        limitation="The exact SAT subclaim is load-bearing, but the graph-to-CNF bridge remains separately assessed.",
    )
    z20_records = (
        [fixed_core, fixed_evidence]
        + fixed_vector
        + [
            z20_claim,
            z20_relation,
            relation_status(
                z20_relation,
                issuer_id="repository:ipitchford/z20-cochromatic",
                issuer_name="ipitchford/z20-cochromatic",
            ),
            z20_evidence,
        ]
        + z20_vector
    )
    write_pack(
        examples / "z20",
        records=z20_records,
        created_at=CREATED,
        primary_claim_record_id=z20_claim["record_id"],
    )

    vr2_actors = [
        actor("human:ian-pitchford", "Ian Pitchford", "human"),
        actor(
            "ai:gpt-5.6-sol",
            "GPT 5.6 Sol",
            "ai-system",
            model_family="GPT 5.6 Sol",
            model_provider="OpenAI",
        ),
        actor(
            "ai:claude-opus-4.8-5",
            "Claude Opus 4.8 / 5",
            "ai-system",
            model_family="Claude Opus 4.8 / 5",
            model_provider="Anthropic",
        ),
        actor("software:openai-codex", "OpenAI Codex", "software"),
    ]
    vr2_provenance = provenance(
        vr2_actors,
        [
            (
                "human:ian-pitchford",
                "research mediation, maintenance, and publication",
                "2026-07-28T00:00:00+00:00",
            ),
            (
                "ai:gpt-5.6-sol",
                "mathematical and computational contribution",
                "2026-07-28T00:00:00+00:00",
            ),
            (
                "ai:claude-opus-4.8-5",
                "mathematical and computational contribution",
                "2026-07-28T00:00:00+00:00",
            ),
            ("software:openai-codex", "release audit and ClaimPack encoding", CREATED),
        ],
    )
    vr2_digest = (
        "sha256:e14178610233f9e5960da06162e07f3a0ce9aa65799dff3d456958a417997f4f"
    )
    vr2_commit = "b303d7d61d1a4cdf6ff0f1c18eee40eded0583cc"
    vr2_sources = [
        source(
            kind="doi-version",
            locator="https://doi.org/10.5281/zenodo.21647654",
            immutable=True,
            version="0.1-candidate",
            digest=vr2_digest,
            rights="Repository original content is CC0-1.0; third-party inputs excluded.",
        ),
        source(
            kind="git-commit",
            locator=f"{z20_repo}/commit/{vr2_commit}",
            immutable=True,
            version=vr2_commit,
            rights="Repository original content is CC0-1.0; third-party inputs excluded.",
        ),
    ]
    vr2_claim = claim(
        natural=(
            "The least n such that every red-blue edge-colouring of K_n "
            "contains two vertex-disjoint monochromatic copies of K_4 is 20; "
            "the copies need not have the same colour."
        ),
        latex=r"\mathrm{VR}_2(K_4)=20",
        definitions=[
            (
                "VR_2(K_4)",
                "The least n such that every red-blue edge-colouring of K_n has two pairwise vertex-disjoint monochromatic K_4 subgraphs.",
            )
        ],
        quantifiers=["for every red-blue edge-colouring of K_n"],
        claim_kind="full-result",
        conditions=["The two monochromatic copies may have different colours."],
        exclusions=["No enumeration or uniqueness claim for extremal colourings."],
        non_implications=[],
        targets=["exact two-copy vertex Ramsey number for K_4"],
        structured_scope={"clique": "K_4", "copy_count": "2", "value": "20"},
        aliases=["VR2(K4)=20", "two vertex-disjoint monochromatic K4s"],
        problem_refs=[
            {
                "id": "VR_2(K_4)",
                "scheme": "vertex-ramsey",
            }
        ],
        sources=vr2_sources,
        claim_provenance=vr2_provenance,
        dependency_targets=[
            {"record_id": fixed_core["record_id"], "record_type": "claim-version"}
        ],
    )
    vr2_evidence = external_evidence(
        subject=vr2_claim,
        issuer_id="repository:ipitchford/z20-cochromatic",
        issuer_name="ipitchford/z20-cochromatic",
        locator="https://doi.org/10.5281/zenodo.21647654",
        digest=vr2_digest,
        name="z20-vr2-k4-v0.1-candidate.zip",
        coverage=[
            "candidate paper",
            "direct K_19 lower-bound verifier",
            "pinned upper-bound dependency",
        ],
        limitations=[
            "The upper bound reuses rather than independently reproduces fixed-core certificates.",
            "No independent external reproduction, peer review, or end-to-end formalization is claimed.",
        ],
        replay_command="python3 applications/vr2-k4/verify_lower_bound.py",
        expected_outputs=["disjoint monochromatic pair exists: False"],
        rights="CC0-1.0 for original repository content; see source exclusions.",
    )
    vr2_vector = status_vector(
        vr2_claim,
        vr2_evidence,
        issuer_id="repository:ipitchford/z20-cochromatic",
        issuer_name="ipitchford/z20-cochromatic",
        passing={
            "canonical-problem-correspondence",
            "formal-or-certificate-verification",
            "provenance-quality",
            "reproducibility",
            "statement-precision",
            "version-stability",
        },
        notes={
            "proof-completeness": "Unrefereed candidate proof; complete correctness remains unestablished.",
            "independent-reproduction": "The upper bound explicitly reuses the z(20) certificate layer.",
            "semantic-scope-match": "The complete graph-to-CNF bridge is not independently audited.",
        },
    )
    vr2_relation = depends_on(
        vr2_claim,
        fixed_core,
        issuer_id="repository:ipitchford/z20-cochromatic",
        issuer_name="ipitchford/z20-cochromatic",
        limitation="The upper bound imports the exact fixed-core UNSAT pair; the semantic bridge remains separately qualified.",
    )
    vr2_records = (
        [fixed_core, fixed_evidence]
        + fixed_vector
        + [
            vr2_claim,
            vr2_relation,
            relation_status(
                vr2_relation,
                issuer_id="repository:ipitchford/z20-cochromatic",
                issuer_name="ipitchford/z20-cochromatic",
            ),
            vr2_evidence,
        ]
        + vr2_vector
    )
    write_pack(
        examples / "vr2-k4",
        records=vr2_records,
        created_at=CREATED,
        primary_claim_record_id=vr2_claim["record_id"],
    )

    erdos_actors = [
        actor("human:ian-pitchford", "Ian Pitchford", "human"),
        actor("software:openai-codex", "OpenAI Codex", "software"),
        actor("human:nat-sothanaphan", "Nat Sothanaphan", "human"),
        actor("human:mehtaab-sawhney", "Mehtaab Sawhney", "human"),
    ]
    erdos_provenance = provenance(
        erdos_actors,
        [
            (
                "software:openai-codex",
                "proof, replay, and audit development",
                "2026-07-28T00:00:00+00:00",
            ),
            (
                "human:ian-pitchford",
                "research direction, mediation, maintenance, and publication",
                "2026-07-28T00:00:00+00:00",
            ),
            (
                "human:nat-sothanaphan",
                "external explicit-threshold theorem cited as input",
                "2026-03-24T00:00:00+00:00",
            ),
            (
                "human:mehtaab-sawhney",
                "external analytic input cited by the source repository",
                "2026-07-28T00:00:00+00:00",
            ),
        ],
    )
    tail_pdf_digest = (
        "sha256:8162113a571dc2283fc77de1cdf36e7abf424eeec952aa27cf82a4f44b3a796f"
    )
    tail_claim = claim(
        natural=(
            "For every integer N at least 264000000000000000, the maximum "
            "size f(N) of an admissible subset is at most floor((N+18)/25)."
        ),
        latex=(
            r"N\ge264000000000000000\Longrightarrow "
            r"f(N)\le\left\lfloor\frac{N+18}{25}\right\rfloor"
        ),
        definitions=[
            (
                "admissible",
                "A subset A of {1,...,N} such that ab+1 is nonsquarefree for every a,b in A, including a=b.",
            ),
            ("f(N)", "The maximum cardinality of an admissible subset."),
        ],
        quantifiers=["for every integer N >= 264000000000000000"],
        claim_kind="asymptotic-result",
        conditions=[],
        exclusions=[],
        non_implications=[],
        targets=["explicit high-threshold upper bound"],
        structured_scope={
            "lower_endpoint": "264000000000000000",
            "range": "unbounded above",
        },
        aliases=["Sothanaphan explicit threshold for Erdős 848"],
        problem_refs=[
            {
                "id": "848",
                "locator": "https://www.erdosproblems.com/848",
                "scheme": "erdos-problems",
            }
        ],
        sources=[
            source(
                kind="other",
                locator="https://drive.google.com/file/d/1ujhm4_WYpgRV_rd1rJXIfHyvx16COEKe/view",
                immutable=False,
                version="2026-03-24",
                digest=tail_pdf_digest,
                rights="Third-party source; not relicensed by ClaimPack.",
            )
        ],
        claim_provenance=erdos_provenance,
        issued_at=CREATED,
        rights_exclusions=["The source theorem and PDF remain third-party material."],
    )
    erdos_digest = (
        "sha256:fcd83b8986bf55784cf97513513d628af1fa5fe3bb0a2bdb869e1307dbbb8060"
    )
    erdos_commit = "56b27ae765f04195dc867db5e1c52750d5f721ae"
    erdos_repo = "https://github.com/ipitchford/erdos-848-all-n"
    erdos_sources = [
        source(
            kind="doi-version",
            locator="https://doi.org/10.5281/zenodo.21647629",
            immutable=True,
            version="0.1-candidate",
            digest=erdos_digest,
            rights="Repository original content is CC0-1.0; third-party analytic inputs excluded.",
        ),
        source(
            kind="git-commit",
            locator=f"{erdos_repo}/commit/{erdos_commit}",
            immutable=True,
            version=erdos_commit,
            rights="Repository original content is CC0-1.0; third-party analytic inputs excluded.",
        ),
    ]
    erdos_claim = claim(
        natural=(
            "For every positive integer N, the maximum size f(N) of a subset "
            "A of {1,...,N} such that ab+1 is nonsquarefree for every a,b in "
            "A, including a=b, equals floor((N+18)/25)."
        ),
        latex=(
            r"f(N)=\left\lfloor\frac{N+18}{25}\right\rfloor"
            r"\quad\text{for every }N\ge1"
        ),
        definitions=[
            (
                "nonsquarefree",
                "Divisible by the square of at least one prime.",
            ),
            (
                "f(N)",
                "The largest cardinality of A subset {1,...,N} for which ab+1 is nonsquarefree for every ordered choice a,b in A, including a=b.",
            ),
        ],
        quantifiers=[
            "for every positive integer N",
            "for every a,b in A including a=b",
        ],
        claim_kind="full-result",
        conditions=["Positive integer N; diagonal pairs a=b are included."],
        exclusions=["No uniqueness claim for extremal sets."],
        non_implications=[],
        targets=["exact extremal value for every positive N"],
        structured_scope={"N": "all positive integers", "formula_denominator": "25"},
        aliases=["Erdős Problem 848 all-N formula", "f(N)=floor((N+18)/25)"],
        problem_refs=[
            {
                "id": "848",
                "locator": "https://www.erdosproblems.com/848",
                "scheme": "erdos-problems",
            }
        ],
        sources=erdos_sources,
        claim_provenance=erdos_provenance,
        dependency_targets=[
            {"record_id": tail_claim["record_id"], "record_type": "claim-version"}
        ],
    )
    erdos_evidence = external_evidence(
        subject=erdos_claim,
        issuer_id="repository:ipitchford/erdos-848-all-n",
        issuer_name="ipitchford/erdos-848-all-n",
        locator="https://doi.org/10.5281/zenodo.21647629",
        digest=erdos_digest,
        name="erdos-848-all-n.zip",
        coverage=[
            "candidate all-N proof",
            "finite certificates",
            "18-stage local replay",
        ],
        limitations=[
            "The high range imports a pinned third-party analytic theorem.",
            "A gapless range ledger does not by itself establish the component bounds.",
            "No independent external reproduction, peer review, or end-to-end formalization is claimed.",
        ],
        replay_command="make verify",
        expected_outputs=["complete fresh-extraction release replay passes all stages"],
        rights="CC0-1.0 for original repository content; third-party inputs excluded.",
    )
    tail_evidence = external_evidence(
        subject=tail_claim,
        issuer_id="repository:ipitchford/erdos-848-all-n",
        issuer_name="ipitchford/erdos-848-all-n",
        locator="https://drive.google.com/file/d/1ujhm4_WYpgRV_rd1rJXIfHyvx16COEKe/view",
        digest=tail_pdf_digest,
        name="explicit-threshold-note.pdf",
        coverage=["source-pinned explicit high-threshold theorem"],
        limitations=[
            "The analytic argument remains a mathematical input.",
            "This seed does not independently verify the analytic proof.",
            "The source is third-party and not bundled.",
        ],
        replay_command=(
            "python3 audit/verify_high_threshold_numerics_v1.py "
            "--source-pdf /path/to/official-threshold-note.pdf"
        ),
        expected_outputs=["directed exact-arithmetic numerical appendix checks pass"],
        rights="Third-party source; not relicensed by ClaimPack.",
        media_type="application/pdf",
    )
    tail_vector = status_vector(
        tail_claim,
        tail_evidence,
        issuer_id="repository:ipitchford/erdos-848-all-n",
        issuer_name="ipitchford/erdos-848-all-n",
        passing={
            "canonical-problem-correspondence",
            "provenance-quality",
            "statement-precision",
            "version-stability",
        },
        notes={
            "proof-completeness": "The analytic source is imported, not independently checked by this package.",
            "reproducibility": "Only a directed numerical appendix replay is repository-reported.",
        },
    )
    erdos_vector = status_vector(
        erdos_claim,
        erdos_evidence,
        issuer_id="repository:ipitchford/erdos-848-all-n",
        issuer_name="ipitchford/erdos-848-all-n",
        passing={
            "canonical-problem-correspondence",
            "formal-or-certificate-verification",
            "provenance-quality",
            "reproducibility",
            "statement-precision",
            "version-stability",
        },
        notes={
            "proof-completeness": "Unrefereed candidate stitched proof; complete correctness remains unestablished.",
            "independent-reproduction": "No independent external reproduction is claimed.",
            "semantic-scope-match": "The semantic bridge across all component ranges is not end-to-end formalized.",
        },
    )
    erdos_relation = depends_on(
        erdos_claim,
        tail_claim,
        issuer_id="repository:ipitchford/erdos-848-all-n",
        issuer_name="ipitchford/erdos-848-all-n",
        limitation="The all-N conclusion imports the source-pinned analytic high-threshold theorem.",
    )
    erdos_records = (
        [tail_claim, tail_evidence]
        + tail_vector
        + [
            erdos_claim,
            erdos_relation,
            relation_status(
                erdos_relation,
                issuer_id="repository:ipitchford/erdos-848-all-n",
                issuer_name="ipitchford/erdos-848-all-n",
            ),
            erdos_evidence,
        ]
        + erdos_vector
    )
    write_pack(
        examples / "erdos848",
        records=erdos_records,
        created_at=CREATED,
        primary_claim_record_id=erdos_claim["record_id"],
    )

    degree_actors = [
        actor("human:ian-pitchford", "Ian Pitchford", "human"),
        actor(
            "organization:openai-codex-anthropic-models",
            "OpenAI Codex / Anthropic models",
            "organization",
        ),
        actor("software:openai-codex", "OpenAI Codex", "software"),
    ]
    degree_provenance = provenance(
        degree_actors,
        [
            (
                "organization:openai-codex-anthropic-models",
                "repository-reported manuscript attribution",
                "2026-07-27T00:00:00+00:00",
            ),
            (
                "human:ian-pitchford",
                "research direction, mediation, maintenance, and publication",
                "2026-07-27T00:00:00+00:00",
            ),
            ("software:openai-codex", "ClaimPack encoding", CREATED),
        ],
    )
    degree_repo = "https://github.com/ipitchford/degree-difference-affine-slices"
    degree_commit = "38bb6c2054fd1e231233ee9c1bbd8ebf7b666685"
    degree_digest = (
        "sha256:8d0b0cfb3b43e3b7c7f32f62506ae66e824890e15a981b8498d41a07b4c2fe43"
    )
    degree_sources = [
        source(
            kind="doi-version",
            locator="https://doi.org/10.5281/zenodo.21647593",
            immutable=True,
            version="0.1-candidate",
            digest=degree_digest,
            rights=(
                "Repository original content is CC0-1.0 to the extent held; "
                "third-party material is excluded."
            ),
        ),
        source(
            kind="git-commit",
            locator=f"{degree_repo}/commit/{degree_commit}",
            immutable=True,
            version=degree_commit,
            rights=(
                "Repository original content is CC0-1.0 to the extent held; "
                "third-party material is excluded."
            ),
        ),
    ]
    degree_theorem = claim(
        natural=(
            "Let r,s>=1 and choose the standard monomial coefficient orders "
            "on V_r, V_s, and V_{r+s}. For Phi_{r,s}(A,B)=(AB,Res(A,B)), "
            "det D Phi_{r,s}=(-1)^{s(r+1)}(r-s)Res(A,B)^2. In particular, "
            "if r!=s, Phi_{r,s} is etale on the coprime locus {Res!=0}. "
            "For nonzero ell in V_{r+s}^*, if r!=s, projectivisation is a "
            "finite etale mu_{|s-r|}-torsor from the normalized slice "
            "tilde X_{r,s,ell} to U_{r,s,ell}; the induced multiplication "
            "map has generic degree |s-r| binom(r+s,r); and, if the "
            "resultant divisor R_{r,s} and multiplication-hyperplane divisor "
            "S_{r,s,ell} are prime, Cl(U_{r,s,ell}) is isomorphic to "
            "Z/|s-r|Z."
        ),
        latex=(
            r"\begin{gathered}"
            r"r,s\ge1,\qquad "
            r"\Phi_{r,s}(A,B)=(AB,\operatorname{Res}(A,B)),\\"
            r"\det D\Phi_{r,s}=(-1)^{s(r+1)}(r-s)"
            r"\operatorname{Res}(A,B)^2.\\"
            r"r\ne s\Longrightarrow "
            r"\widetilde X_{r,s,\ell}\longrightarrow U_{r,s,\ell}"
            r"\text{ is a finite \acute{e}tale }\mu_{|s-r|}\text{-torsor},\\"
            r"\deg(\widetilde X_{r,s,\ell}\to"
            r"\{C\in V_{r+s}:\ell(C)=1\})"
            r"=|s-r|\binom{r+s}{r},\\"
            r"\mathcal R_{r,s},\mathcal S_{r,s,\ell}\text{ prime}"
            r"\Longrightarrow\operatorname{Cl}(U_{r,s,\ell})"
            r"\simeq\mathbb Z/|s-r|\mathbb Z."
            r"\end{gathered}"
        ),
        definitions=[
            (
                "V_d",
                "The vector space Sym^d(W^*) of binary forms of degree d for a two-dimensional complex vector space W.",
            ),
            (
                "tilde X_{r,s,ell}",
                "The pairs (A,B) satisfying Res(A,B)=1 and ell(AB)=1.",
            ),
            (
                "U_{r,s,ell}",
                "The complement of the resultant and multiplication-hyperplane divisors in P(V_r) x P(V_s).",
            ),
        ],
        quantifiers=[
            "for every pair of integers r,s >= 1",
            "for every nonzero ell in V_{r+s}^* for the slice conclusions",
        ],
        claim_kind="stronger-result",
        conditions=[
            "The standard monomial coefficient orders and the manuscript's resultant convention are used.",
            "The class-group conclusion assumes both named boundary divisors are prime.",
        ],
        exclusions=["Degree-zero factors are outside the stated theorem."],
        non_implications=[],
        targets=[
            "Jacobian determinant",
            "etale torsor",
            "generic degree",
            "divisor class group",
        ],
        structured_scope={
            "base_field": "complex numbers for the geometric conclusions",
            "factor_degrees": "all positive r,s",
            "map": "binary-form product and resultant",
        },
        aliases=[
            "degree-difference principle",
            "binary-form product-resultant determinant theorem",
        ],
        problem_refs=[],
        sources=degree_sources,
        claim_provenance=degree_provenance,
        issued_at="2026-07-27T21:33:47+00:00",
    )
    degree_cubic = claim(
        natural=(
            "Let 0!=ell in V_3^*, let Gamma={[M^3]:[M] in P(V_1)} be "
            "the twisted cubic, let H_ell=P(ker ell), and let X_ell be the "
            "normalized linear-quadratic slice. Over C, X_ell is isomorphic "
            "to A^3 if and only if H_ell is tangent but not osculating to "
            "Gamma. More precisely, three distinct intersection points give "
            "X_ell not isomorphic to A^3 with class L^3-L; tangent "
            "nonosculating contact gives X_ell isomorphic to A^3 with class "
            "L^3; and osculating contact gives X_ell isomorphic to G_m x "
            "A^2 with class L^3-L^2. Equivalently, the successful "
            "functionals form the discriminant surface of binary cubics with "
            "the triple-root curve removed."
        ),
        latex=(
            r"\begin{gathered}"
            r"0\ne\ell\in V_3^\vee,\quad "
            r"\Gamma=\{[M^3]:[M]\in\mathbb P(V_1)\},\quad "
            r"\mathcal H_\ell=\mathbb P(\ker\ell),\\"
            r"X_\ell\simeq\mathbb A^3\Longleftrightarrow "
            r"\mathcal H_\ell\text{ is tangent but not osculating to }\Gamma,\\"
            r"(1,1,1):\ [X_\ell]=\mathbb L^3-\mathbb L,\ "
            r"X_\ell\not\simeq\mathbb A^3;\qquad "
            r"(2,1):\ X_\ell\simeq\mathbb A^3,\ "
            r"[X_\ell]=\mathbb L^3;\\"
            r"(3):\ X_\ell\simeq\mathbb G_m\times\mathbb A^2,\ "
            r"[X_\ell]=\mathbb L^3-\mathbb L^2."
            r"\end{gathered}"
        ),
        definitions=[
            ("Gamma", "The twisted cubic of pure cubes in P(V_3)."),
            ("H_ell", "The projective hyperplane P(ker ell)."),
            (
                "X_ell",
                "The normalized linear-quadratic slice with resultant and ell(AB) both equal to one.",
            ),
        ],
        quantifiers=["for every nonzero ell in V_3^*"],
        claim_kind="full-result",
        conditions=["The classification is over the complex numbers."],
        exclusions=["No classification of higher-degree slices is included."],
        non_implications=[],
        targets=["complete cubic contact-orbit classification"],
        structured_scope={
            "base_field": "complex numbers",
            "factor_degrees": "(1,2)",
            "contact_types": "(1,1,1), (2,1), (3)",
        },
        aliases=[
            "complete cubic classification",
            "linear-quadratic affine-slice trichotomy",
        ],
        problem_refs=[],
        sources=degree_sources,
        claim_provenance=degree_provenance,
        issued_at="2026-07-27T21:33:47+00:00",
    )
    degree_theorem_evidence = external_evidence(
        subject=degree_theorem,
        issuer_id="repository:ipitchford/degree-difference-affine-slices",
        issuer_name="ipitchford/degree-difference-affine-slices",
        locator="https://doi.org/10.5281/zenodo.21647593",
        digest=degree_digest,
        name="degree-difference-affine-slices.zip",
        coverage=[
            "candidate manuscript proof of the full degree-difference theorem",
            "exact finite symbolic checks of the determinant identity",
            "normal and optimized local replay with a negative control",
        ],
        limitations=[
            "The all-degree theorem rests on the manuscript proof, not the finite symbolic checks.",
            "The torsor, generic-degree, and class-group arguments are not encoded by the checker.",
            "No independent external reproduction, human review, peer review, or formalisation is documented.",
        ],
        replay_command="make PYTHON=.venv/bin/python verify",
        expected_outputs=[
            "normal and optimized transcripts match verifier_output.txt",
            "the deliberately wrong determinant expectation fails",
        ],
        rights="CC0-1.0 for original repository content to the extent held; source exclusions apply.",
    )
    degree_cubic_evidence = external_evidence(
        subject=degree_cubic,
        issuer_id="repository:ipitchford/degree-difference-affine-slices",
        issuer_name="ipitchford/degree-difference-affine-slices",
        locator="https://doi.org/10.5281/zenodo.21647593",
        digest=degree_digest,
        name="degree-difference-affine-slices.zip",
        coverage=[
            "candidate manuscript proof of the cubic classification",
            "exact checks of the tangent affine parametrisation and explicit map",
        ],
        limitations=[
            "The checker does not encode the orbit classification, motivic calculations, or affine-bundle arguments.",
            "No independent external reproduction, human review, peer review, or formalisation is documented.",
        ],
        replay_command="make PYTHON=.venv/bin/python verify",
        expected_outputs=[
            "normal and optimized transcripts match verifier_output.txt",
            "the deliberately wrong determinant expectation fails",
        ],
        rights="CC0-1.0 for original repository content to the extent held; source exclusions apply.",
    )
    degree_passing = {
        "provenance-quality",
        "reproducibility",
        "statement-precision",
        "version-stability",
    }
    degree_theorem_vector = status_vector(
        degree_theorem,
        degree_theorem_evidence,
        issuer_id="repository:ipitchford/degree-difference-affine-slices",
        issuer_name="ipitchford/degree-difference-affine-slices",
        passing=degree_passing,
        notes={
            "formal-or-certificate-verification": (
                "Only finite instances of the determinant identity are checked; "
                "the full theorem is not formally or certificate verified."
            ),
            "independent-reproduction": "No independent external reproduction is documented.",
            "novelty-audit": "No exhaustive novelty or priority determination was performed.",
            "proof-completeness": "Proof completeness is repository-claimed in an unrefereed manuscript.",
            "semantic-scope-match": "The checker covers selected formulas rather than the complete geometric theorem.",
        },
    )
    degree_cubic_vector = status_vector(
        degree_cubic,
        degree_cubic_evidence,
        issuer_id="repository:ipitchford/degree-difference-affine-slices",
        issuer_name="ipitchford/degree-difference-affine-slices",
        passing=degree_passing,
        notes={
            "formal-or-certificate-verification": "The cubic classification is not formally or certificate verified.",
            "independent-reproduction": "No independent external reproduction is documented.",
            "novelty-audit": "No exhaustive novelty or priority determination was performed.",
            "proof-completeness": "Proof completeness is repository-claimed in an unrefereed manuscript.",
            "semantic-scope-match": "Executable checks cover formulas surrounding only one contact orbit.",
        },
    )
    degree_records = (
        [degree_theorem, degree_theorem_evidence]
        + degree_theorem_vector
        + [degree_cubic, degree_cubic_evidence]
        + degree_cubic_vector
    )
    write_pack(
        examples / "degree-difference-affine-slices",
        records=degree_records,
        created_at=CREATED,
        primary_claim_record_id=degree_theorem["record_id"],
    )

    exotic_actors = [
        actor("human:ian-pitchford", "Ian Pitchford", "human"),
        actor(
            "organization:openai-codex-anthropic-models",
            "OpenAI Codex / Anthropic models",
            "organization",
        ),
        actor("software:openai-codex", "OpenAI Codex", "software"),
    ]
    exotic_provenance = provenance(
        exotic_actors,
        [
            (
                "organization:openai-codex-anthropic-models",
                "repository-reported manuscript attribution",
                "2026-07-28T00:00:00+00:00",
            ),
            (
                "human:ian-pitchford",
                "research direction, mediation, maintenance, and publication",
                "2026-07-28T00:00:00+00:00",
            ),
            ("software:openai-codex", "ClaimPack encoding", CREATED),
        ],
    )
    exotic_repo = (
        "https://github.com/ipitchford/exotic-affine-spheres-quadratic-cubic"
    )
    exotic_commit = "e786cec53c6ea34142ff775f9ab30dd00d960770"
    exotic_digest = (
        "sha256:de92abd2033cf65a2412cb070edd388ae2c3fd0d85a08660954d45408343d737"
    )
    exotic_sources = [
        source(
            kind="doi-version",
            locator="https://doi.org/10.5281/zenodo.21653108",
            immutable=True,
            version="0.1.1",
            digest=exotic_digest,
            rights=(
                "Repository original content is CC0-1.0 to the extent held; "
                "third-party material and the thread snapshot are excluded."
            ),
        ),
        source(
            kind="git-commit",
            locator=f"{exotic_repo}/commit/{exotic_commit}",
            immutable=True,
            version=exotic_commit,
            rights=(
                "Repository original content is CC0-1.0 to the extent held; "
                "third-party material and the thread snapshot are excluded."
            ),
        ),
    ]
    dubouloz_finston_source = source(
        kind="doi-version",
        locator="https://doi.org/10.1090/S1056-3911-2014-00612-3",
        immutable=True,
        version="2015",
        rights="Third-party cited source; not relicensed by ClaimPack.",
    )
    peters_steenbrink_source = source(
        kind="doi-version",
        locator="https://doi.org/10.1007/978-3-540-77017-6",
        immutable=True,
        version="2008",
        rights="Third-party cited source; not relicensed by ClaimPack.",
    )
    exotic_transverse = claim(
        natural=(
            "Every transverse normalized linear-quadratic slice is "
            "isomorphic to X(4,4,-a^3+a^2b^2-b^3), the nontrivial "
            "G_a-bundle over A^2 minus {0} represented by the Cech cocycle "
            "-1/(ab^4)+1/(a^2b^2)-1/(a^4b). Its total space is an exotic "
            "affine three-sphere and is not algebraically isomorphic to "
            "SL_2(C)."
        ),
        latex=(
            r"\begin{gathered}"
            r"X_{\mathrm{transverse}}\simeq "
            r"X(4,4,-a^3+a^2b^2-b^3),\\"
            r"[t]=-{1\over ab^4}+{1\over a^2b^2}-{1\over a^4b}"
            r"\in H^1(\mathbb A^2\setminus\{0\},\mathcal O),\\"
            r"X_{\mathrm{transverse}}\not\simeq\operatorname{SL}_2(\mathbb C)."
            r"\end{gathered}"
        ),
        definitions=[
            (
                "transverse normalized linear-quadratic slice",
                "The (1,2) normalized slice attached to a cubic hyperplane meeting the twisted cubic in three distinct points.",
            ),
            (
                "X(m,n,p)",
                "The Dubouloz-Finston normal form for the indicated principal additive bundle over the punctured affine plane.",
            ),
        ],
        quantifiers=["for every transverse normalized linear-quadratic slice"],
        claim_kind="full-result",
        conditions=["The algebraic non-isomorphism conclusion is over the complex numbers."],
        exclusions=["Tangent and osculating contact types are not classified by this theorem."],
        non_implications=[],
        targets=["transverse slice isomorphism type", "exotic affine three-sphere"],
        structured_scope={
            "base_field": "complex numbers",
            "factor_degrees": "(1,2)",
            "contact_type": "three distinct points",
        },
        aliases=[
            "transverse exotic affine three-sphere",
            "X(4,4,-a^3+a^2b^2-b^3)",
        ],
        problem_refs=[],
        sources=exotic_sources + [dubouloz_finston_source],
        claim_provenance=exotic_provenance,
        dependency_targets=[
            {"record_id": degree_cubic["record_id"], "record_type": "claim-version"}
        ],
        claim_version="0.1.1",
        issued_at="2026-07-28T19:26:41+00:00",
    )
    exotic_universal = claim(
        natural=(
            "For every nonzero ell in V_5^*, the normalized quadratic-cubic "
            "slice X_ell^{2,3} is not isomorphic to A^5. More precisely, if "
            "L=[A^1] and the reduced degeneracy loci K,D_2,D_1,Z are those "
            "defined in the manuscript, then [X_ell^{2,3}]=L^5-L^3-"
            "L^3[K]+L([D_2]-[D_1])+L^2[Z] in K_0(Var_C), and the compactly "
            "supported Hodge-Deligne polynomial of the right-hand side is "
            "never (uv)^5."
        ),
        latex=(
            r"\begin{gathered}"
            r"0\ne\ell\in V_5^\vee\Longrightarrow "
            r"X_\ell^{2,3}\not\simeq\mathbb A^5,\\"
            r"[X_\ell^{2,3}]=\mathbb L^5-\mathbb L^3-\mathbb L^3[K]"
            r"+\mathbb L([D_2]-[D_1])+\mathbb L^2[Z]"
            r"\quad\text{in }K_0(\operatorname{Var}_{\mathbb C}),\\"
            r"E_c(X_\ell^{2,3};u,v)\ne(uv)^5."
            r"\end{gathered}"
        ),
        definitions=[
            (
                "X_ell^{2,3}",
                "The pairs (A,B) of binary forms of degrees two and three satisfying Res(A,B)=1 and ell(AB)=1.",
            ),
            (
                "K,D_2,D_1,Z",
                "For C_ell:V_2 -> V_3^* given by A -> (B -> ell(AB)), "
                "K=P(ker C_ell) in P(V_2); D_2 is the set of [A] in "
                "P(V_2) with ell(A^2 V_1)=0; D_1 is the set of ([P],[Q]) "
                "in P(V_1)^2 with ell(P^2 Q^2 V_1)=0; and Z is the set "
                "of ([P],[Q]) in P(V_1)^2 with ell(P^2 Q V_2)=0. The "
                "loci have their reduced projective structures, and each "
                "displayed vanishing means that ell vanishes on the whole "
                "indicated subspace.",
            ),
        ],
        quantifiers=["for every nonzero ell in V_5^*"],
        claim_kind="full-result",
        conditions=["The Grothendieck-class and Hodge-Deligne conclusions are over the complex numbers."],
        exclusions=["No assertion is made for the proposed (3,4) or general adjacent-degree extension."],
        non_implications=[],
        targets=["all quadratic-cubic normalized slices"],
        structured_scope={
            "base_field": "complex numbers",
            "factor_degrees": "(2,3)",
            "functionals": "all nonzero ell in V_5^*",
        },
        aliases=[
            "universal quadratic-cubic exclusion",
            "no normalized quadratic-cubic slice is affine five-space",
        ],
        problem_refs=[],
        sources=exotic_sources + [peters_steenbrink_source],
        claim_provenance=exotic_provenance,
        claim_version="0.1.1",
        issued_at="2026-07-28T19:26:41+00:00",
    )
    exotic_transverse_evidence = external_evidence(
        subject=exotic_transverse,
        issuer_id="repository:ipitchford/exotic-affine-spheres-quadratic-cubic",
        issuer_name="ipitchford/exotic-affine-spheres-quadratic-cubic",
        locator="https://doi.org/10.5281/zenodo.21653108",
        digest=exotic_digest,
        name="exotic-affine-spheres-quadratic-cubic-0.1.1.zip",
        coverage=[
            "candidate manuscript proof of the transverse identification",
            "exact checks of local sections, fibre direction, transition function, and reduced Cech class",
            "citation-robustness snapshot and release replay",
        ],
        limitations=[
            "The script checks displayed algebra but does not formalise torsor descent.",
            "The decisive non-isomorphism criterion is imported from Dubouloz-Finston.",
            "The repository-reported model audit artifact is not included.",
            "No independent external reproduction, human review, peer review, or formalisation is documented.",
        ],
        replay_command="make PYTHON=.venv/bin/python verify",
        expected_outputs=[
            "verification transcript and generated CSV files match",
            "optimized execution fails closed and the ablation is rejected",
        ],
        rights="CC0-1.0 for original repository content to the extent held; source exclusions apply.",
    )
    exotic_universal_evidence = external_evidence(
        subject=exotic_universal,
        issuer_id="repository:ipitchford/exotic-affine-spheres-quadratic-cubic",
        issuer_name="ipitchford/exotic-affine-spheres-quadratic-cubic",
        locator="https://doi.org/10.5281/zenodo.21653108",
        digest=exotic_digest,
        name="exotic-affine-spheres-quadratic-cubic-0.1.1.zip",
        coverage=[
            "candidate manuscript class-stratification and Hodge-Deligne proof",
            "finite-field realization for the stated fields",
            "generated-table comparison, fixtures, and point-count ablation",
        ],
        limitations=[
            "Finite-field censuses do not prove the complex Grothendieck-ring identity.",
            "The verifier does not encode mixed Hodge theory or the complete geometric stratification.",
            "The repository-reported model audit artifact is not included.",
            "No independent external reproduction, human review, peer review, or formalisation is documented.",
        ],
        replay_command="make PYTHON=.venv/bin/python verify",
        expected_outputs=[
            "verification transcript and generated CSV files match",
            "optimized execution fails closed and the ablation is rejected",
        ],
        rights="CC0-1.0 for original repository content to the extent held; source exclusions apply.",
    )
    exotic_passing = {
        "provenance-quality",
        "reproducibility",
        "statement-precision",
        "version-stability",
    }
    exotic_transverse_vector = status_vector(
        exotic_transverse,
        exotic_transverse_evidence,
        issuer_id="repository:ipitchford/exotic-affine-spheres-quadratic-cubic",
        issuer_name="ipitchford/exotic-affine-spheres-quadratic-cubic",
        passing=exotic_passing,
        notes={
            "formal-or-certificate-verification": "The transverse theorem is not formally or certificate verified.",
            "independent-reproduction": "No independent external reproduction is documented.",
            "novelty-audit": "No complete novelty determination was performed.",
            "proof-completeness": "Proof completeness is repository-claimed in an unrefereed manuscript.",
            "semantic-scope-match": "The exact algebraic checks do not formalise the imported non-isomorphism criterion.",
        },
    )
    exotic_universal_vector = status_vector(
        exotic_universal,
        exotic_universal_evidence,
        issuer_id="repository:ipitchford/exotic-affine-spheres-quadratic-cubic",
        issuer_name="ipitchford/exotic-affine-spheres-quadratic-cubic",
        passing=exotic_passing,
        notes={
            "formal-or-certificate-verification": "The universal exclusion is not formally or certificate verified.",
            "independent-reproduction": "No independent external reproduction is documented.",
            "novelty-audit": "No complete novelty determination was performed.",
            "proof-completeness": "Proof completeness is repository-claimed in an unrefereed manuscript.",
            "semantic-scope-match": "Finite-field checks do not establish the all-functional complex theorem.",
        },
    )
    exotic_degree_relation = depends_on(
        exotic_transverse,
        degree_cubic,
        issuer_id="repository:ipitchford/exotic-affine-spheres-quadratic-cubic",
        issuer_name="ipitchford/exotic-affine-spheres-quadratic-cubic",
        limitation=(
            "The source imports the pinned cubic contact-orbit classification; "
            "this seed does not independently establish that correspondence."
        ),
    )
    exotic_records = (
        [degree_cubic, degree_cubic_evidence]
        + degree_cubic_vector
        + [
            exotic_transverse,
            exotic_degree_relation,
            relation_status(
                exotic_degree_relation,
                issuer_id="repository:ipitchford/exotic-affine-spheres-quadratic-cubic",
                issuer_name="ipitchford/exotic-affine-spheres-quadratic-cubic",
            ),
            exotic_transverse_evidence,
        ]
        + exotic_transverse_vector
        + [exotic_universal, exotic_universal_evidence]
        + exotic_universal_vector
    )
    write_pack(
        examples / "exotic-affine-spheres-quadratic-cubic",
        records=exotic_records,
        created_at=CREATED,
        primary_claim_record_id=exotic_universal["record_id"],
    )

    reducible_actors = [
        actor("human:ian-pitchford", "Ian Pitchford", "human"),
        actor(
            "ai:openai-codex-5.6-sol",
            "OpenAI Codex 5.6 Sol",
            "ai-system",
            model_family="Codex 5.6 Sol",
            model_provider="OpenAI",
        ),
        actor(
            "ai:anthropic-fable-5",
            "Anthropic Fable 5",
            "ai-system",
            model_family="Fable 5",
            model_provider="Anthropic",
        ),
        actor("software:openai-codex", "OpenAI Codex", "software"),
    ]
    reducible_provenance = provenance(
        reducible_actors,
        [
            (
                "ai:openai-codex-5.6-sol",
                "repository-reported proof, verification, and synthesis",
                "2026-07-28T00:00:00+00:00",
            ),
            (
                "ai:anthropic-fable-5",
                "repository-reported research route and model-led audit",
                "2026-07-28T00:00:00+00:00",
            ),
            (
                "human:ian-pitchford",
                "research direction, mediation, maintenance, and publication",
                "2026-07-28T00:00:00+00:00",
            ),
            ("software:openai-codex", "ClaimPack encoding", CREATED),
        ],
    )
    reducible_repo = (
        "https://github.com/ipitchford/"
        "reducible-incidence-divisors-affine-slices"
    )
    reducible_commit = "5b01190b37d5a8c43073a0eb5f1e5c94c65864ad"
    reducible_digest = (
        "sha256:b733f4db720495fc9654e83a45fc7d77edc9a72a225b919e436cdf2ce924fbc9"
    )
    reducible_sources = [
        source(
            kind="doi-version",
            locator="https://doi.org/10.5281/zenodo.21653119",
            immutable=True,
            version="1.0.1",
            digest=reducible_digest,
            rights=(
                "Repository original content is CC0-1.0 to the extent held; "
                "third-party sources, audit inputs, and the thread snapshot "
                "retain their own rights."
            ),
        ),
        source(
            kind="git-commit",
            locator=f"{reducible_repo}/commit/{reducible_commit}",
            immutable=True,
            version=reducible_commit,
            rights=(
                "Repository original content is CC0-1.0 to the extent held; "
                "third-party sources, audit inputs, and the thread snapshot "
                "retain their own rights."
            ),
        ),
    ]
    reducibility_literature_sources = [
        source(
            kind="doi-version",
            locator="https://doi.org/10.4310/MRL.2013.v20.n4.a10",
            immutable=True,
            version="2013",
            rights="Third-party cited source; not relicensed by ClaimPack.",
        ),
        source(
            kind="doi-version",
            locator="https://doi.org/10.1016/j.jsc.2010.08.001",
            immutable=True,
            version="2011",
            rights="Third-party cited source; not relicensed by ClaimPack.",
        ),
    ]
    hodge_source = source(
        kind="doi-version",
        locator="https://doi.org/10.1007/978-3-540-77017-6",
        immutable=True,
        version="2008",
        rights="Third-party cited source; not relicensed by ClaimPack.",
    )
    reducibility_claim = claim(
        natural=(
            "Let m>=2 and 0!=ell in V_{2m+1}^*. The marked-common-root "
            "divisor D_ell is reducible set-theoretically if and only if "
            "[ell] lies in the tangent developable of the rational normal "
            "curve nu_{2m+1}. More precisely: an evaluation functional gives "
            "three reduced irreducible components; a functional on a "
            "punctured tangent line gives exactly two; a genuine two-point "
            "secant functional gives an irreducible divisor; and every "
            "functional with middle-catalecticant rank at least three gives "
            "an irreducible divisor."
        ),
        latex=(
            r"\begin{gathered}"
            r"m\ge2,\quad0\ne\ell\in V_{2m+1}^\vee,\\"
            r"D_\ell\text{ reducible}\Longleftrightarrow "
            r"[\ell]\in\tau(\nu_{2m+1}),\\"
            r"\ell=\lambda\operatorname{ev}_u\Rightarrow "
            r"\#\operatorname{Irr}(D_\ell{}_{\mathrm{red}})=3,\\"
            r"[\ell]\in\tau(\nu_{2m+1})\setminus\nu_{2m+1}"
            r"\Rightarrow\#\operatorname{Irr}(D_\ell{}_{\mathrm{red}})=2,\\"
            r"\ell=a\operatorname{ev}_u+b\operatorname{ev}_v,\ u\ne v,\ ab\ne0"
            r"\Rightarrow D_\ell\text{ irreducible},\\"
            r"\operatorname{rank}C_\ell\ge3\Rightarrow "
            r"D_\ell\text{ irreducible}."
            r"\end{gathered}"
        ),
        definitions=[
            (
                "D_ell",
                "The divisor ell(P^2 A' B')=0 on P(V_1) x P(V_{m-1}) x P(V_m).",
            ),
            (
                "nu_{2m+1}",
                "The rational normal curve of projective evaluation functionals in P(V_{2m+1}^*).",
            ),
            (
                "C_ell",
                "The middle catalecticant A maps to the functional B maps to ell(AB).",
            ),
        ],
        quantifiers=[
            "for every integer m >= 2",
            "for every nonzero ell in V_{2m+1}^*",
        ],
        claim_kind="stronger-result",
        conditions=[
            "Reducibility is set-theoretic and component counts use reduced structures.",
            "The theorem is over the complex numbers.",
        ],
        exclusions=["Positive-characteristic analogues are outside the theorem."],
        non_implications=[],
        targets=["marked-common-root incidence divisor", "tangent developable"],
        structured_scope={
            "base_field": "complex numbers",
            "degrees": "(m,m+1), m>=2",
            "reducibility_locus": "tangent developable of nu_{2m+1}",
        },
        aliases=[
            "reducibility classification",
            "marked-common-root incidence divisor theorem",
        ],
        problem_refs=[],
        sources=reducible_sources + reducibility_literature_sources,
        claim_provenance=reducible_provenance,
        claim_version="1.0.1",
        issued_at="2026-07-28T19:26:41+00:00",
        rights_exclusions=["The cited classical literature remains third-party material."],
    )
    adjacent_hodge = claim(
        natural=(
            "Let m>=2, 0!=ell in V_{2m+1}^*, and rho=rank C_ell. Then "
            "E_c(X_ell^{m,m+1};u,v)!=(uv)^{2m+1}. More precisely, for "
            "rho=1 the polynomial is (uv)^{2m+1}-(uv)^{2m}; for "
            "catalecticant rank two of two-point secant type the coefficient "
            "of u^{2m-1}v^{2m-1} is -2; for rank two of first-jet type it is "
            "-1; and for rho>=3 it is -1. Consequently X_ell^{m,m+1} is not "
            "isomorphic to A^{2m+1} for every such m and ell."
        ),
        latex=(
            r"\begin{gathered}"
            r"m\ge2,\quad0\ne\ell\in V_{2m+1}^\vee,\quad"
            r"\rho=\operatorname{rank}C_\ell,\\"
            r"E_c(X_\ell^{m,m+1};u,v)\ne(uv)^{2m+1},\\"
            r"\rho=1:\ E_c=(uv)^{2m+1}-(uv)^{2m};\\"
            r"\rho=2\text{ secant}:\ [u^{2m-1}v^{2m-1}]E_c=-2;\quad"
            r"\rho=2\text{ first jet}:\ [u^{2m-1}v^{2m-1}]E_c=-1;\\"
            r"\rho\ge3:\ [u^{2m-1}v^{2m-1}]E_c=-1;\\"
            r"X_\ell^{m,m+1}\not\simeq\mathbb A^{2m+1}."
            r"\end{gathered}"
        ),
        definitions=[
            (
                "X_ell^{m,m+1}",
                "The normalized slice Res(A,B)=1 and ell(AB)=1 for binary forms of degrees m and m+1.",
            ),
            ("E_c", "The compactly supported Hodge-Deligne polynomial."),
            (
                "C_ell",
                "The middle catalecticant A maps to the functional B maps to ell(AB).",
            ),
        ],
        quantifiers=[
            "for every integer m >= 2",
            "for every nonzero ell in V_{2m+1}^*",
        ],
        claim_kind="stronger-result",
        conditions=["The Hodge-Deligne conclusion is over the complex numbers."],
        exclusions=["The exceptional boundary m=1 is not included."],
        non_implications=[],
        targets=["all higher adjacent normalized slices"],
        structured_scope={
            "base_field": "complex numbers",
            "degrees": "(m,m+1), m>=2",
            "functionals": "all nonzero ell",
        },
        aliases=[
            "adjacent Hodge defects",
            "universal adjacent-degree exclusion",
        ],
        problem_refs=[],
        sources=reducible_sources + [hodge_source],
        claim_provenance=reducible_provenance,
        dependency_targets=[
            {
                "record_id": reducibility_claim["record_id"],
                "record_type": "claim-version",
            }
        ],
        claim_version="1.0.1",
        issued_at="2026-07-28T19:26:41+00:00",
        rights_exclusions=["The cited Hodge-theory source remains third-party material."],
    )
    conditional_isolation = claim(
        natural=(
            "Let r,s>=1 and 0!=ell in V_{r+s}^*. If |r-s|>=2, then "
            "X_ell^{r,s}(C) is not contractible. If {r,s}={m,m+1} with "
            "m>=2, then X_ell^{r,s} is not isomorphic to A^{2m+1}. If r=s, "
            "relative scaling gives positive-dimensional fibres and the "
            "multiplication-resultant architecture cannot yield a Keller "
            "map. Conditional on the complete cubic classification in the "
            "pinned unrefereed degree-difference candidate, the tangent "
            "nonosculating (1,2) slice and its swapped form are the unique "
            "positive-bidegree normalized affine-space sources in this "
            "architecture that carry a nonzero constant Jacobian determinant."
        ),
        latex=(
            r"\begin{gathered}"
            r"r,s\ge1,\quad0\ne\ell\in V_{r+s}^\vee,\\"
            r"|r-s|\ge2\Rightarrow X_\ell^{r,s}(\mathbb C)"
            r"\text{ is not contractible},\\"
            r"\{r,s\}=\{m,m+1\},\ m\ge2\Rightarrow "
            r"X_\ell^{r,s}\not\simeq\mathbb A^{2m+1},\\"
            r"r=s\Rightarrow\text{positive-dimensional relative-scaling fibres},\\"
            r"\text{conditional on the pinned complete cubic classification: }"
            r"(1,2)_{\mathrm{tangent}}\text{ and }(2,1)_{\mathrm{tangent}}"
            r"\text{ are the unique normalized affine-space sources in the scoped architecture}"
            r"\text{ with nonzero constant Jacobian determinant}."
            r"\end{gathered}"
        ),
        definitions=[
            (
                "X_ell^{r,s}",
                "The normalized binary-form slice Res(A,B)=1 and ell(AB)=1.",
            ),
            (
                "this architecture",
                "The untrimmed positive-degree two-factor binary-form spaces, product-resultant map, and normalized linear slices defined in the source.",
            ),
        ],
        quantifiers=[
            "for every pair of integers r,s >= 1",
            "for every nonzero ell in V_{r+s}^*",
        ],
        claim_kind="conditional-result",
        conditions=[
            "The final uniqueness conclusion assumes the pinned complete cubic classification.",
            "The theorem is over the complex numbers.",
        ],
        exclusions=[
            "Trimmed, nonlinear, quotient, multifactor, degree-zero, and positive-characteristic variants are outside the scoped architecture."
        ],
        non_implications=[],
        targets=["complete positive two-factor affine-slice isolation"],
        structured_scope={
            "base_field": "complex numbers",
            "architecture": "untrimmed positive-degree binary two-factor normalization",
            "conditional_case": "complete cubic classification",
        },
        aliases=[
            "conditional complete two-factor isolation",
            "binary-factorisation affine-slice isolation",
        ],
        problem_refs=[],
        sources=reducible_sources,
        claim_provenance=reducible_provenance,
        dependency_targets=[
            {
                "record_id": adjacent_hodge["record_id"],
                "record_type": "claim-version",
            },
            {
                "record_id": degree_theorem["record_id"],
                "record_type": "claim-version",
            },
            {
                "record_id": degree_cubic["record_id"],
                "record_type": "claim-version",
            },
        ],
        claim_version="1.0.1",
        issued_at="2026-07-28T19:26:41+00:00",
    )
    reducibility_evidence = external_evidence(
        subject=reducibility_claim,
        issuer_id="repository:ipitchford/reducible-incidence-divisors-affine-slices",
        issuer_name="ipitchford/reducible-incidence-divisors-affine-slices",
        locator="https://doi.org/10.5281/zenodo.21653119",
        digest=reducible_digest,
        name="reducible-incidence-divisors-affine-slices-1.0.1.zip",
        coverage=[
            "candidate manuscript incidence-divisor proof",
            "bounded exact Hankel and rank-two falsification tests",
            "model-led audit and low-catalecticant supplement",
        ],
        limitations=[
            "The bounded checkers do not prove complex irreducibility or secant exhaustion.",
            "The cited classical rank-two inputs are not independently verified by this seed.",
            "The model-led audit is repository-reported and not independent external review.",
            "No independent expert human review, peer review, or formalisation is documented.",
        ],
        replay_command=(
            "make PYTHON=.venv/bin/python "
            "CFFCONVERT=.venv/bin/cffconvert release-replay"
        ),
        expected_outputs=[
            "manifest inventory matches before and after replay",
            "normal, optimized, and semantic-control outputs match",
        ],
        rights="CC0-1.0 for original repository content to the extent held; source exclusions apply.",
    )
    adjacent_hodge_evidence = external_evidence(
        subject=adjacent_hodge,
        issuer_id="repository:ipitchford/reducible-incidence-divisors-affine-slices",
        issuer_name="ipitchford/reducible-incidence-divisors-affine-slices",
        locator="https://doi.org/10.5281/zenodo.21653119",
        digest=reducible_digest,
        name="reducible-incidence-divisors-affine-slices-1.0.1.zip",
        coverage=[
            "candidate manuscript Hodge-Deligne proof",
            "exact diagnostic-coefficient bookkeeping",
            "8,653-functional finite-field census and positive and negative controls",
        ],
        limitations=[
            "Finite-field counts do not prove the complex theorem.",
            "The code does not formalise mixed Hodge theory or the component-count bridge.",
            "The model-led audit is repository-reported and not independent external review.",
            "No independent expert human review, peer review, or formalisation is documented.",
        ],
        replay_command=(
            "make PYTHON=.venv/bin/python "
            "CFFCONVERT=.venv/bin/cffconvert release-replay"
        ),
        expected_outputs=[
            "manifest inventory matches before and after replay",
            "normal, optimized, and semantic-control outputs match",
        ],
        rights="CC0-1.0 for original repository content to the extent held; source exclusions apply.",
    )
    isolation_evidence = external_evidence(
        subject=conditional_isolation,
        issuer_id="repository:ipitchford/reducible-incidence-divisors-affine-slices",
        issuer_name="ipitchford/reducible-incidence-divisors-affine-slices",
        locator="https://doi.org/10.5281/zenodo.21653119",
        digest=reducible_digest,
        name="reducible-incidence-divisors-affine-slices-1.0.1.zip",
        coverage=[
            "candidate manuscript synthesis across the three degree-difference regimes",
            "exact references to the pinned upstream ClaimVersions",
        ],
        limitations=[
            "The uniqueness conclusion is explicitly conditional on the pinned cubic classification.",
            "The deterministic checkers do not directly encode the isolation theorem.",
            "No independent expert human review, peer review, or formalisation is documented.",
        ],
        replay_command=(
            "make PYTHON=.venv/bin/python "
            "CFFCONVERT=.venv/bin/cffconvert release-replay"
        ),
        expected_outputs=[
            "manifest inventory matches before and after replay",
            "normal, optimized, and semantic-control outputs match",
        ],
        rights="CC0-1.0 for original repository content to the extent held; source exclusions apply.",
    )
    reducible_passing = {
        "provenance-quality",
        "reproducibility",
        "statement-precision",
        "version-stability",
    }
    reducibility_vector = status_vector(
        reducibility_claim,
        reducibility_evidence,
        issuer_id="repository:ipitchford/reducible-incidence-divisors-affine-slices",
        issuer_name="ipitchford/reducible-incidence-divisors-affine-slices",
        passing=reducible_passing,
        notes={
            "formal-or-certificate-verification": "The geometric classification is not formally or certificate verified.",
            "independent-reproduction": "No independent external reproduction is documented.",
            "novelty-audit": "No literature-wide novelty or priority determination was performed.",
            "proof-completeness": "Proof completeness is repository-claimed in an unrefereed manuscript.",
            "semantic-scope-match": "Bounded exact tests do not establish the complex irreducibility theorem.",
        },
    )
    adjacent_hodge_vector = status_vector(
        adjacent_hodge,
        adjacent_hodge_evidence,
        issuer_id="repository:ipitchford/reducible-incidence-divisors-affine-slices",
        issuer_name="ipitchford/reducible-incidence-divisors-affine-slices",
        passing=reducible_passing,
        notes={
            "formal-or-certificate-verification": "The Hodge-Deligne theorem is not formally or certificate verified.",
            "independent-reproduction": "No independent external reproduction is documented.",
            "novelty-audit": "No literature-wide novelty or priority determination was performed.",
            "proof-completeness": "Proof completeness is repository-claimed in an unrefereed manuscript.",
            "semantic-scope-match": "The census checks consequences rather than the all-degree complex theorem.",
        },
    )
    isolation_vector = status_vector(
        conditional_isolation,
        isolation_evidence,
        issuer_id="repository:ipitchford/reducible-incidence-divisors-affine-slices",
        issuer_name="ipitchford/reducible-incidence-divisors-affine-slices",
        passing=reducible_passing,
        notes={
            "dependency-closure": "The conclusion retains explicit unrefereed upstream dependencies.",
            "formal-or-certificate-verification": "The conditional isolation theorem is not formally or certificate verified.",
            "independent-reproduction": "No independent external reproduction is documented.",
            "novelty-audit": "No literature-wide novelty or priority determination was performed.",
            "proof-completeness": "Proof completeness is repository-claimed and dependency-conditioned.",
            "semantic-scope-match": "The complete synthesis and upstream correspondence have not been independently audited.",
        },
    )
    adjacent_reducibility_relation = depends_on(
        adjacent_hodge,
        reducibility_claim,
        issuer_id="repository:ipitchford/reducible-incidence-divisors-affine-slices",
        issuer_name="ipitchford/reducible-incidence-divisors-affine-slices",
        limitation=(
            "The Hodge diagnostic uses the repository-reported component counts "
            "from the reducibility classification."
        ),
    )
    isolation_dependencies = [
        (
            adjacent_hodge,
            "The adjacent-degree branch imports the exact Hodge-defect theorem proved in the same manuscript.",
        ),
        (
            degree_theorem,
            "The isolation conclusion imports the pinned determinant and degree-difference framework.",
        ),
        (
            degree_cubic,
            "The final uniqueness clause is explicitly conditional on the pinned complete cubic classification.",
        ),
    ]
    isolation_relations = [
        depends_on(
            conditional_isolation,
            target,
            issuer_id="repository:ipitchford/reducible-incidence-divisors-affine-slices",
            issuer_name="ipitchford/reducible-incidence-divisors-affine-slices",
            limitation=limitation,
        )
        for target, limitation in isolation_dependencies
    ]
    reducible_records = (
        [degree_theorem, degree_theorem_evidence]
        + degree_theorem_vector
        + [degree_cubic, degree_cubic_evidence]
        + degree_cubic_vector
        + [reducibility_claim, reducibility_evidence]
        + reducibility_vector
        + [
            adjacent_hodge,
            adjacent_reducibility_relation,
            relation_status(
                adjacent_reducibility_relation,
                issuer_id="repository:ipitchford/reducible-incidence-divisors-affine-slices",
                issuer_name="ipitchford/reducible-incidence-divisors-affine-slices",
            ),
            adjacent_hodge_evidence,
        ]
        + adjacent_hodge_vector
        + [conditional_isolation, isolation_evidence]
        + isolation_vector
        + isolation_relations
        + [
            relation_status(
                relation,
                issuer_id="repository:ipitchford/reducible-incidence-divisors-affine-slices",
                issuer_name="ipitchford/reducible-incidence-divisors-affine-slices",
            )
            for relation in isolation_relations
        ]
    )
    write_pack(
        examples / "reducible-incidence-divisors-affine-slices",
        records=reducible_records,
        created_at=CREATED,
        primary_claim_record_id=adjacent_hodge["record_id"],
    )

    package_paths = [
        examples / "z20",
        examples / "vr2-k4",
        examples / "erdos848",
        examples / "degree-difference-affine-slices",
        examples / "exotic-affine-spheres-quadratic-cubic",
        examples / "reducible-incidence-divisors-affine-slices",
    ]
    catalog_entries: dict[str, dict[str, Any]] = {}
    for package_path in package_paths:
        pack = validate_pack(str(package_path))
        for item in pack.claims():
            entry = catalog_entries.setdefault(
                item["record_id"],
                {
                    "aliases": item["aliases"],
                    "assessment_record_ids": [],
                    "author_claimed_status": "source-reported status; inspect assessment overlays",
                    "canonical_status": "unassessed",
                    "claim_id": item["claim_id"],
                    "claim_kind": item["scope"]["claim_kind"],
                    "claim_record_id": item["record_id"],
                    "formal_verification_status": "source-reported only; inspect exact assessment records",
                    "human_review_status": "no independent human review documented by the seed",
                    "independent_reproduction_status": "none documented by the seed",
                    "latex": item["statement"]["latex"],
                    "natural": item["statement"]["natural"],
                    "novelty_status": "unassessed",
                    "objection_record_ids": [],
                    "packages": [],
                    "search_fingerprint": search_fingerprint(
                        item["statement"]["natural"]
                    ),
                    "sources": item["sources"],
                    "system_assessment": "not evaluated by the static catalog",
                    "status_updated_at": CREATED,
                },
            )
            entry["packages"].append(
                {
                    "package_root": pack.package_root,
                    "path": package_path.relative_to(root).as_posix(),
                    "primary": item is pack.primary_claim(),
                }
            )
            for record in pack.records.values():
                if (
                    record["record_type"] == "assessment"
                    and record["target"]["record_id"] == item["record_id"]
                ):
                    entry["assessment_record_ids"].append(record["record_id"])
                    if record["assessment_kind"] == "objection":
                        entry["objection_record_ids"].append(record["record_id"])
    for entry in catalog_entries.values():
        entry["assessment_record_ids"] = sorted(set(entry["assessment_record_ids"]))
        entry["objection_record_ids"] = sorted(set(entry["objection_record_ids"]))
    catalog: dict[str, Any] = {
        "catalog_head": "",
        "entries": [catalog_entries[key] for key in sorted(catalog_entries)],
        "generated_at": CREATED,
        "schema_version": "claimpack-static-catalog/0.1",
        "search_fingerprint_profile": "NFKC-casefold-whitespace/v0.1",
    }
    projection = dict(catalog)
    projection.pop("catalog_head")
    catalog["catalog_head"] = ni_sha256(canonical_bytes(projection))
    (catalog_dir / "catalog.json").write_bytes(pretty_bytes(catalog))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path.cwd())
    args = parser.parse_args()
    build(args.root.resolve())


if __name__ == "__main__":
    main()
