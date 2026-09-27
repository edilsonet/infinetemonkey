---
session_id: "session-2026-09-27-anac-legislacao-recovery"
date: "2026-09-27"
topic: "anac-legislacao-recovery"
status: "closed"
surface: "opencode"
operator: "the-operator"
namespace: "anac-legislacao"
goal: "Recover the missing ANAC RBAC/IS/IAC legislation through a reader bridge and rebuild the fragment index."
transcript_paths:
  - "sessions/logs/2026-09-27-anac-legislacao-recovery.log.md"
---

# Session: anac legislacao recovery

Extract the legislation still missing from the `anac-legislacao` namespace while the
live ANAC host is unreachable, by fetching norm text through a reader bridge and
reusing the existing fragment/index pipeline.

## Running notes

- The live `www.anac.gov.br` host is unreachable from this environment and the old
  pages return 404 chrome. `r.jina.ai` reads both pages and PDFs; a per-request
  `X-Target-Selector: #content` scopes page text, and `X-Return-Format: text`
  preserves the line breaks the fragment parser needs.
- Added `tools/anac_ingest/fetch_via_reader.py` to reuse `ingest.py` writers.
- Rejected portal chrome, 404 pages, reader `Target URL returned error` lines, and
  broken `pergamum` links so junk does not enter the corpus.
- Found the `visualizar_ato_normativo` viewer endpoint, which exposes the full text
  of IS published in the personnel bulletins; it must be read with `#content`.
- Fixed `parse_listing` so `resolveuid` links no longer hijack `page_url`; this
  recovered `rbac-25`, `rbac-33`, and `is-91-012-1`.
- Final coverage: 285 ok, 21 error of 306. 19709 fragments, 12698 keyword keys,
  58 categories, 0 broken index paths. `_system/validate.sh` passes.
- The 21 remaining are not fetchable: 5 superseded RBAC emendas (live 404, no
  reachable snapshot), 8 login-gated IS plus 1 IS 404 and 2 image-only IS PDFs,
  and 5 IAC (404 or image-only fax scans).
- Open question: 41 documents keep one dominant blob fragment (non-numeric
  ALL-CAPS headings). A parser change plus refragment could fix retrieval quality
  there, at the risk of touching the 244 well-fragmented documents.
- Repaired the parser (PARSER_VERSION 7): reject bare dates, accept single-level
  IS/IAC headings and structural block names, accept `a)` list items, merge repeated
  appendix headers, cap slugs. Reframed 285 docs: 33959 fragments, blob documents
  down from 41 to 8, no document lost fragments, indexes consistent.

## Outputs and changed files

- `tools/anac_ingest/fetch_via_reader.py` (reader bridge)
- `tools/anac_ingest/ingest.py` (`parse_listing` resolveuid fix, PARSER_VERSION 7)
- `knowledge/anac-legislacao/support/` (fragments, indexes, catalogs, report)
- `knowledge/anac-legislacao/synthesis/lacunas-de-cobertura.md`

## Usage receipt

- Usage capture status: unavailable
- Usage source: none
- Runtime session id: unknown
- Captured at: 2026-09-27
- Input tokens: unknown
- Output tokens: unknown
- Cached input tokens: unknown
- Tool calls: unknown
- Tool cost usd: unknown
- Estimated cost usd: unknown
- Usage notes: surface did not expose token or cost totals.

## Closeout pointer

- `sessions/reviews/2026-09-27-anac-legislacao-recovery-closeout.md`
