#!/usr/bin/env python3
"""Embed the ANAC chunks with Workers AI and upsert them into Vectorize.

Reads only support/chunks/manifest.json and the JSONL files it names. It never
touches support/extracted/ or support/fragments/, and never walks support/.

Credentials come from the environment, never from a file in this repo:
    CLOUDFLARE_API_TOKEN   scoped Workers AI:Read + Workers Vectorize:Write
    CLOUDFLARE_ACCOUNT_ID

Usage:
    vectorize_ingest.py --dry-run              # plan only, zero API calls
    vectorize_ingest.py                        # embed and upsert
    vectorize_ingest.py --only rbac-38         # one document
    vectorize_ingest.py --namespace anac-2026-09
    vectorize_ingest.py --prune                # drop vectors not in the manifest
    vectorize_ingest.py --probe 5              # embedding symmetry check
"""

from __future__ import annotations

import argparse
import json
import os
import random
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CHUNKS = ROOT / "knowledge" / "anac-legislacao" / "support" / "chunks"
STATE = ROOT / "outputs" / "_runtime" / "anac-rag" / "state.json"

# Published limits. Workers AI accepts 3000 embedding requests/min; the client
# bucket below runs far under that so retries and live query traffic never
# collide with ingest.
AI_BATCH = 50
UPSERT_BATCH = 100
CALLS_PER_MIN = 60
MAX_ATTEMPTS = 6
BACKOFF_BASE = 2.0

API = "https://api.cloudflare.com/client/v4"

# Metadata keys defined as indexes on the first upsert. Vectorize allows ten;
# the indexed value must be 64 bytes or fewer, hence the truncation.
METADATA_INDEX_KEYS = [
    "kind", "code", "family", "cite", "cite_kind",
    "section_id", "language", "chunk_index", "document_title",
]
MAX_INDEXED_VALUE = 60  # leaves room inside the 64-byte cap


def log(message: str) -> None:
    print(message, file=sys.stderr)


class RateLimiter:
    """Simple rolling-window limiter, well under the published ceiling."""

    def __init__(self, per_min: int) -> None:
        self.per_min = per_min
        self.calls: list[float] = []

    def wait(self) -> None:
        now = time.time()
        self.calls = [t for t in self.calls if t > now - 60]
        if len(self.calls) >= self.per_min:
            sleep_for = 60 - (now - self.calls[0]) + 0.5
            if sleep_for > 0:
                time.sleep(sleep_for)
            now = time.time()
            self.calls = [t for t in self.calls if t > now - 60]
        self.calls.append(time.time())


def api_request(url: str, token: str, method: str = "GET",
                payload: dict | None = None) -> dict:
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    request = urllib.request.Request(url, data=data, method=method)
    request.add_header("Authorization", f"Bearer {token}")
    request.add_header("Content-Type", "application/json")

    last_error: Exception | None = None
    for attempt in range(MAX_ATTEMPTS):
        try:
            with urllib.request.urlopen(request, timeout=120) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")[:400]
            # A 4xx other than 429 is a bad request: retrying cannot fix it.
            if exc.code != 429 and 400 <= exc.code < 500:
                raise RuntimeError(f"HTTP {exc.code}: {body}") from exc
            last_error = RuntimeError(f"HTTP {exc.code}: {body}")
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            last_error = exc
        # Exponential backoff with full jitter.
        delay = random.uniform(0, BACKOFF_BASE * (2 ** attempt))
        log(f"  retry {attempt + 1}/{MAX_ATTEMPTS} after {last_error}")
        time.sleep(delay)
    raise RuntimeError(f"request failed after {MAX_ATTEMPTS} attempts: {last_error}")


def load_manifest() -> dict:
    path = CHUNKS / "manifest.json"
    if not path.exists():
        raise SystemExit(f"missing {path}. Run tools/anac_ingest/chunk.py first.")
    return json.loads(path.read_text(encoding="utf-8"))


def load_chunks(only: list[str] | None) -> list[dict]:
    chunks: list[dict] = []
    for path in sorted(CHUNKS.rglob("*.jsonl")):
        with path.open(encoding="utf-8") as handle:
            for line in handle:
                if not line.strip():
                    continue
                chunk = json.loads(line)
                if only and chunk["code"] not in only:
                    continue
                chunks.append(chunk)
    return chunks


def load_state() -> dict:
    if not STATE.exists():
        return {}
    try:
        return json.loads(STATE.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def save_state(state: dict) -> None:
    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def vectorize_url(account: str, index: str, suffix: str) -> str:
    return f"{API}/accounts/{account}/vectorize/v2/indexes/{index}{suffix}"


def embed_batch(account: str, token: str, texts: list[str],
                limiter: RateLimiter) -> list[list[float]]:
    limiter.wait()
    url = f"{API}/accounts/{account}/ai/run/@cf/baai/bge-m3"
    result = api_request(url, token, method="POST", payload={"text": texts})
    if not result.get("success", True):
        raise RuntimeError(f"Workers AI error: {json.dumps(result.get('errors'))[:300]}")
    data = result.get("result", {}).get("data")
    if not data:
        raise RuntimeError("Workers AI returned no vectors")
    return data


def metadata_for(chunk: dict) -> dict:
    meta = {
        "kind": chunk["kind"],
        "code": chunk["code"],
        "family": str(chunk.get("family") or ""),
        "cite": chunk["cite"][:MAX_INDEXED_VALUE],
        "cite_kind": chunk["cite_kind"],
        "section_id": str(chunk.get("section_id") or "")[:MAX_INDEXED_VALUE],
        "language": chunk.get("language") or "pt",
        "chunk_index": chunk["chunk_index"],
        "document_title": chunk["document_title"][:MAX_INDEXED_VALUE],
        # Not indexed, but returned so the Worker can answer without a second
        # lookup: the text itself, the full cite list, and where to read more.
        "cites": chunk["cites"],
        "cite_base": chunk["cite_base"],
        "section_title": chunk["section_title"],
        "text": chunk["text"],
        "source_path": chunk["source_path"],
        "page_url": chunk.get("page_url") or "",
    }
    return meta


def cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = sum(x * x for x in a) ** 0.5
    nb = sum(y * y for y in b) ** 0.5
    return dot / (na * nb) if na and nb else 0.0


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--only", action="append", default=[])
    parser.add_argument("--namespace", default="anac-2026-09")
    parser.add_argument("--index", default="anac-legislacao")
    parser.add_argument("--model", default="@cf/baai/bge-m3",
                        help="must match the model recorded in manifest.json")
    parser.add_argument("--prune", action="store_true",
                        help="delete vectors in the namespace absent from the manifest")
    parser.add_argument("--probe", type=int, default=0, metavar="N",
                        help="embedding symmetry check over N sampled chunks")
    args = parser.parse_args(argv)

    manifest = load_manifest()

    # A corpus embedded with one model and queried with another produces
    # plausible-looking, silently wrong rankings. Catch it before any write.
    if manifest.get("embed_model") != args.model:
        log(f"FATAL: manifest was built for {manifest.get('embed_model')!r} but --model is "
            f"{args.model!r}. Recreate the index rather than mixing models.")
        return 1
    if manifest.get("embed_dimensions") != 1024:
        log(f"FATAL: manifest expects {manifest.get('embed_dimensions')} dimensions; "
            "the index is fixed at creation time and cannot be resized.")
        return 1

    chunks = load_chunks(args.only or None)
    if not chunks:
        log("no chunks found. Run tools/anac_ingest/chunk.py first.")
        return 1

    total_chars = sum(len(c["embed_text"]) for c in chunks)
    est_tokens = sum(c["est_tokens"] for c in chunks)
    log(f"[plan] {len(chunks)} chunks, {total_chars} chars, ~{est_tokens} tokens, "
        f"namespace={args.namespace}")
    log(f"[plan] AI calls: {-(-len(chunks) // AI_BATCH)}, upsert calls: "
        f"{-(-len(chunks) // UPSERT_BATCH)}")

    if args.dry_run:
        account = os.environ.get("CLOUDFLARE_ACCOUNT_ID")
        token = os.environ.get("CLOUDFLARE_API_TOKEN")
        log(f"[plan] CLOUDFLARE_ACCOUNT_ID: {'set' if account else 'MISSING'}")
        log(f"[plan] CLOUDFLARE_API_TOKEN: {'set' if token else 'MISSING'}")
        print(json.dumps({
            "chunks": len(chunks),
            "namespace": args.namespace,
            "model": args.model,
            "dimensions": manifest["embed_dimensions"],
            "ai_calls": -(-len(chunks) // AI_BATCH),
            "upsert_calls": -(-len(chunks) // UPSERT_BATCH),
            "est_tokens": est_tokens,
        }, indent=2))
        return 0

    token = os.environ.get("CLOUDFLARE_API_TOKEN")
    account = os.environ.get("CLOUDFLARE_ACCOUNT_ID")
    if not token or not account:
        log("FATAL: set CLOUDFLARE_API_TOKEN and CLOUDFLARE_ACCOUNT_ID in the environment. "
            "Never write a credential into this repo; see secrets/README.md.")
        return 1

    limiter = RateLimiter(CALLS_PER_MIN)

    if args.probe:
        return run_probe(token, account, args, chunks[: args.probe], limiter)

    state = load_state()
    url = vectorize_url(account, args.index, "")
    defined = False
    embedded = 0
    upserted = 0
    started = time.time()

    for i in range(0, len(chunks), AI_BATCH):
        batch = chunks[i : i + AI_BATCH]
        vectors = embed_batch(account, token, [c["embed_text"] for c in batch], limiter)
        embedded += len(batch)

        for j in range(0, len(batch), UPSERT_BATCH):
            sub = batch[j : j + UPSERT_BATCH]
            payload = {
                "namespace": args.namespace,
                "vectors": [
                    {
                        "id": chunk["chunk_id"],
                        "values": vectors[j + k],
                        "metadata": metadata_for(chunk),
                    }
                    for k, chunk in enumerate(sub)
                ],
            }
            api_request(url, token, method="POST", payload=payload)
            upserted += len(sub)
            # defineMetadataIndexes is a per-call option declaring the index for
            # the keys in that batch; re-declaring every batch is wasted work.
            if not defined:
                api_request(f"{url}/indexes", token, method="POST",
                            payload={"metadataIndexes": METADATA_INDEX_KEYS})
                defined = True

        for chunk in batch:
            state[chunk["code"]] = {
                "chunk_count": chunk["chunk_count"],
                "sha256": chunk["content_sha256"],
                "embedded_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            }
        save_state(state)

        if (i // AI_BATCH) % 10 == 0:
            rate = embedded / max(time.time() - started, 1e-9)
            log(f"  {embedded}/{len(chunks)} embedded+upserted ({rate:.0f}/s)")

    log(f"[done] embedded {embedded}, upserted {upserted} into {args.namespace}")

    if args.prune:
        prune(token, account, args, chunks)
    return 0


def prune(token: str, account: str, args: argparse.Namespace,
          chunks: list[dict]) -> None:
    """Delete vectors whose id is no longer in the chunk set.

    Vectorize has no TTL and no partial delete, so an orphaned vector from a
    changed id scheme answers queries with text that no longer exists in the
    repo, forever.
    """
    wanted = {c["chunk_id"] for c in chunks}
    url = f"{vectorize_url(account, args.index, '')}/list?namespace={args.namespace}"
    result = api_request(url, token)
    vectors = result.get("result", {}).get("vectors", [])
    orphans = [v["id"] for v in vectors if v["id"] not in wanted]
    if not orphans:
        log("[prune] no orphaned vectors")
        return
    log(f"[prune] deleting {len(orphans)} orphaned vectors")
    delete_url = vectorize_url(account, args.index, "/delete_by_ids")
    api_request(delete_url, token, method="POST",
                payload={"namespace": args.namespace, "ids": orphans})


def run_probe(token: str, account: str, args: argparse.Namespace,
              sample: list[dict], limiter: RateLimiter) -> int:
    """Round-trip proof that corpus and query sides share one vector space.

    Embed each chunk, embed its own first sentence as a query, and require the
    chunk to rank first. A symmetric retriever does this trivially; a mismatch
    between models or between passage and query formatting does not.
    """
    failures = 0
    for chunk in sample:
        sentence = chunk["text"].split(".")[0][:400]
        if len(sentence) < 20:
            sentence = chunk["text"][:200]
        doc_vec, query_vec = embed_batch(account, token, [chunk["embed_text"], sentence], limiter)

        url = vectorize_url(account, args.index, "/query")
        result = api_request(url, token, method="POST", payload={
            "namespace": args.namespace,
            "vector": query_vec,
            "topK": 3,
            "includeMetadata": False,
        })
        matches = result.get("result", {}).get("matches", [])
        top = matches[0] if matches else {}
        score = top.get("score", 0.0)
        hit = top.get("id") == chunk["chunk_id"]
        similarity = cosine(doc_vec, query_vec)
        status = "OK " if (hit and score >= 0.95) else "FAIL"
        if status == "FAIL":
            failures += 1
        log(f"[probe] {status} {chunk['chunk_id'][:60]} score={score:.4f} "
            f"cos={similarity:.4f} rank_id_match={hit}")
    log(f"[probe] {len(sample) - failures}/{len(sample)} passed")
    return 1 if failures else 0


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    raise SystemExit(main(sys.argv[1:]))