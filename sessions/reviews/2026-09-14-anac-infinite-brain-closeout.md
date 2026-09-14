---
session_id: "session-2026-09-14-anac-infinite-brain"
date: "2026-09-14"
topic: "anac-infinite-brain"
status: "closed"
---

# Closeout: anac infinite brain

## Outputs produced

- Namespace `knowledge/anac-legislacao/` (doctrine profile) plus ingest tools
  `tools/anac_ingest/ingest.py` and `query.py`.
- Catalog 56 RBAC, 232 IS, 18 IAC. Ingest 72 ok, 234 error, 14208 fragments,
  7747 keyword keys.
- Indexes in `knowledge/anac-legislacao/support/indexes/`.

## Decisions made

- The brain is this cloned OS, not a sidecar wiki.
- Corpus lives in `support/` (not canon). Grain is lettered subsection.
- Fetch uses Arquivo.pt only in this environment. CDX must encode `@@` and
  prefix-match the document folder. Ignore `anexo_norma` CEF files.

## Wrong turns

- Treating `rbha-e-rbac` as a document code (regex too loose).
- CDX prefix on `/arquivos/` pulled unrelated Pergamum PDFs.
- PDF bytes decoded as HTML when CDX returned a PDF for a page URL.

## Session usage and cost

Surface did not expose token or cost totals.

## Memory candidates

- Arquivo.pt CDX: quote special path chars; never prefix a generic PDF folder.

## Follow-up

- Re-ingest IS and IAC when live ANAC fetch works.
- Replace HTML stubs `rbac-27`, `rbac-29`, `rbac-38` with PDFs.

## Human review

- Do not promote fragments to canon without operator review.

## Unresolved

- 205 IS and all 18 IAC missing from Arquivo.pt.
- Some later RBAC emendas and `resolveuid` rows have no snapshot.
