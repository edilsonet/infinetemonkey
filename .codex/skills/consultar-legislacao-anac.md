---
id: "skill-consultar-legislacao-anac"
aliases: ["skill-consultar-legislacao-anac", "consultar-legislacao-anac"]
type: "Skill"
namespace: "anac-legislacao"
lifecycle_state: "research"
summary: "Answer ANAC legal questions with two retrieval paths: the keyword index for precision, tools/anac-rag for semantic recall."
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
  - target: "[[tool-anac-rag]]"
    relation: "uses"
    confidence: 0.9
created: "2026-09-14"
---

# consultar-legislacao-anac

Use this skill whenever the operator asks about ANAC rules.

## The two retrieval paths

| Path | Tool | Role | Works offline |
|---|---|---|---|
| Precision | `tools/anac_ingest/query.py` | Exact terms, topic keys | Yes |
| Recall | `tools/anac-rag` `POST /query` | Natural phrasing, paraphrase | No |

Neither replaces the other. Precision resolves the question; recall rescues a phrasing the
index has no key for. See `_system/retrieval-load-order-policy.md` Rule LOAD-1.

## Do

1. Enter `knowledge/anac-legislacao/` through `INDEX.md`.
2. Read `canon/core-doctrine.md`.
3. Choose the path:
   - the operator named a topic key (`manutencao`, `retorno ao servico`): run
     `python3 tools/anac_ingest/query.py <termos>` (keywords in Portuguese, no accents).
   - the question is natural language, or step 3 returned nothing: call `POST /query` on the
     `tools/anac-rag` Worker with `{"query": "<pergunta>"}`.
4. If both were used, union the cite sets.
5. Read the listed fragment YAML files.
6. Cite `cite` fields in the answer.

Calling the Worker needs the bearer token in `ANAC_RAG_TOKEN`. If it is unset or the network
is down, that is not a failure: fall back to the keyword index and say which path answered.

## Do not

- Do not load an entire extracted Markdown file first.
- Do not treat an IS as if it repealed an RBAC.
- Do not invent section numbers when retrieval is empty.
- Do not quote a Worker hit without opening the fragment. A vector hit is a pointer.
- Do not answer from memory when the corpus has nothing. Say the coverage gap and point to
  `synthesis/lacunas-de-cobertura.md`.