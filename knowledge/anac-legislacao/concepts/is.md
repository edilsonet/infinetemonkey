---
id: "knowledge-anac-legislacao-conceito-is"
aliases: ["knowledge-anac-legislacao-conceito-is", "conceito-is", "is"]
type: "Knowledge"
namespace: "anac-legislacao"
lifecycle_state: "research"
summary: "IS is an ANAC supplementary instruction that shows an acceptable means of compliance with an RBAC. It does not repeal the regulation it interprets."
confidence: 0.92
retrieval_class: "domain"
export_class: "internal"
edges:
  - target: "[[conceito-rbac]]"
    relation: "depends_on"
    confidence: 0.9
created: "2026-09-14"
---

## Definition

IS (Instrucao Suplementar) is guidance that demonstrates one acceptable way to comply
with an RBAC. An operator may propose an equivalent means, but the RBAC remains the
binding text.

## Shape

Codes look like `IS 43-001A`. Body structure is usually numbered (`1. Objetivo`,
`5. Disposicoes`, `5.1`, `5.1.1`) rather than FAR-style `43.1(a)`.

## Retrieval

Catalog: `support/catalogs/is.yml`. Fragments: `support/fragments/is/<codigo>/`.
