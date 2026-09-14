---
id: "tool-anac-ingest"
aliases: ["tool-anac-ingest", "anac-ingest"]
type: "Tool"
namespace: "anac-legislacao"
lifecycle_state: "research"
summary: "Local ingest and query scripts that fetch ANAC RBAC, IS, and IAC sources, fragment them, and look up subsection files."
confidence: 0.9
retrieval_class: "identity"
export_class: "internal"
tool_type: "cli"
tool_status: "active"
system_fit: "department-local-tool"
contract_status: "pointer-only"
contract_reason: "Local ingest scripts live in tools/anac_ingest/. A separate tool-contract namespace would duplicate the anac-legislacao playbooks."
created: "2026-09-14"
---

# anac-ingest

Bounded capability: ingest and query the ANAC corpus. No network tool is required at
answer time. The working tree is the retrieval surface.

## Commands

```bash
python3 tools/anac_ingest/ingest.py
python3 tools/anac_ingest/query.py manutencao
```

## Outputs

Writes under `knowledge/anac-legislacao/support/`. Does not write canon.
