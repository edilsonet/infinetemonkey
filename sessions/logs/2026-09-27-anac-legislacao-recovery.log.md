# Transcript: anac-legislacao-recovery (2026-09-27)

Surface: opencode. The live chat transport does not export a byte-for-byte tool
trace into the repo, so this log is a curated event trail rather than a raw dump.
The gap is stated explicitly per Rule SESSION-4.

## Event trail

1. Confirmed the gap: 306 catalogued documents, 63 recovered, 243 missing.
2. Confirmed the live ANAC host is unreachable; adopted the `r.jina.ai` bridge.
3. Built `tools/anac_ingest/fetch_via_reader.py` over `ingest.py`.
4. Trial: text format restored structure (`is-43-001` went from 1 to 22 fragments).
5. Rejected junk: 404 chrome, reader error lines, portal navigation, `pergamum`.
6. Ran IAC: 12 real documents recovered; 6 unavailable (404 or scanned fax PDF).
7. Fixed `parse_listing` `resolveuid` hijack; regenerated the RBAC/IS/IAC catalogs.
8. Drained IS in chunks; added `visualizar_ato_normativo` viewer support.
9. Ran a final recovery pass over the remaining IS documents.
10. Fixed the fragmenter: date rejection, single-level headings, structural block
    names, `a)` list items, appendix merge, slug length cap (PARSER_VERSION 7).
11. Refragmented 285 docs offline and rebuilt the indexes.

Final counts are recorded in the closeout review at
`sessions/reviews/2026-09-27-anac-legislacao-recovery-closeout.md`.
