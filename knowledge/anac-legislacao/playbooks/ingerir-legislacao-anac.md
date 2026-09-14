---
id: "knowledge-anac-legislacao-ingerir-legislacao-anac"
aliases: ["knowledge-anac-legislacao-ingerir-legislacao-anac", "ingerir-legislacao-anac"]
type: "Knowledge"
namespace: "anac-legislacao"
lifecycle_state: "research"
summary: "Procedure to refresh RBAC, IS, and IAC listings, download sources, extract text, fragment to subsection YAML, and rebuild keyword indexes."
confidence: 0.93
retrieval_class: "domain"
export_class: "internal"
edges:
  - target: "[[fragmentacao-legislativa]]"
    relation: "implements"
    confidence: 0.92
created: "2026-09-14"
---

# Ingerir legislacao ANAC

## Trigger

First standup, a new emenda, or `support/catalogs/ingest-report.yml` showing errors.

## Steps

1. From the Infinite Brain root run:

```bash
python3 tools/anac_ingest/ingest.py
```

2. Optional subset:

```bash
python3 tools/anac_ingest/ingest.py rbac
python3 tools/anac_ingest/ingest.py is iac
```

3. Confirm catalogs in `support/catalogs/`.
4. Confirm fragments in `support/fragments/<tipo>/<codigo>/`.
5. Confirm indexes in `support/indexes/`.
6. Read `ingest-report.yml` and record remaining errors in
   `synthesis/lacunas-de-cobertura.md`.

## Notes

Live `www.anac.gov.br` may time out. The ingest prefers Arquivo.pt and stores the
original ANAC URL on every catalog item.
