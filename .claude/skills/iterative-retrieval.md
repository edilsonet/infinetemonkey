---
id: "skill-iterative-retrieval"
aliases: ["skill-iterative-retrieval", "iterative-retrieval"]
type: "Skill"
namespace: "anac-legislacao"
lifecycle_state: "research"
summary: "Refine retrieval across passes when top-k misses: broaden, add a synonym, requery, then fall back to the keyword index."
confidence: 0.82
retrieval_class: "domain"
export_class: "internal"
description: "Use this skill when a first retrieval pass over the ANAC corpus misses the right fragment and the query must be reformulated before answering."
edges:
  - target: "[[tool-anac-rag]]"
    relation: "uses"
    confidence: 0.9
  - target: "[[consultar-legislacao-anac]]"
    relation: "paired_with"
    confidence: 0.9
verified_by: "operator-pending"
created: "2026-09-30"
---

# iterative-retrieval

Retry discipline for retrieval. Use it when the first pass did not return the fragment the
question needs. Adapted from `skills/iterative-retrieval` in affaan-m/ECC (MIT).

## Use when

- `POST /query` on `tools/anac-rag` returned nothing above `MIN_SCORE`.
- The returned chunks are topically adjacent but do not answer the question.
- The question was phrased in natural language and the keyword index has no key for it.

## Do not use when

- The corpus genuinely does not cover the topic. Iterating cannot create coverage. See
  `synthesis/lacunas-de-cobertura.md`.
- The question is a meta-question about the corpus itself (what is an RBAC, how does this
  brain work). Those live in `concepts/`, not in a chunk.

## The loop

Each pass changes one thing, so a failure tells you which change mattered.

| Pass | Change | If it still misses |
|---|---|---|
| 1 | The question as asked | Pass 2 |
| 2 | Strip to the legal noun phrase: drop qualifiers, keep the regulated object | Pass 3 |
| 3 | Add a domain synonym in Portuguese, unaccented (`licenca`, `tripulante`, `aerodromo`) | Pass 4 |
| 4 | Constrain by family: `{"family": "43"}` for maintenance | Pass 5 |
| 5 | Query the keyword index with `tools/anac_ingest/query.py`, which is exact rather than semantic | Stop, report the gap |

Stop after pass 5. Two retrieval paths plus the keyword index is the ceiling. Continuing
past it produces a confident answer with no source, which is the one failure mode that
`canon/core-doctrine.md` exists to prevent.

## Recording the outcome

When a loop resolved, note which pass worked. That is the cheapest signal available for
deciding whether `MIN_SCORE` or `TOP_K_SEMANTIC` in `tools/anac-rag/wrangler.jsonc` is
wrong, and it is worth more than a speculative parameter change.

## Anti-patterns

- Reformulating every pass at once. Then a hit tells you nothing about what fixed it.
- Lowering `MIN_SCORE` to force results. That trades precision for the appearance of recall.
- Answering from a pass-4 result you did not read. A vector hit is a pointer; open the
  fragment before quoting it.
- Iterating on a coverage gap. The document is missing, not hard to find.