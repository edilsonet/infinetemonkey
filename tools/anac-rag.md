---
id: "tool-anac-rag"
aliases: ["tool-anac-rag", "anac-rag"]
type: "Tool"
namespace: "anac-legislacao"
lifecycle_state: "research"
summary: "Semantic retrieval over the ANAC RBAC, IS and IAC corpus through a Cloudflare Worker backed by Vectorize and Workers AI."
confidence: 0.85
retrieval_class: "identity"
export_class: "internal"
tool_type: "api"
tool_status: "active"
system_fit: "department-local-tool"
contract_status: "pointer-only"
contract_reason: "The Worker and ingest scripts live in tools/anac-rag/ and tools/anac_ingest/. The retrieval doctrine already lives in knowledge/anac-legislacao/canon/core-doctrine.md and synthesis/lacunas-de-cobertura.md, so a separate tool-contract namespace would duplicate it."
departments: []
related_namespaces: ["anac-legislacao"]
party_slugs: []
client_slug: null
brand_slug: null
secret_refs:
  - "secret://anac-rag-token"
  - "secret://llm-api-key"
created: "2026-09-30"
---

# anac-rag

## What the tool does

Answers a natural-language question in Portuguese against the ANAC corpus and returns
small, citable chunks. It is a recall path, not the retrieval surface: the working tree and
the keyword index stay authoritative, and this sits in front of them.

Corpus: 285 documents (51 RBAC, 221 IS, 13 IAC) re-cut by `tools/anac_ingest/chunk.py` into
7,956 heading-aware windows, embedded with Workers AI `@cf/baai/bge-m3` (1024 dimensions),
and stored in a Vectorize index. Every chunk carries the exact fragment identifier it was
cut from, so a semantic hit resolves to the same fragment the keyword index would name.

## System fit class and boundary

System fit class: `department-local-tool`.

It may own the vector index, the chunk corpus, the query route, and the citation check. It
must never own canon, must never answer a normative question without a citable fragment, and
must never be the only retrieval path available.

## Deep contract linkage

There is no separate tool-contract namespace. The retrieval doctrine already lives in the
namespace that owns it: `knowledge/anac-legislacao/canon/core-doctrine.md` for the hard rules
and `knowledge/anac-legislacao/synthesis/lacunas-de-cobertura.md` for the 21 documents that
failed to ingest. A `knowledge/anac-rag-tool-contract/` would fork that doctrine out from
under its owner, so this pointer is `pointer-only`, matching `tools/anac-ingest.md`.

## Ownership

Owner: the `anac-legislacao` namespace. Operator-approved only; agents propose.

## Endpoints

| Route | Purpose |
|---|---|
| `POST /query` | Embed and retrieve cited chunks. No LLM needed. |
| `POST /chat` | Retrieve, then generate from any OpenAI-compatible LLM. |
| `GET /health` | Liveness. Unauthenticated, exposes no corpus content. |

## Commands

```bash
PY=./.venv/Scripts/python.exe

# Offline: chunk the corpus, no network and no credentials.
$PY tools/anac_ingest/chunk.py --dry-run --verify-cites
$PY tools/anac_ingest/chunk.py

# Embed and upsert. Credentials come from the environment, never from the repo.
$PY tools/anac_ingest/vectorize_ingest.py --dry-run
$PY tools/anac_ingest/vectorize_ingest.py --namespace anac-2026-09

# Prove corpus and query sides share one vector space.
$PY tools/anac_ingest/vectorize_ingest.py --probe 5

cd tools/anac-rag && npx wrangler dev --local
```

## Runtime and source location

| Piece | Location |
|---|---|
| Worker | `tools/anac-rag/` |
| Chunker | `tools/anac_ingest/chunk.py` |
| Ingest | `tools/anac_ingest/vectorize_ingest.py` |
| Shared parser | `tools/anac_ingest/segment.py` |
| Chunks | `knowledge/anac-legislacao/support/chunks/` |

## Auth and credential boundary

`POST /query` and `POST /chat` require `Authorization: Bearer <ANAC_RAG_TOKEN>`, set with
`npx wrangler secret put`. Values never appear in this repo; `secrets/` holds references
only. `LLM_API_KEY` is optional and only needed for a hosted provider.

CORS echoes only origins listed in `CORS_ORIGINS` and never sends `*`, because the API
requires a bearer.

## Risks and limitations

- **Remote service.** This is a network dependency. When Cloudflare is unreachable, fall
  back to `tools/anac_ingest/query.py`, which is the precision path and still works offline.
- **A deployed Worker cannot reach `127.0.0.1`.** If `LLM_BASE_URL` points at a local Ollama
  or LM Studio, the call fails with a connection error, not a helpful one. Use
  `npx wrangler dev --local`, a LAN or Tailscale address, or a hosted provider. With no LLM
  configured, `/chat` returns HTTP 200 with `mode: retrieval-only` and the full result set.
- **Free-tier ceiling.** Workers AI allows a daily neuron allowance. One full embed of the
  corpus is roughly 5,900 neurons against an allowance of about 10,000, so a full re-embed
  fits in a day but two do not. Ingest is incremental via
  `outputs/_runtime/anac-rag/state.json`.
- **No TTL, no partial delete.** Vectorize never expires a vector. An id orphaned by a
  changed chunking scheme would answer queries with text that no longer exists in the repo.
  Mitigations: structural (never content-derived) `chunk_id`, `--prune`, and namespace
  versioning as the nuclear option.
- **Quality is unmeasured on Portuguese legal register.** BGE-M3 is multilingual and covers
  Portuguese, but nobody has benchmarked it on this corpus. The regression set at
  `knowledge/anac-legislacao/support/chunks/eval-set.jsonl` exists so the next person to
  change a chunking parameter can tell whether they helped.
- **The rate limit is not a security control.** The per-isolate IP bucket is a runaway-loop
  guard only; isolates are ephemeral and distributed. The bearer token is the access control.
- **Retrieval is a pointer, not a source.** A vector hit still resolves to a fragment. Open
  the fragment YAML before quoting it, per `canon/core-doctrine.md` hard rule 2.

## Next integration step

A Worker deploy, then the nine-question retrieval check in
`knowledge/anac-legislacao/support/chunks/eval-set.jsonl`, before this pointer's
`confidence` rises above 0.85.