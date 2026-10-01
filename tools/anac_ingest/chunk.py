#!/usr/bin/env python3
"""Cut the ANAC corpus into embeddable, citable chunks.

The 33,959 existing fragments are the *parse* product: the median one is 186
characters and roughly a third are under 100, because RBAC subclauses like
"43.1(a)" are bare citations with no prose to embed. An embedding model
wants a few hundred tokens of meaningful text.

So this does not embed fragments. It re-reads the 285 full documents under
support/extracted/, sectionizes them with the same parser the fragmenter uses
(segment.fragment_blocks), and packs whole *citation blocks* into windows.
Because a window boundary always lands on a citation boundary, every chunk
carries an exact `cite` rather than an approximate one. That is what makes the
downstream RAG answer citable, per knowledge/anac-legislacao/canon/core-doctrine.md
hard rule 2.

Usage:
    chunk.py --dry-run                 # plan only, no writes
    chunk.py                           # write support/chunks/
    chunk.py --only rbac-38            # one document
    chunk.py --verify-cites --strict   # audit citations, exit 1 on failure
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
import segment  # noqa: E402

try:  # pragma: no cover - depends on the local PyYAML build
    from yaml import CSafeLoader as _Loader  # type: ignore[attr-defined]
except ImportError:  # pragma: no cover
    _Loader = yaml.SafeLoader

ROOT = Path(__file__).resolve().parents[2]
SUPPORT = ROOT / "knowledge" / "anac-legislacao" / "support"
CATALOGS = SUPPORT / "catalogs"
EXTRACTED = SUPPORT / "extracted"
FRAGMENTS = SUPPORT / "fragments"
INDEXES = SUPPORT / "indexes"
CHUNKS = SUPPORT / "chunks"
QUARANTINE = ROOT / "outputs" / "quarantine" / "chunks"

# Window shape. TARGET_CHARS is tuned for Portuguese legal prose, where a
# character is worth roughly a third of a token; 3000 chars lands near 970
# tokens, inside bge-m3's comfortable input range.
TARGET_CHARS = 3000
MIN_CHARS = 400
OVERLAP_CHARS = 450
MAX_CITATIONS = 8
SPLIT_RATIO = 1.3
CHARS_PER_TOKEN = 3.1

CHUNKER_VERSION = 1
# Stamped into every chunk so a later model swap is visible in the data rather
# than inferred. Must match the Worker.
EMBED_MODEL = "@cf/baai/bge-m3"
EMBED_DIMENSIONS = 1024


class CitableError(Exception):
    """A chunk could not be attributed to a real fragment of its document."""


def log(message: str) -> None:
    print(message, file=sys.stderr)


def load_yaml(path: Path) -> dict:
    if not path.exists():
        return {}
    return yaml.load(path.read_text(encoding="utf-8"), Loader=_Loader) or {}


def iter_documents(only: list[str] | None) -> list[dict]:
    """Every successfully ingested document, read from the catalogs.

    Iterating the catalog rather than walking support/ is deliberate: the tree
    holds 35,000 files and a recursive walk over it on NTFS times out. This
    costs 285 stat calls.
    """
    rows: list[dict] = []
    for kind in ("rbac", "is", "iac"):
        catalog = load_yaml(CATALOGS / f"{kind}.yml")
        for item in catalog.get("items", []):
            code = item.get("code")
            if not code:
                continue
            if only and code not in only:
                continue
            if not (EXTRACTED / kind / f"{code}.md").exists():
                continue
            rows.append({
                "kind": kind,
                "code": code,
                "family": item.get("family") or "",
                "title": item.get("title") or code,
                "ementa": item.get("ementa") or "",
                "publication_date": item.get("publication_date") or "",
                "page_url": item.get("page_url") or "",
                "pdf_url": item.get("pdf_url") or "",
            })
    return rows


def window(text: str, size: int, overlap: int) -> list[str]:
    """Split on paragraph boundaries, never mid-paragraph.

    A paragraph longer than `size` is hard-split on line boundaries, and then on
    word boundaries if a single line still exceeds `size`, so the result is
    always under budget. bge-m3 accepts 8192 tokens, but a window far above that
    is both expensive and useless as a retrieval unit.
    """
    paragraphs = [p for p in text.split("\n\n") if p.strip()]
    out: list[str] = []
    buf: list[str] = []
    length = 0

    def hard_split(block: str) -> list[str]:
        pieces: list[str] = []
        current: list[str] = []
        current_len = 0
        for line in block.split("\n"):
            while len(line) > size:
                head, line = line[:size], line[size:]
                if current:
                    pieces.append("\n".join(current))
                    current, current_len = [], 0
                pieces.append(head)
            if current_len + len(line) > size and current:
                pieces.append("\n".join(current))
                current, current_len = [], 0
            current.append(line)
            current_len += len(line) + 1
        if current:
            pieces.append("\n".join(current))
        return [p for p in pieces if p.strip()]

    def flush() -> None:
        nonlocal buf, length
        if buf:
            out.append("\n\n".join(buf))
            buf, length = [], 0

    for para in paragraphs:
        if len(para) > size:
            flush()
            pieces = hard_split(para)
            for i, piece in enumerate(pieces):
                out.append(piece)
                # Overlap forward from the tail of this piece so a requirement
                # split across the break stays retrievable from the next one.
                if i < len(pieces) - 1:
                    tail = piece[-overlap:]
                    if tail.strip():
                        out.append(tail)
            continue
        if length + len(para) > size and buf:
            flush()
            # Carry the tail of the previous paragraphs forward as overlap.
            tail: list[str] = []
            tail_len = 0
            for prev in reversed(buf):
                if tail_len + len(prev) > overlap:
                    break
                tail.insert(0, prev)
                tail_len += len(prev)
            buf, length = list(tail), tail_len
        buf.append(para)
        length += len(para) + 2
    if buf:
        out.append("\n\n".join(buf))
    return [w.strip() for w in out if w.strip()]


def build_chunk(blocks: list[dict], window_index: int, window_count: int,
                doc: dict, preamble: str, chunk_index: int,
                chunk_count: int) -> dict:
    text = "\n\n".join(b["text"] for b in blocks).strip()
    cites: list[str] = []
    for block in blocks:
        cite = block["cite"]
        if cite not in cites:
            cites.append(cite)

    first = blocks[0]
    cite = first["cite"]
    if window_count > 1:
        cite = f"{cite} (janela {window_index + 1})"

    section_title = first["section_title"]
    title = first["title"]
    display_prefix = "" if len(cites) == 1 else f"{cites[0]} a {cites[-1]}: "
    text_out = display_prefix + text
    if preamble:
        text_out = preamble + "\n\n" + text_out

    # The embed side carries the document and section title because an IS
    # sub-clause like "5.1" carries no meaning without "IS 43-001".
    embed_text = f"{doc['title']} - {title}\n{text_out}"

    return {
        # Document-scoped and structural, never content-derived: two runs over
        # an unchanged document must produce identical ids so a Vectorize upsert
        # is idempotent. chunk_index disambiguates windows that happen to open on
        # the same block.
        "chunk_id": f"{doc['kind']}:{doc['code']}:c{chunk_index}:{first['id']}",
        "chunk_index": chunk_index,
        "window_index": window_index,
        "window_count": window_count,
        "cite": cite,
        "cite_base": first["cite"],
        "cites": cites,
        "cite_kind": "fragment",
        "kind": doc["kind"],
        "code": doc["code"],
        "family": doc["family"],
        "document_title": doc["title"],
        "ementa": doc["ementa"],
        "publication_date": doc["publication_date"],
        "page_url": doc["page_url"],
        "pdf_url": doc["pdf_url"],
        "source_path": f"knowledge/anac-legislacao/support/extracted/{doc['kind']}/{doc['code']}.md",
        "section_id": first["section_id"],
        "section_title": section_title,
        "subsection_id": first["subsection_id"],
        "language": "pt",
        "keywords": segment.keywords_for(first),
        "categories": segment.CATEGORY_BY_FAMILY.get(doc["family"], []),
        "has_preamble": bool(preamble),
        "preamble_chars": len(preamble),
        "text_chars": len(text_out),
        "est_tokens": round(len(text_out) / CHARS_PER_TOKEN),
        "content_sha256": hashlib.sha256(text_out.encode("utf-8")).hexdigest(),
        "text": text_out,
        "embed_text": embed_text,
        "parser_version": segment.PARSER_VERSION,
        "chunker_version": CHUNKER_VERSION,
        "embed_model": EMBED_MODEL,
        "embed_dimensions": EMBED_DIMENSIONS,
    }


def pack_document(doc: dict, blocks: list[dict], preamble: str) -> list[dict]:
    """Pack citation blocks into windows, splitting oversized blocks."""
    packed: list[dict] = []
    buf: list[dict] = []
    buf_len = 0

    def flush() -> None:
        nonlocal buf, buf_len
        if buf:
            packed.append((buf, 0, 1))
            buf, buf_len = [], 0

    for block in blocks:
        body = block["text"]
        if len(body) > TARGET_CHARS * SPLIT_RATIO:
            flush()
            pieces = window(body, TARGET_CHARS, OVERLAP_CHARS)
            for i, piece in enumerate(pieces):
                synthetic = dict(block)
                synthetic["text"] = piece
                packed.append(([synthetic], i, len(pieces)))
            continue
        buf.append(block)
        buf_len += len(body)
        if buf_len >= TARGET_CHARS or len(buf) >= MAX_CITATIONS:
            flush()
    flush()

    chunks: list[dict] = []
    total = len(packed)
    for i, (blocks_i, window_index, window_count) in enumerate(packed):
        chunks.append(build_chunk(
            blocks_i, window_index, window_count, doc,
            preamble if i == 0 else "", i, total,
        ))
    return chunks


def assert_citable(chunk: dict, doc_cites: set[str]) -> None:
    if not chunk["cite_base"]:
        raise CitableError(f"{chunk['chunk_id']}: empty cite")
    if chunk["cite_base"] not in doc_cites:
        raise CitableError(
            f"{chunk['chunk_id']}: cite {chunk['cite_base']!r} is not a fragment of {chunk['code']}"
        )
    if len(chunk["cites"]) > MAX_CITATIONS:
        raise CitableError(f"{chunk['chunk_id']}: {len(chunk['cites'])} citations exceeds {MAX_CITATIONS}")


def chunk_document(doc: dict) -> tuple[list[dict], list[str]]:
    path = EXTRACTED / doc["kind"] / f"{doc['code']}.md"
    header = segment.read_extracted_header(path)
    if header.get("title"):
        doc["title"] = header["title"]
    if header.get("ementa"):
        doc["ementa"] = header["ementa"]
    if header.get("page_url"):
        doc["page_url"] = header["page_url"]

    text = segment.clean_legal_text(segment.read_extracted_text(path))
    blocks = segment.fragment_blocks(doc["kind"], doc["code"], doc["family"], text)

    # A sumario or a repeated page header emits the same block twice. fragment
    # dedupes these away; the chunker must too, otherwise two windows can open
    # on the same block id and collide in Vectorize.
    deduped: dict[str, dict] = {}
    for block in blocks:
        prev = deduped.get(block["id"])
        if prev is None or len(block["text"]) > len(prev["text"]):
            deduped[block["id"]] = block
    blocks = list(deduped.values())

    doc_cites = {b["cite"] for b in blocks}

    # Every document opens with one preamble block that carries no citation of
    # its own. Emitting it alone would produce chunks nothing can cite, so it is
    # folded into the first window as context.
    preamble = ""
    if blocks and blocks[0]["section_id"] == "preambulo":
        preamble = blocks[0]["text"].strip()[:600]
        blocks = blocks[1:]

    if not blocks or len(text) < MIN_CHARS:
        # A document too small to section becomes one citable-by-title chunk.
        body = text or doc["title"]
        return [{
            "chunk_id": f"{doc['kind']}:{doc['code']}:document:w0",
            "chunk_index": 0, "window_index": 0, "window_count": 1,
            "cite": doc["title"],
            "cite_base": doc["title"],
            "cites": [doc["title"]],
            "cite_kind": "document",
            "kind": doc["kind"], "code": doc["code"], "family": doc["family"],
            "document_title": doc["title"], "ementa": doc["ementa"],
            "publication_date": doc["publication_date"],
            "page_url": doc["page_url"], "pdf_url": doc["pdf_url"],
            "source_path": f"knowledge/anac-legislacao/support/extracted/{doc['kind']}/{doc['code']}.md",
            "section_id": "", "section_title": doc["title"], "subsection_id": "",
            "language": "pt",
            "keywords": segment.CATEGORY_BY_FAMILY.get(doc["family"], []),
            "categories": segment.CATEGORY_BY_FAMILY.get(doc["family"], []),
            "has_preamble": False, "preamble_chars": 0,
            "text_chars": len(body),
            "est_tokens": round(len(body) / CHARS_PER_TOKEN),
            "content_sha256": hashlib.sha256(body.encode("utf-8")).hexdigest(),
            "text": body,
            "embed_text": f"{doc['title']}\n{body}",
            "parser_version": segment.PARSER_VERSION,
            "chunker_version": CHUNKER_VERSION,
            "embed_model": EMBED_MODEL,
            "embed_dimensions": EMBED_DIMENSIONS,
        }], []

    chunks = pack_document(doc, blocks, preamble)
    errors: list[str] = []
    for chunk in chunks:
        try:
            assert_citable(chunk, doc_cites)
        except CitableError as exc:
            errors.append(str(exc))
    return chunks, errors


def verify_cites(chunks: list[dict]) -> tuple[int, list[str]]:
    """Cross-check every chunk cite against the committed fragment index.

    chunk.py builds windows from the same parser that produced the fragments,
    so an unresolvable cite should be impossible. This is the independent check
    that catches drift between the two.
    """
    index = load_yaml(INDEXES / "fragment-index.yml")
    known = {
        str(entry.get("cite"))
        for entry in (index.get("fragments") or {}).values()
        if isinstance(entry, dict) and entry.get("cite")
    }
    failures: list[str] = []
    checked = 0
    for chunk in chunks:
        for cite in chunk["cites"]:
            checked += 1
            if cite not in known:
                failures.append(f"{chunk['chunk_id']}: cite {cite!r} not in fragment-index")
    return checked, failures


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="plan only, no writes")
    parser.add_argument("--only", action="append", default=[], help="restrict to a document code")
    parser.add_argument("--verify-cites", action="store_true", help="audit cites against the fragment index")
    parser.add_argument("--strict", action="store_true", help="exit 1 on any verification failure")
    parser.add_argument("--quiet", action="store_true", help="suppress per-document progress")
    args = parser.parse_args(argv)

    started = time.time()
    documents = iter_documents(args.only or None)
    if not documents:
        log("no documents matched")
        return 1

    all_chunks: list[dict] = []
    quarantined: list[dict] = []
    by_kind: dict[str, int] = {}
    total_chars = 0

    for doc in documents:
        try:
            chunks, errors = chunk_document(doc)
        except Exception as exc:  # noqa: BLE001 - one bad document must not stop the run
            log(f"[{doc['kind']}:{doc['code']}] ERROR {exc}")
            quarantined.append({"code": doc["code"], "error": str(exc)})
            continue
        bad = [c for c in chunks if c["chunk_id"] in set(errors)]
        good = [c for c in chunks if c["chunk_id"] not in set(errors)]
        if bad:
            stamp = time.strftime("%Y-%m-%d")
            dest = QUARANTINE / stamp
            dest.mkdir(parents=True, exist_ok=True)
            (dest / f"{doc['code']}.json").write_text(
                json.dumps({"document": doc, "errors": errors}, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            quarantined.extend({"code": doc["code"], "error": e} for e in errors)
        all_chunks.extend(good)
        by_kind[doc["kind"]] = by_kind.get(doc["kind"], 0) + len(good)
        doc_chars = sum(c["text_chars"] for c in good)
        total_chars += doc_chars
        if not args.quiet:
            log(f"[{doc['kind']}:{doc['code']}] chars={doc_chars} chunks={len(good)}")

    log(f"[done] {len(documents)} documents, {len(all_chunks)} chunks, "
        f"{len(quarantined)} quarantined, {time.time() - started:.1f}s")

    verified = 0
    failures: list[str] = []
    if args.verify_cites:
        verified, failures = verify_cites(all_chunks)
        log(f"[verify-cites] checked {verified} cites, {len(failures)} unresolved")
        for failure in failures[:10]:
            log(f"  {failure}")

    if args.dry_run:
        manifest = {
            "generated": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "dry_run": True,
            "chunker_version": CHUNKER_VERSION,
            "parser_version": segment.PARSER_VERSION,
            "embed_model": EMBED_MODEL,
            "embed_dimensions": EMBED_DIMENSIONS,
            "target_chars": TARGET_CHARS,
            "min_chars": MIN_CHARS,
            "overlap_chars": OVERLAP_CHARS,
            "max_citations": MAX_CITATIONS,
            "documents": len(documents),
            "chunks": len(all_chunks),
            "by_kind": by_kind,
            "total_chars": total_chars,
            "quarantined": len(quarantined),
            "verify_cites": "pass" if not failures else "fail",
            "cites_verified": verified,
        }
        print(json.dumps(manifest, ensure_ascii=False, indent=2))
        if args.strict and (failures or quarantined):
            return 1
        return 0

    # Group by document so each file is written once, and chunk_index is
    # document-local rather than corpus-global.
    grouped: dict[tuple[str, str], list[dict]] = {}
    for chunk in all_chunks:
        grouped.setdefault((chunk["kind"], chunk["code"]), []).append(chunk)
    for chunks_i in grouped.values():
        chunks_i.sort(key=lambda c: c["chunk_index"])
        for position, chunk in enumerate(chunks_i):
            chunk["chunk_index"] = position
            chunk["chunk_count"] = len(chunks_i)

    for (kind, code), chunks_i in grouped.items():
        dest = CHUNKS / kind / f"{code}.jsonl"
        dest.parent.mkdir(parents=True, exist_ok=True)
        with dest.open("w", encoding="utf-8", newline="\n") as handle:
            for chunk in chunks_i:
                handle.write(json.dumps(chunk, ensure_ascii=False) + "\n")

    manifest = {
        "generated": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "chunker_version": CHUNKER_VERSION,
        "parser_version": segment.PARSER_VERSION,
        "embed_model": EMBED_MODEL,
        "embed_dimensions": EMBED_DIMENSIONS,
        "target_chars": TARGET_CHARS,
        "min_chars": MIN_CHARS,
        "overlap_chars": OVERLAP_CHARS,
        "max_citations": MAX_CITATIONS,
        "documents": len(grouped),
        "chunks": len(all_chunks),
        "by_kind": by_kind,
        "total_chars": total_chars,
        "quarantined": len(quarantined),
        "verify_cites": "pass" if not failures else ("not-run" if not args.verify_cites else "fail"),
        "cites_verified": verified,
    }
    CHUNKS.mkdir(parents=True, exist_ok=True)
    (CHUNKS / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8", newline="\n"
    )
    log(f"[write] {len(grouped)} files, {CHUNKS}")

    if args.strict and (failures or quarantined):
        return 1
    return 0


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    raise SystemExit(main(sys.argv[1:]))