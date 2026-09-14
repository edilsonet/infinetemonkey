---
id: "knowledge-anac-legislacao-canon-core-doctrine"
aliases: ["knowledge-anac-legislacao-canon-core-doctrine", "anac-legislacao-core-doctrine"]
type: "Knowledge"
namespace: "anac-legislacao"
lifecycle_state: "research"
summary: "Retrieval doctrine for ANAC law: index first, then subsection fragments, never a whole RBAC, IS, or IAC as the first read."
confidence: 0.9
retrieval_class: "identity"
export_class: "internal"
verified_at: "2026-09-14"
verified_by: "operator-pending"
edges:
  - target: "[[fragmentacao-legislativa]]"
    relation: "derived_from"
    confidence: 0.95
  - target: "[[conceito-rbac]]"
    relation: "derived_from"
    confidence: 0.9
  - target: "[[conceito-is]]"
    relation: "derived_from"
    confidence: 0.9
  - target: "[[conceito-iac]]"
    relation: "derived_from"
    confidence: 0.88
  - target: "[[granularidade-subsecao]]"
    relation: "derived_from"
    confidence: 0.92
created: "2026-09-14"
---

## Read this first

This namespace is a retrieval machine over Brazilian civil aviation law. The unit of
truth an agent may quote is a subsection fragment, not a whole regulation and not a
paraphrase in this file.

## Hard rules

1. Load this canon, then the keyword index, then only the fragments the index names.
2. Cite the fragment identifier (`43.1(a)`, `Apêndice A`, `IS 43-001 5.1`), not "o RBAC 43".
3. RBAC is the binding regulation. IS explains how to comply. IAC is the older
   instruction family, often historical.
4. If two fragments conflict, prefer the later emenda in the catalog and surface the
   conflict instead of averaging them.
5. Raw PDFs and HTML are provenance. They are not the retrieval surface.

## The four layers

Documento (RBAC 43) -> secao (43.1) -> subsecao (43.1(a)) -> indice por palavra-chave.
The index exists so a question about "aprovacao para retorno ao servico" loads 43.5 and
43.7 fragments, not 31 pages of RBAC 43.

## Boundary

This canon does not restate statutory text. If a claim needs a legal sentence, open the
YAML fragment. If the fragment is missing, say the coverage gap and point to
`synthesis/lacunas-de-cobertura.md`.

## Changelog

- 2026-09-14: Initial retrieval doctrine for the ANAC namespace standup.
