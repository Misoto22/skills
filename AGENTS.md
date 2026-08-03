# Repository guidance

- Keep all code identifiers, comments, documentation, and commit messages in English.
- Explore existing skills and tests before changing behavior.
- Only release-ready skills may live under `skills/`; use top-level `drafts/` for unfinished work and `deprecated/` for retired material.
- Every published skill requires `SKILL.md`, `agents/openai.yaml`, a registry entry, tests, and matching plugin metadata.
- Preserve organization neutrality: no personal identity, company domain, credentials, local absolute path, or provider-specific transport assumption in runtime content.
- Default ambiguous or incomplete outbound email intent to draft. Never weaken send authorization, disclosure, artifact-integrity, or readback gates.
- Use dependency-free Python for portable runtime validation unless a reviewed design explicitly justifies a dependency.
- Add tests before implementation and run `python3 scripts/validate-repository.py` before release.
- Do not force-push `main` or `master`.
