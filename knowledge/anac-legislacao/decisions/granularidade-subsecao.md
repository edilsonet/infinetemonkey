---
id: "knowledge-anac-legislacao-granularidade-subsecao"
aliases: ["knowledge-anac-legislacao-granularidade-subsecao", "granularidade-subsecao"]
type: "Knowledge"
namespace: "anac-legislacao"
lifecycle_state: "research"
summary: "Chose lettered subsection grain (43.1(a)) over whole-section or nested (1)(i) files as the default fragment, because that matches how ANAC texts are cited."
confidence: 0.9
retrieval_class: "domain"
export_class: "internal"
edges:
  - target: "[[fragmentacao-legislativa]]"
    relation: "depends_on"
    confidence: 0.92
created: "2026-09-14"
---

## Decision

Default fragment grain is the lettered subsection: `43.1(a)`, `43.1(b)`, `43.1(d)-I`.
Nested numerals `(1)`, `(2)`, `(i)` stay inside the letter fragment.

## Rejected alternative

One file per nested numeral (`43.1(a)(1)`) was rejected as the default: it explodes
file count and splits sentences that only make sense under the parent letter.

Whole-section files were rejected as the default: 43.3 is already several distinct
authorization rules.

## Consequence

The keyword index points at letter fragments. An agent that needs a nested numeral
still reads the parent letter, which contains it.
