# anac-legislacao: support

Provenance and generated corpus. No node frontmatter. Excluded from graph checks.

- `sources/html/`: listing pages and document HTML
- `sources/pdf/`: downloaded PDFs
- `extracted/`: full text Markdown
- `fragments/`: YAML per subsection
- `indexes/`: keyword, category, and fragment indexes
- `catalogs/`: RBAC, IS, IAC inventories plus ingest-report.yml

Agents retrieve through `indexes/` then `fragments/`. They do not browse PDFs first.
