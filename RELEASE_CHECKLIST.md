# Candidate release checklist

- [ ] `git diff --check` passes and the intended worktree is reviewed.
- [ ] `make verify` passes.
- [ ] `make verify-optimized` passes.
- [ ] Both Agent Skills pass `skills-ref==0.1.1` validation.
- [ ] `skills@1.5.21` discovers exactly two named skills.
- [ ] A clean wheel and source distribution build.
- [ ] The wheel installs in a fresh environment outside the repository.
- [ ] `CITATION.cff` validates.
- [ ] CC0 and third-party rights boundaries are present.
- [ ] Security reporting and supported-version language are present.
- [ ] Release notes retain the structural-validity and candidate boundaries.
- [ ] Generated seed packs and the catalogue match their generator bytewise.
- [ ] Public GitHub source, tag, release assets, checksums, and CI are read back.
- [ ] The public one-line skill installer discovers both skills.
- [ ] Research-repository seed commits are pushed and publicly readable.

Checking an item records an operational gate only; it does not certify any
scientific claim contained in a seed package.
