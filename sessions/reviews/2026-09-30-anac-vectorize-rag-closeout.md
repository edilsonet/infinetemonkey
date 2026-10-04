---
id: "session-2026-09-30-anac-vectorize-rag-closeout"
aliases: ["session-2026-09-30-anac-vectorize-rag-closeout"]
type: "Doc"
namespace: "anac-legislacao"
lifecycle_state: "research"
summary: "Closeout review for the ANAC Cloudflare Vectorize semantic RAG layer."
confidence: 0.9
retrieval_class: "identity"
export_class: "internal"
created: "2026-09-30"
---

# Closeout: ANAC Vectorize RAG layer

## What was built

A semantic retrieval layer over the ANAC corpus, sitting in front of the existing keyword
index rather than replacing it.

| Piece | Location |
|---|---|
| Shared parser (stdlib only) | `tools/anac_ingest/segment.py` |
| Chunker | `tools/anac_ingest/chunk.py` |
| Embed and upsert | `tools/anac_ingest/vectorize_ingest.py` |
| Worker | `tools/anac-rag/` |
| Tool pointer | `tools/anac-rag.md` |
| Chunk corpus | `knowledge/anac-legislacao/support/chunks/` |
| Regression set | `knowledge/anac-legislacao/support/chunks/eval-set.jsonl` |

Result: 285 documents re-cut into **7,956** chunks (1,909 RBAC, 5,919 IS, 128 IAC), 16,968,035
characters, median 740 estimated tokens, maximum 2,328.

## Decisions made

1. **Workers AI `@cf/baai/bge-m3` for corpus and queries alike.** A deployed Worker cannot
   reach a local Ollama, so a local embedding model would have forced query-side embedding
   onto the operator machine too. One model on both sides removes the silent-mismatch risk
   that produces plausible-looking but wrong rankings.
2. **Re-chunk rather than embed the existing fragments.** The 33,959 fragments are the
   parse product: median 186 characters, 30% under 100. They are citations, not prose.
3. **Chunk boundaries land on citation boundaries**, so `cite` is exact rather than
   approximate. Every one of 36,138 citations resolves against the fragment index.
4. **Keyword index stays.** It is the precision path and works offline; the Worker is recall.
   `_system/retrieval-load-order-policy.md` Rule LOAD-1 now names both.

## Wrong turns worth keeping

- **Duplicate chunk ids, caught only after writing.** The first run produced 9,163 chunks but
  only 7,920 unique ids, because `fragment_blocks` emits repeated blocks (a table of contents
  or a repeated page header) that `fragment_document` dedupes afterwards. The chunker
  inherited that. Vectorize upserts by id, so 1,243 chunks would have silently overwritten
  each other. Fixed by deduping blocks in the chunker and putting `chunk_index` in the id.
  Lesson: the dry-run summary printed a plausible chunk count and hid it. Only counting
  *unique* ids caught it.
- **One 36,567-character window.** The first `window()` could exceed its own budget when a
  single paragraph was longer than the target, because the oversized-paragraph branch
  hard-split on lines without re-checking line length. bge-m3 accepts 8,192 tokens; that
  window would have been 11,796. Fixed with word-boundary splitting.
- **Em-dash validation failure from a scratch clone.** Cloning `affaan-m/ECC` into
  `outputs/_runtime/ecc` failed `validate.sh`, because that path is pruned from the node walk
  but not from the dash grep. Not a code defect: the clone was gitignored scratch. Removed.
- **Two classifier denials, both correct.** A `rm -rf` on a path that did not yet exist, and
  an edit to the out-of-repo user skill. The first was unnecessary; the second means
  `C:\Users\edils\.claude\skills\anac-legislacao\SKILL.md` is still keyword-only and needs the
  operator's explicit go-ahead before it learns about `/query`.

## Verified

| Check | Result |
|---|---|
| `bash _system/validate.sh` | exit 0, same 12 baseline warnings, 244 node files |
| Fragmenter refactor | all 33,959 fragments regenerate byte-identical (text and cite) |
| `import ingest` in stock venv | works; `bs4` now imported lazily |
| Chunker citations | 36,138 cites, 0 unresolved |
| Chunker ids | 7,956 unique, 0 collisions |
| Chunk sizes | median 740 tokens, max 2,328, 0 over 8,192 |
| Chunker idempotency | id and content digests identical across two runs |
| `tool-three-layer-standard-check.sh` | pass |

## Not verified, and why

- **No Cloudflare account was configured**, so nothing was embedded, upserted, or deployed.
  The cost figure (~5,880 neurons against a ~10,000 daily allowance) is computed from
  published pricing and the measured corpus size, not observed.
- **`npx wrangler` was blocked** by the sandbox classifier, so the Worker is unbuilt and
  untyped. The TypeScript has not been compiled.
- **bge-m3 quality on Portuguese legal register is unmeasured.** This is the largest open
  unknown. The nine-question eval set exists so the next person to change a chunk parameter
  can tell whether they helped.

## Memory candidates

- Vectorize and Workers AI both key on id, so an id scheme must be structural, never
  content-derived, because neither has a TTL or partial delete.
- `fragment_blocks` is not deduplicated. Anything consuming raw section output must dedupe
  before using block ids as keys.

## Follow-ups

1. Set `CLOUDFLARE_API_TOKEN` and `CLOUDFLARE_ACCOUNT_ID`, run `vectorize_ingest.py`, deploy
   the Worker, then run the nine-question eval set.
2. Run `rag-pipeline-reviewer` against the live pipeline before raising the tool pointer's
   confidence above 0.85.
3. Amend `knowledge/ai-architecture/pillars/retrieval-over-raw-memory.md`, which still says
   there is no vector store. It is ai-architecture canon and needs operator sign-off; keep it
   a separate commit so it can be dropped.
4. Update the out-of-repo user skill `~/.claude/skills/anac-legislacao/SKILL.md` once
   authorized.
5. A company registry corpus (RBAC 135 operators by COA) is absent from this brain. The
   corpus holds the norm, not the operator directory.

## Human review requirements

- The ai-architecture pillar amendment (item 3).
- Deploying anything to a paid Cloudflare account.

## Usage receipt

- `usage_capture_status`: unavailable. Claude Code desktop does not expose per-session token
  or cost totals to the shell, and no provider-side lookup surface was available. The
  `mcp__ccd_session_mgmt__get_usage` surface reports plan limits, not per-session totals for
  this run.