---
session_id: "session-2026-09-14-anac-ingest-retry"
date: "2026-09-14"
topic: "anac-ingest-retry"
status: "closed"
---

# Closeout: anac ingest retry

Session record: `sessions/closed/2026-09-14-anac-ingest-retry.md`

## Summary

Recovered four RBAC snapshots, refragmented the corpus with id dedupe, moved dead
artifacts to quarantine, and pulled the 14 CFR Part 27/29 annexes carried inside
RBAC 27 and 29. The validator passes on the whole vault again.

## Outputs produced

- Parser v6 in `tools/anac_ingest/ingest.py`: language detection, foreign-annex
  labeling, id dedupe, `--refragment`, `--clean`, `--only=<codes>`, and live mode.
- Corpus: 53 ok, 253 error, 10177 unique fragments, 8169 keyword keys.
- Quarantine: `outputs/quarantine/2026-09-14/` (60 dead artifacts).
- Coverage note and `START-HERE.md` updated.

## Decisions made

- Keep the CFR/FAA annex text shipped inside an RBAC: it is real ANAC document
  content, labeled `foreign_annex: true` instead of discarded.
- Dedupe fragments by id, keeping the longest text, so counts are trustworthy.
- Quarantine dead artifacts rather than delete them.
- Treat `outputs/quarantine/` as generated output in the validator.

## Wrong turns and confusion

- The first `--only` parser read positional args, so `--only=...` was ignored and
  a full reingest started; killed and fixed.
- Parallel edits to `_system/validate.sh` dropped one hunk; edits to one file must
  stay sequential.
- The counters had been inflated by duplicate ids (14344 reported vs 10177 real).

## Usage receipt

- Usage capture status: unavailable
- Usage source: none
- Runtime session id: unknown
- Captured at: 2026-09-14
- Input tokens: unknown
- Output tokens: unknown
- Cached input tokens: unknown
- Tool calls: unknown
- Tool cost usd: unknown
- Estimated cost usd: unknown
- Usage notes: surface did not expose token or cost totals.

## Memory candidates

- Arquivo.pt CDX returns 14 CFR annex PDFs for RBAC 27/29; label them, do not drop.
- Fragment ids can repeat within a document; dedupe before counting.

## PKM or namespace candidates

- `knowledge/anac-legislacao/support/indexes/` remains the retrieval surface.

## Follow-up tasks

- Re-ingest IS and IAC when live ANAC fetch works (`ANAC_LIVE=1`).
- Local manual folders under `/OM-145/` are still to be created.

## Swarm candidates or follow-ups

- None.

## Human review needed

- Do not promote fragments to canon without operator review.

## System improvements

- `_system/validate.sh` now prunes `outputs/quarantine/` for frontmatter and dash
  checks.

## Unresolved risks or open questions

- 224 IS and all 18 IAC still missing from Arquivo.pt.
- RBAC 27/29 hold only the English CFR annex, not a Portuguese RBAC body.
