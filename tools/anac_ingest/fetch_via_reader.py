#!/usr/bin/env python3
"""Recover ANAC documents the offline ingest could not fetch.

The build environment cannot reach www.anac.gov.br, and the public archive
only covers part of the corpus. This helper reads each still-missing document
through the external reader r.jina.ai: the page with the #content selector
when the page embeds the norm text, otherwise the PDF attachment the page
links. The recovered text goes through the same fragment writer as the offline
ingest, then the keyword indexes are rebuilt.

Usage:
    python3 tools/anac_ingest/fetch_via_reader.py                # every miss
    python3 tools/anac_ingest/fetch_via_reader.py --limit=8      # small trial
    python3 tools/anac_ingest/fetch_via_reader.py --only=rbac,is
"""

from __future__ import annotations

import argparse
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ingest  # noqa: E402

READER = "https://r.jina.ai/"
UA = "InfiniteBrainANAC/1.0 (legislation ingest; +local-knowledge-os)"
CONTENT_MARK = "Markdown Content:"
PDF_RE = re.compile(r"\((https?://[^)\s]+\.pdf)\)", re.I)
VIEWER_RE = re.compile(r"\((https?://[^)\s]+/visualizar_ato_normativo)\)", re.I)
HEADER_RE = re.compile(
    r"^(Title|URL Source|Published Time|Number of Pages|Warning|Markdown Content):",
    re.I,
)
MIN_TEXT = 400
ERROR_HINT = "esta página não existe"
PORTAL_MARKS = ("Ir para o menu", "MAPA DO SITE", "ACESSIBILIDADE ALTO CONTRASTE")


def usable(text: str) -> bool:
    if len(text) < MIN_TEXT or ERROR_HINT in text.lower():
        return False
    return not all(mark.lower() in text.lower() for mark in PORTAL_MARKS[:2])


def reader_failed(body: str) -> str:
    """Return the reader error line when the target itself failed."""
    for line in body.splitlines():
        if "Target URL returned error" in line:
            return line.strip()
    return ""


def reader_get(url: str, selector: str | None = None, fmt: str = "text",
               timeout: int = 180, attempts: int = 4) -> str:
    """Fetch a URL through the reader, retrying transient limits.

    fmt="text" keeps the original line breaks, which the fragment parser needs;
    fmt="markdown" is used only when link targets must be read.
    """
    target = READER + url
    last = ""
    for i in range(attempts):
        req = urllib.request.Request(target)
        req.add_header("User-Agent", UA)
        req.add_header("X-Return-Format", fmt)
        if selector:
            req.add_header("X-Target-Selector", selector)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                body = resp.read().decode("utf-8", "replace")
                failed = reader_failed(body)
                if failed:
                    raise RuntimeError(failed)
                return body
        except urllib.error.HTTPError as exc:
            last = f"http={exc.code}"
            if exc.code in (429, 500, 502, 503, 504) and i < attempts - 1:
                time.sleep(4 * (i + 1))
                continue
            raise
        except Exception as exc:  # noqa: BLE001
            last = str(exc)
            if i < attempts - 1:
                time.sleep(4 * (i + 1))
                continue
            raise
    raise RuntimeError(f"reader failed for {url}: {last}")


def body_after_content(body: str) -> str:
    if CONTENT_MARK in body:
        body = body.split(CONTENT_MARK, 1)[1]
    lines = [ln for ln in body.splitlines() if not HEADER_RE.match(ln.strip())]
    return "\n".join(lines).strip()


def find_document_link(md: str) -> str:
    """Pick the best document target on a norm page: PDF, then viewer."""
    for url in PDF_RE.findall(md) + VIEWER_RE.findall(md):
        if ingest.is_junk_attachment(url):
            continue
        if "pergamum" in url.lower():
            # The old site rendered a broken relative link; the host is wrong
            # and the fetch returns a 404 page, so ignore it here.
            continue
        return url
    return ""


def reader_text(url: str, selector: str | None = None) -> str:
    raw = reader_get(url, selector=selector, fmt="text")
    return ingest.clean_legal_text(body_after_content(raw))


def try_text(url: str, selector: str | None = None) -> str:
    try:
        return reader_text(url, selector=selector)
    except Exception:  # noqa: BLE001 - a failed source falls through to the next
        return ""


def read_document(item: dict) -> tuple[str, str, bool]:
    """Return (text, used_url, foreign_annex) for one catalog item."""
    pdf_url = item.get("pdf_url") or ""
    if pdf_url and not ingest.is_junk_attachment(pdf_url):
        text = try_text(pdf_url)
        if usable(text):
            return text, pdf_url, ingest.is_foreign_annex(pdf_url)

    page = item.get("page_url") or ""
    if page:
        link = ""
        try:
            md = reader_get(page, selector="#content", fmt="markdown")
            link = find_document_link(body_after_content(md))
        except Exception:  # noqa: BLE001
            pass
        if link:
            # The norm viewer wraps the text in portal chrome unless scoped.
            link_sel = "#content" if "visualizar_ato_normativo" in link else None
            text = try_text(link, selector=link_sel)
            if usable(text):
                return text, link, ingest.is_foreign_annex(link)
        page_text = try_text(page, selector="#content")
        if usable(page_text):
            return page_text, page, ingest.is_foreign_annex(page)

    if pdf_url:
        text = try_text(pdf_url)
        if usable(text):
            return text, pdf_url, ingest.is_foreign_annex(pdf_url)
    raise RuntimeError("reader produced no usable text")


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--kinds", default="rbac,is,iac")
    parser.add_argument("--only", default="")
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--delay", type=float, default=1.0)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args(argv)

    kinds = [k for k in args.kinds.split(",") if k]
    only = {c for c in args.only.split(",") if c}

    catalog = ingest.load_catalog(kinds)
    report = ingest.load_report()
    done = {
        (r.get("kind"), r.get("code"))
        for r in (report.get("results") or [])
        if r.get("status") == "ok"
    }
    todo = [
        item for item in catalog
        if (args.force or (item["kind"], item["code"]) not in done)
        and (not only or item["code"] in only)
    ]
    if args.limit:
        todo = todo[: args.limit]
    print(f"[plan] {len(todo)} missing document(s)", flush=True)

    results = []
    for item in todo:
        try:
            text, used, foreign = read_document(item)
            language = "en" if foreign else ingest.detect_language(text)
            stats = ingest.write_document(
                item, text, "reader", used, item.get("page_url") or "",
                language, foreign,
            )
            row = {
                **item, "status": "ok", "source_type": "reader",
                "archive_url": used, "chars": len(text),
                "sections": stats["sections"], "fragments": stats["fragments"],
                "language": language, "foreign_annex": bool(foreign), "error": "",
            }
            print(
                f"[ok] {item['kind']}:{item['code']} "
                f"chars={len(text)} frags={stats['fragments']}",
                flush=True,
            )
        except Exception as exc:  # noqa: BLE001
            row = {
                **item, "status": "error", "source_type": "reader",
                "archive_url": "", "chars": 0, "sections": 0, "fragments": 0,
                "language": "unknown", "foreign_annex": False,
                "error": f"reader: {exc}",
            }
            print(f"[error] {item['kind']}:{item['code']} {exc}", flush=True)
        results.append(row)
        time.sleep(args.delay)

    merged = ingest.merge_report(results)
    ingest.save_report(merged)
    ingest.build_keyword_index(merged)
    ok = sum(1 for r in results if r["status"] == "ok")
    print(f"[done] {ok}/{len(results)} recovered; report and indexes written",
          flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
