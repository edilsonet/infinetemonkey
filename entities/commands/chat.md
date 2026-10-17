---
id: "command-chat"
aliases: ["command-chat", "chat"]
type: "command"
namespace: "anac-legislacao"
lifecycle_state: "research"
summary: "Ask the Cloudflare brain a Brazilian civil aviation question and answer from the retrieved fragments."
confidence: 0.88
retrieval_class: "identity"
export_class: "internal"
auto_inject: false
applicable_when: "Use when the operator types /chat, or asks the cloud brain a question about RBAC, IS or IAC in natural language."
tags: [command, anac, rbac, is, iac, vectorize, rag]
created: "2026-10-04"
---

# /chat

Ask the Cloudflare brain a question in plain Portuguese and answer from what it returns.

## Invoke

```bash
powershell.exe -NoProfile -Command "
\$t=[Environment]::GetEnvironmentVariable('ANAC_RAG_TOKEN','User')
if(-not \$t){ Write-Output 'SEM_TOKEN'; exit }
\$q = Read-Host 'Pergunta'
\$body = @{ query = \$q; top_k = 6 } | ConvertTo-Json -Compress
\$r = Invoke-RestMethod -Uri 'https://anac-rag.rocha-eng.workers.dev/query' -Method Post -Headers @{Authorization=\"Bearer \$t\"} -ContentType 'application/json' -Body \$body -TimeoutSec 90
if(\$r.count -eq 0){ Write-Output 'NENHUM_RESULTADO' }
else{ \$r.results | ForEach-Object { Write-Output ('--- ' + \$_.score + ' | ' + \$_.cite + ' | ' + \$_.code + ' | ' + \$_.document_title); Write-Output \$_.text; Write-Output ('sec: ' + \$_.section_title) } }
"
```

Type `/chat`, then the question at the prompt. Without a question, nothing runs.

## Do

1. Read the question the operator typed. Do not rephrase it before sending.
2. Run the block above.
3. If it prints `SEM_TOKEN`, the token is not registered. Tell the operator and use the
   local keyword index instead, which covers all 285 documents and needs no network.
4. If it prints `NENHUM_RESULTADO`, the corpus does not cover the question. Say so and point
   at `knowledge/anac-legislacao/synthesis/lacunas-de-cobertura.md`. Do not try another
   phrasing more than twice.
5. Otherwise answer from the returned fragments. Every normative claim carries the `cite` of
   the fragment that supports it.

## Do not

- **Do not open `support/extracted/` or the PDFs.** The endpoint returns the passage. That is
  the whole point of the retrieval layer.
- **Do not answer from memory.** Every claim about what the norm requires comes from a
  fragment returned above, with its `cite`.
- **Do not invent a section number.** If the returned cites do not support it, it is not in
  the answer.
- **Do not call `/chat` on the Worker.** It needs a language model configured and returns
  `mode: retrieval-only`. Write the answer yourself from the fragments; that path hallucinates
  less.

## Output

Prose answer in Portuguese, with citations inline like `61.73(a)` or `IS 175-005 5.2`. Name the
document when the distinction matters, since RBAC binds, IS explains compliance and IAC is
often superseded.

## Related

- `tools/anac-rag` is the Worker pointer. `tools/anac-rag.md` carries the endpoint contract.
- [[consultar-legislacao-anac]] is the keyword path, which is the fallback and the more precise
  of the two when the operator names a topic key.
- [[anac-legislacao-core-doctrine]] holds the hard rules this command applies.