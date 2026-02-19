# Computer Agents Skills Catalog

Canonical first-party skills catalog used by the marketplace/store.

## Goals

- Keep first-party skills in a stable, GitHub-friendly structure.
- Make every skill auditable and versioned.
- Allow downstream marketplaces and importers to consume a single source of truth.

## Structure

- `index.json`: catalog index of all listed skills.
- `schema/skill-manifest.schema.json`: JSON schema for skill manifests.
- `skills/<slug>/manifest.json`: metadata and install contract.
- `skills/<slug>/skill.md`: prompt/instructions content.
- `skills/<slug>/code/*`: code files shipped with the skill.

## Validation

Run locally:

```bash
pnpm skills:validate
```

This validates:

- index entries point to existing manifests
- required manifest fields exist and match schema shape
- `skill.md` exists
- all listed code files exist

## Publish Workflow

1. Update skill content in marketplace/runtime.
2. Mirror the update in this catalog (manifest + skill.md + code).
3. Run `pnpm skills:validate`.
4. Commit and push to GitHub.
5. Tag release when needed.
