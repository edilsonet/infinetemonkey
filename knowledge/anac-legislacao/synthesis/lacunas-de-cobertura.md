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
- Listing snapshots: RBAC 2024-06, IS 2025-12, IAC 2025-11. Newer emendas after those
  dates may be absent.
- Scanned IACs may yield weak text if the PDF is image-only.

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
