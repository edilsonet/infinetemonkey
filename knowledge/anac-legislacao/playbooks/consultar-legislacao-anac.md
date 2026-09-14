---
id: "knowledge-anac-legislacao-consultar-legislacao-anac"
aliases: ["knowledge-anac-legislacao-consultar-legislacao-anac", "consultar-legislacao-anac"]
type: "Knowledge"
namespace: "anac-legislacao"
lifecycle_state: "research"
summary: "Procedure for any file-reading AI to answer an ANAC legal question by index then fragment, with a citation."
confidence: 0.94
retrieval_class: "domain"
export_class: "internal"
edges:
  - target: "[[anac-legislacao-core-doctrine]]"
    relation: "implements"
    confidence: 0.95
created: "2026-09-14"
---

# Consultar legislacao ANAC

## Trigger

Any question about Brazilian civil aviation rules, maintenance, licensing, operations,
aerodromes, security, or dangerous goods.

## Steps

1. Read `canon/core-doctrine.md` if not already loaded.
2. Open `support/indexes/keyword-index.yml` and `support/indexes/category-index.yml`.
3. Collect fragment paths for the topic keys (example: manutencao, retorno, inspecao).
4. Read those YAML files only. Each file has `cite`, `title`, `text`, `keywords`.
5. Answer with the `cite` in front of the quoted or paraphrased rule.
6. If the fragment is incomplete, open the sibling `subsection_id: body` for that section.
7. Only then open `support/extracted/` for the whole document.

## Escalation

If the index has no key and the catalog has no document, say coverage is missing and
point to `synthesis/lacunas-de-cobertura.md`. Do not invent a section number.
