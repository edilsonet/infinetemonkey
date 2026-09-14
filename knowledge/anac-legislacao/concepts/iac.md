---
id: "knowledge-anac-legislacao-conceito-iac"
aliases: ["knowledge-anac-legislacao-conceito-iac", "conceito-iac", "iac"]
type: "Knowledge"
namespace: "anac-legislacao"
lifecycle_state: "research"
summary: "IAC is the older Civil Aviation Instruction family. Many items were replaced by IS. Always check catalog status before treating an IAC as current."
confidence: 0.9
retrieval_class: "domain"
export_class: "internal"
edges:
  - target: "[[conceito-is]]"
    relation: "informed_by"
    confidence: 0.86
created: "2026-09-14"
---

## Definition

IAC (Instrucao de Aviacao Civil) predates the IS system. Remaining IACs are often
narrow or historical. Do not assume an IAC is in force because a PDF exists.

## Retrieval

Catalog: `support/catalogs/iac.yml`. Fragments: `support/fragments/iac/<codigo>/`.
If an IS covers the same subject, prefer the IS and note the IAC as lineage.
