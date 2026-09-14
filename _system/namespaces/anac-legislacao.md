---
id: namespace-anac-legislacao
name: anac-legislacao
purpose: "Corpus operativo da legislacao ANAC: RBAC, IS e IAC fragmentados ate subsecao, com indice por palavras-chave para qualquer agente de arquivos."
owner: the-operator
lifecycle_state: research
created: 2026-09-14
group: operations
retrieval_class: explicit
export_class: internal
default_visibility: private
tags: [namespace, research, operations, anac, rbac, is, iac, legislacao]
supersedes: null
profile: doctrine
v2_status: upgraded
canon_posture: full
freshness_posture: review-on-edit
archive_posture: support
expected_folders: [INDEX.md, canon, pillars, concepts, decisions, playbooks, support, synthesis]
notes: "Born V2. Raw PDFs and HTML live in support/. Fragments and keyword indexes also live in support/ so legal punctuation does not trip node lint. Canon states retrieval doctrine, not the statutes themselves."
---

# anac-legislacao

## Summary

Namespace of Brazilian civil aviation legislation for AI retrieval. Agents never load a
whole RBAC, IS, or IAC first. They load canon, then the keyword index, then only the
subsection fragments the index names.

## Defaults

| Field | Default |
|-------|---------|
| `lifecycle_state` on nodes | `research` |
| `retrieval_class` on nodes | `domain` |
| `export_class` on nodes | `internal` |

## Profile and folders

Profile: `doctrine`. The job is durable retrieval doctrine over a legal corpus, not an
SOP library and not a tool contract.

Expected folders: `INDEX.md`, `canon/`, `pillars/`, `concepts/`, `decisions/`,
`playbooks/`, `support/`, `synthesis/`.

## Review posture

Freshness posture: `review-on-edit`. Re-ingest when ANAC publishes a new emenda.
`archive_posture: support` means provenance, PDFs, extracted text, fragments, and
indexes live under `support/` and are historical plus mechanical, not canon.
