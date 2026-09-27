---
id: "knowledge-anac-legislacao-lacunas-de-cobertura"
aliases: ["knowledge-anac-legislacao-lacunas-de-cobertura", "lacunas-de-cobertura"]
type: "Knowledge"
namespace: "anac-legislacao"
lifecycle_state: "research"
summary: "Known coverage gaps for the ANAC corpus: live ANAC host blocked, archive snapshots may lag current emendas, and some PDFs fail extraction."
confidence: 0.8
retrieval_class: "domain"
export_class: "internal"
edges:
  - target: "[[ingerir-legislacao-anac]]"
    relation: "informed_by"
    confidence: 0.85
created: "2026-09-14"
---

## Current gaps

- `www.anac.gov.br` timed out from this environment. Ingest uses Arquivo.pt.
- When a live ANAC fetch path exists, `r.jina.ai` reads both pages and PDFs. Use it
  with `x-return-format: text` so line breaks survive, and `x-target-selector: #content`
  to drop portal chrome.
- Listing snapshots: RBAC 2024-06, IS 2025-12, IAC 2025-11. Newer emendas after those
  dates may be absent.
- Scanned IACs may yield weak text if the PDF is image-only.
- Some IS and IAC pages sit behind a login wall (`Nome do Usuário` / `Senha`). Those
  bodies are not fetchable without credentials.

## Ingest 2026-09-27 (reader bridge)

Catalog stays at 56 RBAC, 232 IS, 18 IAC (306 total). After this pass: 285 ok, 21 error,
19709 unique fragments, 12698 keyword keys, 58 categories. Full rows:
`support/catalogs/ingest-report.yml`.

Method: `tools/anac_ingest/fetch_via_reader.py` fetches through `r.jina.ai` and reuses the
`ingest.py` writers. It rejects 404 chrome, reader `Target URL returned error` lines, the
ANAC portal navigation, and broken `pergamum` links. For a norm page it prefers the official
PDF, then the `visualizar_ato_normativo` viewer, then the page body. `parse_listing` no longer
lets `resolveuid` links hijack `page_url`, which recovered `rbac-25`, `rbac-33`, and
`is-91-012-1`.

Unrecoverable in this pass:

- RBAC (5): `rbac-01-emd-17`, `rbac-21-emd-11`, `rbac-90-emd-02`, `rbac-91-emd-04`,
  `rbac-121-emd-21`. These superseded emenda pages return 404 on the live host and have no
  Arquivo.pt or Wayback snapshot reachable from here.
- IS (11, login wall unless noted): `is-90-001`, `is-91-403-001`, `is-107-002`,
  `is-121-002b`, `is-135-001`, `is-145-002b`, `is-145-003`, `is-175-013` are login gated;
  `is-21-019` returns 404; `is-141-007` and `is-175-001` are image-only PDFs with no
  extractable text.
- IAC (5): `iac-121-1013`, `iac-3130`, `iac-3507` return 404; `iac-2211` yields no text;
  `iac-2214` is a fax scan (image-only).

Note: `rbac-25` and `rbac-33` now carry the in-force text that used to be listed as the
missing `rbac-25-emd-146` and `rbac-33-emd-35` rows.

## Parser repair 2026-09-27 (PARSER_VERSION 7)

Before this pass, 41 documents collapsed into one dominant fragment (20KB to 396KB) because
the section detector only accepted numeric headings. The worst case was a bare date such as
`27.05.2025` matching the numeric pattern and swallowing the rest of the document.

Fixed in `tools/anac_ingest/ingest.py`:

- Reject a bare date (`dd.mm.yyyy`, `dd/mm/yyyy`) before section detection.
- Accept single-level IS/IAC headings (`7. PREPARAÇÃO PARA O EXAME`).
- Accept short standalone block names (`OBJETIVO`, `FUNDAMENTOS`, `DESENVOLVIMENTO DO
  ASSUNTO`), matched case-insensitively against a fixed structural list, with appendix
  repeats merged instead of overwritten.
- Accept list items written `a)` as well as `(a)`.
- Cap fragment and section slugs so long appendix titles stay under filesystem name limits.

After `--refragment`: 33959 fragments (was 19567), keyword index 15525 keys (was 12698),
dominant-blob documents 8 (was 41), zero documents lost fragments, report counts match disk,
fragment index has no broken paths.

The 8 remaining blobs are genuinely large sections that carry Title-Case subtitles or wide
tables rather than structural headings: `is-117-004`, `is-117-001`, `is-145-163-001`,
`is-21-004`, `is-110-003`, `is-183-003`, `is-154-002`, `is-141-005`.

## Ingest 2026-09-14

Catalog: 56 RBAC, 232 IS, 18 IAC. Final pass 12:21:36 after refragment and
cleanup: 53 ok, 253 error, 10177 unique fragments, 8169 keyword keys. Full rows:
`support/catalogs/ingest-report.yml`.

Counting fix: fragment ids used to repeat inside a document, which inflated the
totals (the raw run reported 14344). The parser now dedupes by id and keeps the
longest text, so metadata, `_index.yml` counts, and fragment-index entries all
agree: 10177 files, 10177 ids, 0 broken paths.

RBAC: 45 documents with text. Recovered: `rbac-129` (HTML), `rbac-23` (padded
`rbac-023` CDX), `rbac-031` and `rbac-035` (official ANAC PDFs that quote FAR
language). `rbac-27` (62 fragments) and `rbac-29` (74 fragments) now hold the 14
CFR Part 27/29 annex text shipped inside those RBACs, tagged `language: en` and
`foreign_annex: true`. Failed (no snapshot or `resolveuid`): `rbac-01-emd-17`,
`rbac-01-emd-18`, `rbac-21-emd-11`, `rbac-25-emd-146`, `rbac-33-emd-35`,
`rbac-61-emd-15`, `rbac-90-emd-02`, `rbac-91-emd-04`, `rbac-108-emd-07`,
`rbac-121-emd-21`. `rbac-38` has no usable snapshot at all.

IS: 8 documents with usable text. Most individual IS pages and PDFs are absent
from Arquivo.pt. Thin HTML chrome under 400 characters is treated as a miss, not
as a document. `@@` in `arquivo_norma` URLs must be CDX-quoted or prefix-matched
on the document folder.

IAC: 0 of 18. No document snapshots under the current IAC paths in Arquivo.pt.

Live ANAC and `www.gov.br/anac` were not usable here (timeout / 404 JSON).
Pergamum PDF hosts are also mostly missing. Re-ingest when a live ANAC fetch
path exists: run `ANAC_LIVE=1 python3 tools/anac_ingest/ingest.py` (or pass
`--live`). Live mode re-fetches the listing pages first, so a moved snapshot
does not block the run.

Cleanup: fragments with no surviving extracted text were moved to
`outputs/quarantine/2026-09-14/` (60 artifacts). `_system/validate.sh` now treats
`outputs/quarantine/` as generated output, the same as `outputs/_runtime/`.

## How to update this note

After each ingest, copy error rows from `support/catalogs/ingest-report.yml` into a
dated list below. Do not put that list in canon.
