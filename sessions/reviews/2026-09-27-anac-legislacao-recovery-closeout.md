---
session_id: "session-2026-09-27-anac-legislacao-recovery"
date: "2026-09-27"
topic: "anac-legislacao-recovery"
status: "closed"
---

# Closeout: anac legislacao recovery

Session record: `sessions/closed/2026-09-27-anac-legislacao-recovery.md`
Transcript: `sessions/logs/2026-09-27-anac-legislacao-recovery.log.md`

## Summary

Recovered the ANAC legislation still missing from `knowledge/anac-legislacao` while the live
host is unreachable, by reading norm pages and PDFs through an r.jina.ai bridge and reusing
the existing ingest writers. Then repaired the fragmenter so headings that were not purely
numeric no longer collapse whole documents into one blob, and refragmented the whole corpus
offline. Coverage is 285 ok of 306; 21 documents are genuinely not fetchable from this
environment.

## Outputs produced

- `tools/anac_ingest/fetch_via_reader.py`: reader-bridge fetcher with portal-chrome, 404 and
  reader-error rejection; PDF-official, viewer and page fallbacks; `#content` scoping.
- `tools/anac_ingest/ingest.py`: `parse_listing` resolveuid fix and PARSER_VERSION 7 parser
  repair (date rejection, single-level headings, structural block names, `a)` items,
  appendix merge, slug length cap).
- Corpus: 285 ok, 21 error, 33959 fragments, 15525 keyword keys, 58 categories, 0 broken
  index paths.
- `knowledge/anac-legislacao/support/catalogs/` and `support/indexes/` rebuilt.
- `knowledge/anac-legislacao/synthesis/lacunas-de-cobertura.md` updated with the new gaps and
  the parser-repair record.

## Decisions made

- Use `r.jina.ai` as the only reachable bridge; `X-Return-Format: text` preserves the line
  breaks the fragmenter needs and `X-Target-Selector: #content` strips portal chrome.
- Prefer the official PDF, then the `visualizar_ato_normativo` viewer, then the page body.
- Reject junk before it enters the corpus rather than cleaning it later.
- Repair the parser and refragment in place instead of leaving 41 dominant blobs, accepting
  the risk of touching the 244 already well-fragmented documents.
- For `rbac-25` and `rbac-33`, carry the in-force text that the stale listing had attributed
  to superseded emendas.

## Wrong turns and confusion

- The live host is unreachable; several page fetches returned portal chrome or 404 that the
  first parser accepted. Rejection rules were added only after junk was found in the output.
- `parse_listing` let `resolveuid` links overwrite `page_url`, silently dropping some
  documents until the fix.
- The blob cause was a bare date such as `27.05.2025` matching the numeric section pattern,
  so the whole rest of the document became one fragment. A whole pass was needed to find it.
- The viewer endpoint returns chrome unless it is read with `#content`.

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

## Memory candidates

- An unreachable legislation host can still read through `r.jina.ai`; scope it with
  `X-Target-Selector: #content` and keep `X-Return-Format: text` for paragraph structure.
- A bare date line can match a numeric section pattern and swallow a document; reject dates
  before heading detection.
- ANAC IS bulletins keep full text behind a `visualizar_ato_normativo` viewer that needs
  `#content`.

## PKM or namespace candidates

- `knowledge/anac-legislacao/support/indexes/` stays the retrieval surface for fragments.
- The recovered IS/IAC bodies are not promoted further; promotion out of `scratch` is an
  operator decision.

## Follow-up tasks

- Re-attempt the 21 unfetchable documents if a snapshot source (for example Arquivo.pt or the
  live host) becomes reachable, and through `ANAC_LIVE=1` once the host works.
- Decide whether the 8 remaining long sections warrant finer splitting or an OCR path for the
  image-only PDFs.

## Swarm candidates or follow-ups

- None.

## Human review needed

- Do not promote fragments or the coverage note to canon without operator review.
- Confirm the in-force text swap for `rbac-25` and `rbac-33` against the official listing.

## System improvements

- `fetch_via_reader.py` centralizes the bridge and its junk filters, so future recovery runs
  do not re-derive the rejection rules.
- A focused parser self-test confirms the date, single-level, structural, appendix and `a)`
  cases and the filename-length guard.

## Unresolved risks or open questions

- 21 documents (5 RBAC emendas, 11 IS, 5 IAC) remain out of reach; 3 are image-only PDFs and
  would need OCR.
- 8 documents still hold one large dominant fragment; the split is coarse but the fragments
  are legitimate sections, not parser failures.
- The bridge depends on a third-party reader; if it changes behavior, recovery quality drops.
