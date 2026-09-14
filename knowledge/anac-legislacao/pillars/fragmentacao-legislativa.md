---
id: "knowledge-anac-legislacao-fragmentacao-legislativa"
aliases: ["knowledge-anac-legislacao-fragmentacao-legislativa", "fragmentacao-legislativa"]
type: "Knowledge"
namespace: "anac-legislacao"
lifecycle_state: "research"
summary: "The ANAC corpus is stored as document, section, subsection, then keyword index, so an agent reads the smallest sufficient legal grain."
confidence: 0.93
retrieval_class: "identity"
export_class: "internal"
edges:
  - target: "[[granularidade-subsecao]]"
    relation: "informed_by"
    confidence: 0.9
created: "2026-09-14"
---

## Claim

A regulation is not a retrieval unit. A subsection is. RBAC 43 is a container. 43.1 is a
section. 43.1(a) is the grain an agent should load for aplicabilidade.

## The stack

1. Documento: um RBAC, uma IS ou uma IAC, com ementa e emenda.
2. Secao: `43.1`, `43.1-I`, `Apêndice A`, ou `5.1` em IS.
3. Subsecao: `43.1(a)`, `43.1(b)`, `43.1(d)-I`.
4. Indice: palavra-chave e categoria apontam para o YAML da subsecao.

## Why this is the pillar

Context windows fail when the agent swallows 30 pages to answer one applicability
question. Fragmentation is the control that keeps retrieval honest.
