---
id: "knowledge-anac-legislacao-conceito-rbac"
aliases: ["knowledge-anac-legislacao-conceito-rbac", "conceito-rbac", "rbac"]
type: "Knowledge"
namespace: "anac-legislacao"
lifecycle_state: "research"
summary: "RBAC is a binding Brazilian Civil Aviation Regulation issued by ANAC, organized in FAR-like numbered parts with sections and lettered subsections."
confidence: 0.92
retrieval_class: "domain"
export_class: "internal"
edges:
  - target: "[[fragmentacao-legislativa]]"
    relation: "depends_on"
    confidence: 0.9
created: "2026-09-14"
---

## Definition

RBAC (Regulamento Brasileiro da Aviacao Civil) is the primary binding rule set. Numbering
follows the FAA FAR family in many parts (43 maintenance, 91 general operating, 121 air
carrier, 145 repair station), with Brazilian adaptations.

## Shape

Sections look like `43.1`, `43.1-I`, `43.13`. Subsections look like `(a)`, `(b)`,
`(d)-I`. Appendices are `Apendice A` through `F` and may carry internal codes such as
`A43.1`.

## Retrieval

Catalog: `support/catalogs/rbac.yml`. Fragments: `support/fragments/rbac/<codigo>/`.
