# Agent Load Order: anac-legislacao

This file is navigational. It tells agents what to load after `core-doctrine.md`.

## Always load first

`canon/core-doctrine.md` in full.

## By query class

**Lookup of a legal topic** (manutencao, retorno ao servico, licenca, operador):
Load `support/indexes/keyword-index.yml` and `support/indexes/category-index.yml`.
Open only the fragment YAML paths listed. If two fragments collide, also open the
parent section fragment (`subsection_id: body`).

**What kind of instrument is this**:
Load `concepts/rbac.md`, `concepts/is.md`, or `concepts/iac.md`.

**How to ingest or refresh the corpus**:
Load `playbooks/ingerir-legislacao-anac.md` and run `tools/anac_ingest/ingest.py`.

**Coverage gaps**:
Load `synthesis/lacunas-de-cobertura.md` and `support/catalogs/ingest-report.yml`.

## What not to load first

Do not open `support/sources/pdf/` or a full `support/extracted/` file until the index
has named a fragment and that fragment is insufficient.

## Navigational note

This file does not carry node frontmatter.
