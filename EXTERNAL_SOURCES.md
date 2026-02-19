# External Skill Ingestion (Next Phase)

This is the phase-2/3 plan for listing external skills safely.

## Sources (metadata-first)

- MCP Registry (official)
- Curated GitHub repositories
- Optional secondary aggregators

## Policy

- Do not auto-install arbitrary external code.
- Ingest metadata first, then run curation checks.
- Tag each item with trust tier:
  - `official`
  - `verified`
  - `community`

## Required Checks Before Listing

- License present and compatible
- Source URL and owner provenance
- Last update recency
- Installability in Computer Agents runtime
- Security review for code-bearing templates

## Install Contract

All external skills must be normalized into internal custom-skill shape:

- `name`
- `description`
- `markdown`
- `codeFiles[]`
- `metadata.source`
- `metadata.version`

Then install through the same `/api/projects/:projectId/skills` route used by first-party and user-created custom skills.

## Imported Community Sources (2026-02-19)

Star counts are snapshots at import time.

- `coreyhaines31/marketingskills` (MIT, 8,313 stars):
  - Imported 8 skills
- `czlonkowski/n8n-skills` (MIT, 2,848 stars):
  - Imported 4 skills
- `Jeffallan/claude-skills` (MIT, 3,190 stars):
  - Imported 4 skills
- `PleasePrompto/notebooklm-skill` (MIT, 3,596 stars):
  - Imported 1 skill
- `lackeyjb/playwright-skill` (MIT, 1,717 stars):
  - Imported 1 skill

All imported skills include source attribution in `ATTRIBUTION.md` within each skill folder.
