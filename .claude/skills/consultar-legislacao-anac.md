---
id: "skill-consultar-legislacao-anac"
aliases: ["skill-consultar-legislacao-anac", "consultar-legislacao-anac"]
type: "Skill"
namespace: "anac-legislacao"
lifecycle_state: "research"
summary: "Answer ANAC legal questions by loading the keyword index then only the named subsection fragments."
confidence: 0.94
retrieval_class: "identity"
export_class: "internal"
description: "Use this skill for any RBAC, IS, or IAC question."
edges:
  - target: "[[consultar-legislacao-anac]]"
    relation: "implements"
    confidence: 0.95
  - target: "[[anac-legislacao-core-doctrine]]"
    relation: "depends_on"
    confidence: 0.95
created: "2026-09-14"
---

# consultar-legislacao-anac

Use this skill whenever the operator asks about ANAC rules.

## Do

1. Enter `knowledge/anac-legislacao/` through `INDEX.md`.
2. Read `canon/core-doctrine.md`.
3. Search `support/indexes/keyword-index.yml` and `category-index.yml`.
4. Optionally run `python3 tools/anac_ingest/query.py <termos>`.
5. Read the listed fragment YAML files.
6. Cite `cite` fields in the answer.

## Do not

- Do not load an entire extracted Markdown file first.
- Do not treat an IS as if it repealed an RBAC.
- Do not invent section numbers when the index is empty.
