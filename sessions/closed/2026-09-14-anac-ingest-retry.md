---
session_id: "session-2026-09-14-anac-ingest-retry"
date: "2026-09-14"
topic: "anac-ingest-retry"
status: "closed"
surface: "opencode"
operator: "the-operator"
namespace: "anac-legislacao"
goal: "Recover missing ANAC RBAC/IS/IAC snapshots and repair the fragment index."
transcript_paths:
  - "sessions/logs/2026-09-14-anac-ingest-retry.log.md"
---

# Session: anac ingest retry

Second pass on the ANAC corpus: recover dead documents, fix fragment counting,
and pull the CFR annexes shipped inside RBAC 27 and 29.

## Running notes

- Added attachment rejection in CDX pick and page PDF ranking.
- Recovered `rbac-129`, `rbac-23`, `rbac-031`, `rbac-035`.
- Refragmented 51 docs, quarantined 60 dead artifacts, deduped fragment ids.
- Ingested `rbac-27` and `rbac-29` as labeled `foreign_annex` English text.
- `--only=<codes>` flag fixed; live mode (`ANAC_LIVE=1`/`--live`) wired for the
  next attempt against a reachable ANAC host.
- `_system/validate.sh`: all checks passed.

## Outputs and changed files

- `tools/anac_ingest/ingest.py` (parser v6)
- `knowledge/anac-legislacao/support/` (fragments, indexes, catalogs)
- `knowledge/anac-legislacao/synthesis/lacunas-de-cobertura.md`
- `START-HERE.md`
- `_system/validate.sh` (quarantine treated as generated output)
- `outputs/quarantine/2026-09-14/`

## Closeout pointer

- `sessions/reviews/2026-09-14-anac-ingest-retry-closeout.md`
