---
id: command-consultar-anac
aliases: ["command-consultar-anac", "consultar-anac"]
type: command
namespace: anac-legislacao
summary: "Slash command that answers an ANAC legislation question via keyword index then subsection fragments."
auto_inject: false
applicable_when: "Use when the operator asks what an RBAC, IS, or IAC requires."
confidence: 0.9
verified_at: 2026-09-14
verified_by: operator-pending
lifecycle_state: research
export_class: internal
retrieval_class: normal
tags: [command, anac, rbac, is, iac]
---

# /consultar-anac

Answer a Brazilian civil aviation law question using the `anac-legislacao` namespace.

1. Read `knowledge/anac-legislacao/INDEX.md` and `canon/core-doctrine.md`.
2. Look up terms in `knowledge/anac-legislacao/support/indexes/keyword-index.yml`.
3. Read only the fragment YAML files listed.
4. Answer with citations such as `43.1(a)` or `IS 43-001 5.1`.
