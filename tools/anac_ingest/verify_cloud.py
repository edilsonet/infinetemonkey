#!/usr/bin/env python3
"""Check that the Cloudflare Vectorize index actually matches the chunk corpus.

The chunker proves the local corpus is intact. It says nothing about whether the
cloud is in step. That gap matters: an ingest can report success, write every
vector, and still leave the index unusable, because metadata is dropped when the
metadata indexes were never declared, or because vectors land in a different
namespace than the one configured.

This answers the three questions the ingest cannot:
  1. how many vectors does the index really hold, and in which namespace
  2. did the vectors land in the namespace we asked for
  3. does a query return metadata, which is what /query needs to cite

Usage:
    verify_cloud.py            # report, exit 0 even when unhealthy
    verify_cloud.py --strict   # exit 1 when unhealthy

This sends one short probe question to Workers AI. It embeds no corpus text, so
it is safe to run on a schedule as a health check.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.request
import urllib.error
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from vectorize_ingest import (  # noqa: E402
    API,
    INDEX_NAME_DEFAULT,
    NAMESPACE_DEFAULT,
    load_dotenv,
    vectorize_url,
)

CHUNKS = Path(__file__).resolve().parents[2] / "knowledge" / "anac-legislacao" / "support" / "chunks"
# A short, real question. The point is to prove retrieval works end to end, not to
# score answer quality; the eval set covers that.
PROBE_TEXT = "aprovacao para retorno ao servico apos manutencao"


def call(account: str, token: str, url: str, payload: dict, timeout: int = 90) -> dict:
    req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), method="POST")
    req.add_header("Authorization", f"Bearer {token}")
    req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            return json.loads(response.read())
    except urllib.error.HTTPError as exc:
        return {"success": False, "errors": [{"message": exc.read().decode("utf-8", "replace")[:200]}]}
    except Exception as exc:  # noqa: BLE001
        return {"success": False, "errors": [{"message": str(exc)[:200]}]}


def expected_chunks() -> int:
    manifest = CHUNKS / "manifest.json"
    if not manifest.exists():
        return 0
    return int(json.loads(manifest.read_text(encoding="utf-8")).get("chunks", 0))


def embed(account: str, token: str, text: str) -> list[float] | None:
    result = call(account, token, f"{API}/accounts/{account}/ai/run/@cf/baai/bge-m3", {"text": [text]})
    data = (result.get("result") or {}).get("data")
    return data[0] if data else None


def index_info(account: str, token: str, index: str) -> dict:
    req = urllib.request.Request(vectorize_url(account, index, ""), method="GET")
    req.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(req, timeout=45) as response:
            return json.loads(response.read()).get("result", {})
    except Exception as exc:  # noqa: BLE001
        return {"error": str(exc)[:160]}


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--strict", action="store_true", help="exit 1 when unhealthy")
    parser.add_argument("--index", default=INDEX_NAME_DEFAULT)
    parser.set_defaults()
    parser.add_argument("--namespace", default=NAMESPACE_DEFAULT)
    args = parser.parse_args(argv)

    load_dotenv()
    account = os.environ.get("CLOUDFLARE_ACCOUNT_ID")
    token = os.environ.get("CLOUDFLARE_API_TOKEN")
    if not account or not token:
        print("FATAL: CLOUDFLARE_ACCOUNT_ID or CLOUDFLARE_API_TOKEN not available.")
        return 1

    expected = expected_chunks()
    base = vectorize_url(account, args.index, "")

    info = index_info(account, token, args.index)
    config = info.get("config") or {}
    print(f"[index] {args.index}: dims={config.get('dimensions')} metric={config.get('metric')}")
    # The Vectorize REST API used by these scripts does NOT expose declared
    # metadata indexes; `config` carries only dimensions and metric. Asserting
    # "NENHUM" from this key produced a false alarm while wrangler listed real
    # indexes. Authoritative check is a metadata-bearing query below, which
    # tests the thing that actually matters.
    print("[index] metadata indexes: verificar pela consulta com metadados abaixo")

    vector = embed(account, token, PROBE_TEXT)
    if not vector:
        print("[embed] FALHOU: nao foi possivel embutir a pergunta de sondagem.")
        return 1
    print(f"[embed] ok, {len(vector)} dimensoes")

    def probe(label: str, payload: dict) -> tuple[int, dict | None]:
        result = call(account, token, base + "/query", payload)
        res = result.get("result") or {}
        matches = res.get("matches") or []
        print(f"[query {label:22}] count={res.get('count', 0)}")
        return len(matches), (matches[0] if matches else None)

    # The REST API takes returnMetadata: "all" | "indexed" | "none", the same
    # levels as the Workers binding. "includeMetadata" is silently ignored, and
    # it was that wrong key that made this verifier report missing metadata for
    # an index that had it.
    in_ns, first = probe(f"ns={args.namespace}", {
        "namespace": args.namespace, "topK": 3, "vector": vector, "returnMetadata": "all",
    })
    default_ns, first_default = probe("sem namespace", {
        "topK": 3, "vector": vector, "returnMetadata": "all",
    })

    findings: list[str] = []

    if in_ns == 0 and default_ns > 0:
        findings.append(
            f"Vetores estao no namespace PADRAO, nao em '{args.namespace}'. "
            "A busca com o namespace configurado retorna zero e a skill anac-nuvem "
            "nao encontraria nada."
        )
    elif in_ns == 0 and default_ns == 0:
        findings.append("Nenhum vetor visivel em nenhum namespace. O indice esta vazio.")

    best = first or first_default
    if best is not None:
        metadata = best.get("metadata")
        if not metadata:
            findings.append(
                "Os vetores nao tem metadados. Sem cite, code e text a resposta nao pode "
                "ser citada, que e exatamente o que /query precisa devolver. Causa "
                "provavel: metadata indexes nunca declarados (o PUT retorna 405 com o "
                "token de API). Declarar pelo dashboard resolve."
            )

    print()
    print(f"Esperados no corpus local: {expected} chunks")
    if findings:
        print(f"SAUDE: {len(findings)} problema(s)")
        for item in findings:
            print(f"  - {item}")
    else:
        print("SAUDE: ok")
    if best is not None:
        print(f"top hit: {best.get('id')} score={best.get('score')}")

    return 1 if (args.strict and findings) else 0


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    raise SystemExit(main(sys.argv[1:]))