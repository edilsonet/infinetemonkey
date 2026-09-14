# Transcript notes

Surface does not export a full chat transcript into git. This file records the
durable work trail for session-2026-09-14-anac-infinite-brain.

- Cloned https://github.com/starmynd-org/infinite-brain-os into infinite-brain-os/
- Registered namespace anac-legislacao (doctrine profile, full canon)
- Built tools/anac_ingest/ingest.py and query.py
- Live www.anac.gov.br timed out; ingest uses Arquivo.pt
- Catalog: 56 RBAC, 232 IS, 18 IAC
- Validator: All checks passed after pointer-only exemption on tools/anac-ingest.md
- Fetch: quote `@@` in Arquivo.pt CDX; prefix-match document folders; skip
  `anexo_norma` CEF PDFs; skip Pergamum as first source
- Parser version 5. Catalog codes come from `/rbac|is|iac/<code>` in the URL
- Ingest finished 2026-09-14 01:49:26: 72 ok, 234 error, 14208 fragments
- `python3 tools/anac_ingest/query.py manutencao 43.1` returns RBAC 43 subsecoes
