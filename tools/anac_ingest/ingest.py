#!/usr/bin/env python3
"""Ingest ANAC RBAC, IS, and IAC into fragment YAML plus a keyword index."""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
import unicodedata
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from urllib.parse import quote, urljoin, urlparse, unquote

import yaml
from bs4 import BeautifulSoup

try:
    import pymupdf
except Exception:  # pragma: no cover
    pymupdf = None

ROOT = Path(__file__).resolve().parents[2]
NS = ROOT / "knowledge" / "anac-legislacao"
SUPPORT = NS / "support"
CATALOGS = SUPPORT / "catalogs"
SOURCES_HTML = SUPPORT / "sources" / "html"
SOURCES_PDF = SUPPORT / "sources" / "pdf"
EXTRACTED = SUPPORT / "extracted"
FRAGMENTS = SUPPORT / "fragments"
INDEXES = SUPPORT / "indexes"

LISTING_URLS = {
    "rbac": "https://www.anac.gov.br/assuntos/legislacao/legislacao-1/rbha-e-rbac/rbac",
    "is": "https://www.anac.gov.br/assuntos/legislacao/legislacao-1/iac-e-is/is",
    "iac": "https://www.anac.gov.br/assuntos/legislacao/legislacao-1/iac-e-is/iac",
}

ARCHIVE_PREFIX = "https://arquivo.pt/wayback/"
USER_AGENT = "InfiniteBrainANAC/1.0 (legislation ingest; +local-knowledge-os)"
CURL_TIMEOUT = 45

_cdx_lock = threading.Lock()
_cdx_cache: dict[str, tuple[int, bytes]] = {}
_cdx_last = 0.0

STOPWORDS = {
    "a", "ao", "aos", "as", "ate", "com", "como", "da", "das", "de", "do", "dos",
    "e", "em", "entre", "essa", "esse", "esta", "este", "foi", "ja", "mais",
    "nao", "nas", "no", "nos", "o", "os", "ou", "para", "pela", "pelo", "por",
    "que", "se", "sem", "ser", "sua", "suas", "seu", "seus", "um", "uma", "uns",
    "umas", "the", "and", "of", "for", "to", "in", "on", "an", "is", "are",
    "n", "no", "na", "rbac", "rbha", "iac", "anac", "emd", "emenda", "nesta",
    "neste", "qualquer", "quando", "onde", "apos", "antes", "conforme",
    "previsto", "prevista", "previstos", "previstas", "deve", "devem",
    "podera", "poderao", "sera", "serao", "sendo", "sido", "tambem", "apenas",
    "ainda", "muito", "sobre", "sob", "apos", "via", "item", "itens",
}

CATEGORY_BY_FAMILY = {
    "00": ["governanca", "procedimento-geral"],
    "01": ["definicoes", "regras-gerais"],
    "11": ["processo-normativo"],
    "13": ["investigacao", "ocorrencias"],
    "21": ["certificacao", "projeto", "aeronavegabilidade"],
    "23": ["aeronavegabilidade", "aeronaves-pequenas"],
    "25": ["aeronavegabilidade", "transporte"],
    "26": ["aeronavegabilidade", "envelhecimento"],
    "27": ["aeronavegabilidade", "rotorcraft"],
    "29": ["aeronavegabilidade", "rotorcraft"],
    "31": ["aeronavegabilidade", "baloes"],
    "33": ["motores", "aeronavegabilidade"],
    "34": ["emissoes", "meio-ambiente"],
    "35": ["helices", "aeronavegabilidade"],
    "36": ["ruido", "meio-ambiente"],
    "38": ["ice-protection", "aeronavegabilidade"],
    "39": ["diretrizes-de-aeronavegabilidade"],
    "43": ["manutencao", "aeronavegabilidade"],
    "45": ["identificacao", "aeronavegabilidade"],
    "47": ["registro-aeronautico"],
    "60": ["simuladores", "treinamento"],
    "61": ["licencas", "pilotos", "pessoal"],
    "63": ["licencas", "tripulacao", "pessoal"],
    "65": ["licencas", "mecanicos", "pessoal"],
    "67": ["saude", "certificado-medico", "pessoal"],
    "90": ["regras-de-voo", "operacoes"],
    "91": ["operacoes-gerais", "regras-de-voo"],
    "103": ["ultraleves", "operacoes"],
    "105": ["paraquedismo", "operacoes"],
    "107": ["seguranca", "aeroporto"],
    "108": ["seguranca", "operador"],
    "110": ["carga", "operacoes"],
    "117": ["fadiga", "jornada", "operacoes"],
    "119": ["certificacao-de-operador", "operacoes"],
    "120": ["antidrogas", "saude"],
    "121": ["transporte-aereo", "operacoes"],
    "129": ["operador-estrangeiro", "operacoes"],
    "133": ["carga-externa", "helicoptero"],
    "135": ["taxi-aereo", "operacoes"],
    "136": ["turismo", "operacoes"],
    "137": ["aeroagricola", "operacoes"],
    "139": ["aerodromos", "infraestrutura"],
    "141": ["escolas", "treinamento"],
    "145": ["organizacao-de-manutencao", "manutencao"],
    "147": ["escolas-de-manutencao", "treinamento"],
    "153": ["aerodromos", "operacao-aeroportuaria"],
    "154": ["seguranca-aeroportuaria"],
    "155": ["seguranca-aeroportuaria"],
    "164": ["servicos-aereos"],
    "175": ["artigos-perigosos", "carga"],
    "183": ["delegacao", "credenciamento"],
    "193": ["protecao-ao-passageiro"],
}

PAGE_HEADER_RE = re.compile(
    r"^(Data da emiss[a~a]o:|Data de vig[eê]ncia:|Emenda n|RBAC n|RBHA n|"
    r"IS\s+\d|IAC\s+\d|Origem:|P[aá]gina\s+\d|\d{1,3}/\d{1,3}$|"
    r"Ag[eê]ncia Nacional de Avia)",
    re.IGNORECASE,
)
SECTION_RE = re.compile(
    r"^(?:(?P<prefix>[A-Z])?(?P<code>\d{1,3}\.\d+[A-Z]?(?:-[IVX]+)?)|"
    r"(?P<apendice>AP[ÊE]NDICE\s+[A-Z])|"
    r"(?P<issec>\d{1,3}(?:\.\d+){1,4}))"
    r"(?:\s+|$)(?P<title>.*)$"
)
# A bare date ("27.05.2025") also matches the numeric section pattern, so it is
# rejected explicitly before section detection.
DATE_RE = re.compile(r"^\d{1,2}[./]\d{1,2}[./]\d{2,4}\.?$")
# IS and IAC use single-level headings ("7. PREPARAÇÃO PARA O EXAME").
SINGLE_SECTION_RE = re.compile(r"^(\d{1,3})\.\s+(\S.*)$")
# Short standalone block names ("OBJETIVO", "DESENVOLVIMENTO DO ASSUNTO") do not
# carry a number. Match the whole folded line to keep precision.
STRUCTURAL_HEADINGS = frozenset({
    "objetivo", "objetivos", "revogacao", "fundamento", "fundamentos",
    "definicao", "definicoes", "termos e definicoes", "desenvolvimento",
    "desenvolvimento do assunto", "disposicoes", "disposicoes finais",
    "disposicoes gerais", "disposicoes preliminares", "disposicoes transitorias",
    "introducao", "referencia", "referencias", "aplicabilidade", "abrangencia",
    "escopo", "sumario", "historico", "historico de revisoes", "bibliografia",
    "vigencia", "aprovacao", "preambulo", "consideracoes", "responsabilidades",
    "requisitos", "procedimentos", "siglas", "acronimos", "abreviaturas",
    "generalidades", "apendice", "apendices", "anexo", "anexos",
})
STRUCTURAL_PREFIXES = ("apendice", "anexo")
APPENDIX_HEADS = frozenset({"apendice", "apendices", "anexo", "anexos"})
# ANAC list items are written both "(a) ..." and "a) ...".
LETTER_SUB_RE = re.compile(r"^\(?([a-z])\)(?:-([IVX]+))?\s*(.*)$")
PARSER_VERSION = 7

# Set ANAC_LIVE=1 (or pass --live) when www.anac.gov.br is reachable, so the
# crawler tries the live site before falling back to Arquivo.pt snapshots.
LIVE = os.environ.get("ANAC_LIVE", "").strip() == "1"

PT_HINTS = {
    "de", "da", "do", "que", "para", "com", "nao", "uma", "dos", "das", "no",
    "na", "os", "as", "ser", "por", "pelo", "pela", "ao", "aos", "ou", "em",
    "um", "se", "sua", "seu", "mais", "como", "quando", "onde", "deve", "sao",
}
EN_HINTS = {
    "the", "and", "of", "to", "in", "shall", "which", "must", "for", "is",
    "be", "or", "with", "are", "by", "on", "this", "that", "not", "may",
    "each", "any", "all", "such", "as",
}


def slug(text: str) -> str:
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = re.sub(r"[^a-zA-Z0-9]+", "-", text.lower()).strip("-")
    return text or "x"


def short_slug(text: str, maxlen: int = 60) -> str:
    """Slug that stays under filesystem limits, with a stable hash suffix."""
    value = slug(text)
    if len(value) <= maxlen:
        return value
    digest = hashlib.sha256(value.encode("utf-8")).hexdigest()[:6]
    return value[: maxlen - 7].rstrip("-") + "-" + digest


def fold(text: str) -> str:
    text = unicodedata.normalize("NFKD", text or "")
    return "".join(ch for ch in text if not unicodedata.combining(ch)).lower()


def ensure_dirs() -> None:
    for path in (CATALOGS, SOURCES_HTML, SOURCES_PDF, EXTRACTED, FRAGMENTS, INDEXES):
        path.mkdir(parents=True, exist_ok=True)


def curl_get(url: str, dest: Path | None = None, timeout: int = CURL_TIMEOUT) -> tuple[int, bytes, str]:
    cmd = [
        "curl", "-sS", "-L", "--max-time", str(timeout),
        "-A", USER_AGENT,
    ]
    if dest is not None:
        dest.parent.mkdir(parents=True, exist_ok=True)
        cmd += ["-o", str(dest), "-w", "%{http_code}\t%{content_type}"]
        result = subprocess.run(cmd + [url], capture_output=True, check=False)
        meta = (result.stdout or b"").decode("utf-8", "replace").strip()
        parts = meta.split("\t", 1)
        http = int(parts[0]) if parts and parts[0].isdigit() else 0
        content_type = parts[1] if len(parts) > 1 else ""
        body = dest.read_bytes() if dest.exists() else b""
        return http, body, content_type
    cmd += ["-w", "\n__HTTP__%{http_code}__TYPE__%{content_type}__", url]
    result = subprocess.run(cmd, capture_output=True, check=False)
    raw = result.stdout or b""
    marker = b"\n__HTTP__"
    if marker in raw:
        body, meta = raw.rsplit(marker, 1)
        meta_s = meta.decode("utf-8", "replace")
        http_m = re.search(r"(\d+)", meta_s)
        http = int(http_m.group(1)) if http_m else 0
        ctype = re.search(r"__TYPE__(.*?)(?:__|$)", meta_s)
        content_type = (ctype.group(1) if ctype else "").strip()
    else:
        body = raw
        http = 0
        content_type = ""
    return http, body, content_type


def archive_candidates(url: str) -> list[str]:
    if "arquivo.pt" in url:
        return [url]
    if LIVE and "anac.gov.br" in url:
        # Live ANAC first when explicitly enabled; CDX is the fallback.
        return [url]
    # Untimestamped wayback URLs return an HTML wrapper. Use CDX snapshots.
    return []


def url_variants(url: str) -> list[str]:
    parsed = urlparse(url)
    path = parsed.path
    paths = [path, path.rstrip("/") + "/", path.rstrip("/")]

    def pad(seg: str) -> str:
        return re.sub(
            r"(rbac|rbha)-(\d{1,2})(?!\d)",
            lambda m: f"{m.group(1)}-{m.group(2).zfill(3)}",
            seg,
            flags=re.I,
        )

    def unpad(seg: str) -> str:
        return re.sub(
            r"(rbac|rbha)-0+(\d+)",
            lambda m: f"{m.group(1)}-{m.group(2)}",
            seg,
            flags=re.I,
        )

    for transform in (pad, unpad):
        paths.append(transform(path))
        paths.append(transform(path).rstrip("/") + "/")
    seen = set()
    out = []
    for p in paths:
        for query in ("", "visao=tabela"):
            candidate = parsed._replace(path=p.split("?")[0], query=query).geturl()
            if candidate not in seen:
                seen.add(candidate)
                out.append(candidate)
    return out


def fetch_bytes(url: str, dest: Path | None = None) -> tuple[bytes, str, str]:
    last_err = ""
    for candidate in archive_candidates(url):
        http, body, ctype = curl_get(candidate, dest=dest)
        if http in (200, 203) and body:
            if b"Arquivo.pt" in body[:800] and b"wbinfo" in body[:2000]:
                last_err = f"archive wrapper via {candidate}"
                continue
            if dest is not None and dest.exists() and dest.stat().st_size > 200:
                return dest.read_bytes(), ctype, candidate
            if len(body) > 200:
                if dest is not None:
                    dest.write_bytes(body)
                return body, ctype, candidate
        last_err = f"http={http} bytes={len(body)} via {candidate}"
        time.sleep(0.15)
    cdx_url = cdx_best(url)
    if cdx_url:
        http, body, ctype = curl_get(cdx_url, dest=dest)
        if http in (200, 203) and body and len(body) > 200:
            if dest is not None:
                dest.write_bytes(body)
            return body, ctype, cdx_url
        last_err += f" cdx={http}"
    raise RuntimeError(f"failed to fetch {url}: {last_err}")


def _cdx_records(body: bytes) -> list[dict]:
    records = []
    try:
        parsed_json = json.loads(body.decode("utf-8", "replace"))
        if isinstance(parsed_json, dict):
            records = [parsed_json]
        elif isinstance(parsed_json, list):
            records = [r for r in parsed_json if isinstance(r, dict)]
    except Exception:
        for line in body.decode("utf-8", "replace").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except Exception:
                continue
            if isinstance(rec, dict):
                records.append(rec)
    return records


def is_junk_attachment(url: str) -> bool:
    """Skip CEF scans and resolucao PDFs that are not ANAC norm text."""
    low = unquote(url or "").lower()
    if "cef" in low:
        return True
    if "resolucao" in low and re.search(r"/(rbac|rbha|is|iac)/", low):
        return True
    return False


def is_foreign_annex(url: str) -> bool:
    """True for the FAA/CFR annex PDFs ANAC attaches to some RBAC pages.

    These are kept (the user wants whatever the document contains, in any
    language) but are labelled `foreign_annex: true` so a reader knows the
    text is the CFR/FAA source and not the translated ANAC regulation.
    """
    low = unquote(url or "").lower()
    if "cfr" in low or "title 14" in low or "federal aviation" in low:
        return True
    if re.search(r"part[\s._-]?2[0-9]\b", low):
        return True
    return False


def detect_language(text: str) -> str:
    sample = fold(text or "")[:40000]
    words = re.findall(r"[a-z]{2,}", sample)
    pt = sum(1 for w in words if w in PT_HINTS)
    en = sum(1 for w in words if w in EN_HINTS)
    if pt == 0 and en == 0:
        return "unknown"
    if en > pt * 1.4:
        return "en"
    if pt > en * 1.4:
        return "pt"
    return "mixed"


def cache_is_contaminated(meta: dict, extracted_path: Path) -> bool:
    return is_junk_attachment(str(meta.get("archive_url") or ""))


def _cdx_pick(records: list[dict], fallback_url: str) -> str:
    best = ""
    # Very low floor so a lone foreign annex is still usable as last resort.
    best_score = -(10**18)
    needles = []
    names = []
    for variant in url_variants(fallback_url) + [fallback_url]:
        path = urlparse(variant).path.split("/@@")[0].rstrip("/").lower()
        names.append(Path(urlparse(variant).path).name.lower())
        if path.endswith(".pdf"):
            path = str(Path(path).parent).lower()
        if path:
            needles.append(path)
    for rec in records:
        status = str(rec.get("status") or "200")
        if status not in {"200", "203"}:
            continue
        ts = str(rec.get("timestamp") or "")
        if not ts.isdigit():
            continue
        original = rec.get("url") or fallback_url
        if is_junk_attachment(original):
            continue
        rec_path = urlparse(original).path.lower()
        if needles and not any(n in rec_path for n in needles):
            if not any(n and n in rec_path for n in names):
                continue
        mime = str(rec.get("mime") or "").lower()
        score = int(ts)
        if "pdf" in mime or str(original).lower().endswith(".pdf"):
            score += 10**14
        low = unquote(str(original)).lower()
        if "arquivo_norma" in low:
            score += 10**13
        if "anexo_norma" in low:
            score -= 10**12
        if is_foreign_annex(original):
            # Keep as last resort only, never over an ANAC arquivo_norma PDF.
            score -= 10**15
        if score > best_score:
            best_score = score
            best = f"{ARCHIVE_PREFIX}{ts}id_/{original}"
    return best


def cdx_query_keys(url: str) -> list[str]:
    keys = []
    seen = set()
    variants = [url]
    if re.search(r"(rbac|rbha)-\d{1,2}(?!\d)", urlparse(url).path, re.I):
        variants = [v for v in url_variants(url) if "visao=" not in v]
    for variant in variants:
        parsed = urlparse(variant)
        path = parsed.path or "/"
        candidates = [path]
        if "/@@" in path:
            candidates.append(path.split("/@@")[0])
        if path.lower().endswith(".pdf"):
            parent = str(Path(path).parent)
            if re.search(r"(rbac|rbha|is|iac)-\d", parent, re.I):
                candidates.append(parent)
        for p in candidates:
            query = parsed.netloc + p
            if parsed.query and p == path:
                query += "?" + parsed.query
            if query not in seen:
                seen.add(query)
                keys.append(query)
    return keys[:6]


def cdx_http(api: str) -> tuple[int, bytes]:
    global _cdx_last
    with _cdx_lock:
        cached = _cdx_cache.get(api)
        if cached is not None:
            return cached
        wait = 0.45 - (time.time() - _cdx_last)
        if wait > 0:
            time.sleep(wait)
        http, body, _ctype = curl_get(api, timeout=25)
        _cdx_last = time.time()
        _cdx_cache[api] = (http, body)
        return http, body


def cdx_best(url: str) -> str:
    tried = set()
    for query in cdx_query_keys(url):
        for match_type in ("", "prefix"):
            key = (query, match_type)
            if key in tried:
                continue
            tried.add(key)
            api = (
                "https://arquivo.pt/wayback/cdx?url="
                + quote(query, safe="")
                + "&output=json&limit=40"
            )
            if match_type:
                api += "&matchType=prefix"
            http, body = cdx_http(api)
            if http != 200 or not body:
                continue
            best = _cdx_pick(_cdx_records(body), url)
            if best:
                return best
    return ""


def abs_url(href: str, base: str) -> str:
    href = href.strip()
    if href.startswith("/Anac/"):
        href = "https://www.anac.gov.br" + href[5:]
    if href.startswith("/"):
        href = "https://www.anac.gov.br" + href
    return urljoin(base, href).split("#")[0]


def parse_listing(kind: str, html: str, base: str) -> list[dict]:
    soup = BeautifulSoup(html, "lxml")
    items = []
    seen = set()
    table = soup.find("table")
    rows = table.find_all("tr") if table else []
    for row in rows:
        cells = row.find_all("td")
        if len(cells) < 3:
            continue
        title_a = cells[0].find("a")
        if not title_a:
            continue
        title = " ".join(title_a.get_text(" ", strip=True).split())
        page_url = abs_url(title_a.get("href", ""), base)
        date = cells[1].get_text(" ", strip=True) if len(cells) > 1 else ""
        ementa = cells[2].get_text(" ", strip=True) if len(cells) > 2 else ""
        pdf_url = ""
        if len(cells) > 3:
            for a in cells[3].find_all("a", href=True):
                href = abs_url(a["href"], base)
                if "arquivo_norma" in href or (
                    href.lower().endswith(".pdf") and "anexo_norma" not in href
                ):
                    pdf_url = href
                elif "anexo_norma" in href:
                    continue
                elif (
                    not href.lower().endswith(".pdf")
                    and "/resolveuid/" not in href
                ):
                    page_url = href or page_url
        code = infer_code(kind, title, page_url)
        key = (kind, code, page_url)
        if key in seen:
            continue
        seen.add(key)
        items.append({
            "kind": kind,
            "code": code,
            "title": title,
            "ementa": ementa,
            "publication_date": date,
            "page_url": page_url,
            "pdf_url": pdf_url,
            "family": infer_family(kind, title, page_url, code),
        })
    return items


def infer_code(kind: str, title: str, url: str) -> str:
    path = unquote(urlparse(url).path)
    m = re.search(r"/(?:rbac|is|iac)/((?:rbac|rbha|is|iac)-[^/]+)", path, re.I)
    if m:
        return slug(m.group(1))
    m = re.search(
        rf"\b{kind}\s*n?o?\.?\s*(\d{{1,3}}(?:[.-]\d+)*)(?:\s*emd\s*(\d+))?",
        title,
        re.I,
    )
    if m:
        code = f"{kind}-{m.group(1)}"
        if m.group(2):
            code += f"-emd-{m.group(2)}"
        return slug(code)
    stem = Path(urlparse(url).path).name
    stem = re.sub(r"\?.*$", "", stem)
    if stem and "resolveuid" not in url and not re.fullmatch(r"[0-9a-f]{32}", stem):
        return slug(stem)
    return slug(title)


def infer_family(kind: str, title: str, url: str, code: str) -> str:
    blob = f"{title} {url} {code}"
    m = re.search(rf"{kind}\s*-?\s*(\d{{1,3}})", blob, re.I)
    if m:
        return m.group(1).lstrip("0") or "0"
    m = re.search(r"(\d{1,3})", code)
    return m.group(1).lstrip("0") if m else ""


def find_pdf_on_page(html: str, base: str, code: str = "") -> str:
    soup = BeautifulSoup(html, "lxml")
    ranked: list[tuple[int, str]] = []
    code_slug = slug(code) if code else ""
    compact = code_slug.replace("-", "")
    for a in soup.find_all("a", href=True):
        href = abs_url(a["href"], base)
        low = href.lower()
        if "arquivo_norma" not in low and not low.endswith(".pdf") and "/@@display-file/" not in low:
            continue
        if is_junk_attachment(href):
            continue
        score = 0
        if "arquivo_norma" in low:
            score += 12
        if compact and compact in slug(unquote(href)).replace("-", ""):
            score += 20
        if "resolucao" in low:
            score -= 12
        if "anexo_norma" in low:
            score -= 4
        if is_foreign_annex(href):
            # Keep as last resort only, never over an ANAC arquivo_norma PDF.
            score -= 100
        ranked.append((score, href))
    ranked.sort(key=lambda pair: pair[0], reverse=True)
    if not ranked:
        return ""
    best_score, best_href = ranked[0]
    if best_score > 0:
        return best_href
    # No ANAC native PDF on the page: fall back to the foreign annex if any.
    for score, href in ranked:
        if not is_foreign_annex(href):
            return href
    return best_href
    return ""


def html_to_text(html: str) -> str:
    soup = BeautifulSoup(html, "lxml")
    for tag in soup(["script", "style", "nav", "footer", "header"]):
        tag.decompose()
    core = soup.select_one("#content-core") or soup.select_one("#content") or soup.body
    text = core.get_text("\n") if core else soup.get_text("\n")
    lines = [" ".join(line.split()) for line in text.splitlines()]
    return "\n".join(line for line in lines if line)


def pdf_to_text(data: bytes) -> str:
    if not pymupdf:
        raise RuntimeError("pymupdf is not installed")
    doc = pymupdf.open(stream=data, filetype="pdf")
    parts = [page.get_text("text") for page in doc]
    doc.close()
    return "\n".join(parts)


def clean_legal_text(text: str) -> str:
    text = text.replace("\u00a0", " ").replace("\uf0b7", "-")
    text = text.replace("\u2013", "-").replace("\u2014", "-")
    lines = []
    for raw in text.splitlines():
        line = " ".join(raw.split())
        if not line:
            if lines and lines[-1] != "":
                lines.append("")
            continue
        if PAGE_HEADER_RE.match(line):
            continue
        if re.fullmatch(r"\d{1,3}/\d{1,3}", line):
            continue
        lines.append(line)
    cleaned = "\n".join(lines)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned.strip()


class SectionHead:
    """A detected section heading: stable id, display title, appendix marker."""

    __slots__ = ("section_id", "title", "apendice")

    def __init__(self, section_id: str, title: str, apendice: str = "") -> None:
        self.section_id = section_id
        self.title = title
        self.apendice = apendice


def is_section_header(line: str, family: str, kind: str) -> SectionHead | None:
    text = line.strip()
    if not text or DATE_RE.match(text):
        return None

    if kind in {"is", "iac"}:
        single = SINGLE_SECTION_RE.match(text)
        if single and len(text) <= 90:
            title = single.group(2)
            if title[:1].isupper() and 1 <= int(single.group(1)) <= 99:
                return SectionHead(single.group(1), title)

    folded = fold(text.rstrip(":").strip())
    if folded in STRUCTURAL_HEADINGS or any(
        folded == prefix or folded.startswith(prefix + " ")
        for prefix in STRUCTURAL_PREFIXES
    ):
        # Appendices repeat their header on every page; mark them so the
        # fragmenter merges the repeats instead of losing the later text.
        is_appendix = folded in APPENDIX_HEADS or any(
            folded.startswith(prefix + " ") for prefix in STRUCTURAL_PREFIXES
        )
        merge_key = short_slug(" ".join(folded.split()[:2]), 24) if is_appendix else ""
        return SectionHead(short_slug(folded), text, merge_key)

    m = SECTION_RE.match(text)
    if not m:
        return None
    code = m.group("code") or ""
    apendice = m.group("apendice") or ""
    issec = m.group("issec") or ""
    title = (m.group("title") or "").strip()
    if apendice:
        if kind == "is":
            return None
        return SectionHead(short_slug(apendice + " " + title), text, slug(apendice))
    if code:
        if re.match(r"^\d+\.0{2,}$", code):
            return None
        prefix = m.group("prefix") or ""
        if prefix:
            return SectionHead(prefix + code, title or prefix + code)
        head = code.split(".")[0].lstrip("0")
        fam = (family or "").lstrip("0")
        if fam and head != fam:
            return None
        return SectionHead(code, title or code)
    if kind in {"is", "iac"} and issec:
        if len(text) < 160:
            return SectionHead(issec, title or issec)
    return None


def fragment_document(kind: str, code: str, family: str, text: str) -> list[dict]:
    lines = text.splitlines()
    sections: list[dict] = []
    current = {
        "section_id": "preambulo",
        "section_title": "Preambulo e sumario",
        "lines": [],
    }
    for line in lines:
        head = is_section_header(line, family, kind)
        if head:
            if head.apendice and current["section_id"].startswith(head.apendice):
                current["lines"].append(line)
                continue
            if current["lines"]:
                sections.append(current)
            current = {
                "section_id": head.section_id,
                "section_title": head.title,
                "lines": [line],
            }
        else:
            current["lines"].append(line)
    if current["lines"]:
        sections.append(current)

    fragments = []
    for section in sections:
        body_lines = section["lines"]
        buckets: list[tuple[str, str, list[str]]] = []
        current_sub = "body"
        current_label = section["section_title"]
        current_lines: list[str] = []
        for line in body_lines:
            lm = LETTER_SUB_RE.match(line)
            if lm:
                # Every lettered item is its own fragment.
                if current_lines:
                    buckets.append((current_sub, current_label, current_lines))
                letter = lm.group(1)
                roman = lm.group(2)
                current_sub = f"{letter}-{roman.lower()}" if roman else letter
                current_label = f"{section['section_id']}({letter}" + (f"-{roman}" if roman else "") + ")"
                current_lines = [line]
                continue
            current_lines.append(line)
        if current_lines:
            buckets.append((current_sub, current_label, current_lines))

        for sub_id, sub_label, sub_lines in buckets:
            body = "\n".join(sub_lines).strip()
            if len(body) < 20:
                continue
            frag_id = short_slug(
                f"{kind}-{code}-{section['section_id']}-{sub_id}", 120
            )
            fragments.append({
                "id": frag_id,
                "kind": kind,
                "document": code,
                "family": family,
                "section_id": section["section_id"],
                "section_title": section["section_title"],
                "subsection_id": sub_id,
                "cite": sub_label if sub_id != "body" else section["section_id"],
                "title": section["section_title"] if sub_id == "body" else sub_label,
                "text": body,
            })

    # A sumario/toc or a repeated page header can emit the same section twice,
    # which used to overwrite the real body fragment. Keep the longest text.
    deduped: dict[str, dict] = {}
    for frag in fragments:
        prev = deduped.get(frag["id"])
        if prev is None or len(frag["text"]) > len(prev["text"]):
            deduped[frag["id"]] = frag
    return list(deduped.values())


def keywords_for(fragment: dict) -> list[str]:
    blob = fold(fragment.get("title", "") + " " + fragment.get("section_title", "") + " " + fragment.get("text", ""))
    words = re.findall(r"[a-zA-Z0-9]{4,}", blob)
    counts: dict[str, int] = {}
    for word in words:
        if word in STOPWORDS or word.isdigit():
            continue
        counts[word] = counts.get(word, 0) + 1
    ranked = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))
    cats = CATEGORY_BY_FAMILY.get(fragment.get("family", ""), [])
    out = list(cats)
    for word, _n in ranked[:12]:
        if word not in out:
            out.append(word)
    return out[:16]


def dump_yaml(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        yaml.safe_dump(data, allow_unicode=True, sort_keys=False, width=88),
        encoding="utf-8",
    )


def quarantine_dir() -> Path:
    path = ROOT / "outputs" / "quarantine" / time.strftime("%Y-%m-%d")
    path.mkdir(parents=True, exist_ok=True)
    return path


def quarantine(path: Path) -> None:
    """Move stale artifacts out of the knowledge surface instead of deleting."""
    if not path.exists():
        return
    dest = quarantine_dir() / path.relative_to(SUPPORT)
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists():
        dest = dest.with_name(f"{dest.name}.{int(time.time() * 1000)}")
    shutil.move(str(path), str(dest))


def write_document(item: dict, text: str, source_type: str, used_url: str,
                   page_url: str, language: str, foreign_annex: bool) -> dict:
    kind = item["kind"]
    code = item["code"]
    family = item.get("family") or ""
    doc_dir = FRAGMENTS / kind / code
    extracted_path = EXTRACTED / kind / f"{code}.md"

    extracted_path.parent.mkdir(parents=True, exist_ok=True)
    extracted_path.write_text(
        f"# {item['title']}\n\n"
        f"- kind: {kind}\n"
        f"- code: {code}\n"
        f"- source: {source_type}\n"
        f"- language: {language}\n"
        f"- foreign_annex: {str(bool(foreign_annex)).lower()}\n"
        f"- page_url: {page_url}\n"
        f"- pdf_url: {item.get('pdf_url','')}\n"
        f"- archive_url: {used_url}\n"
        f"- ementa: {item.get('ementa','')}\n\n"
        f"## Texto extraido\n\n{text}\n",
        encoding="utf-8",
    )

    frags = fragment_document(kind, code, family, text)
    doc_dir.mkdir(parents=True, exist_ok=True)
    keep = {f["id"] for f in frags}
    for stale in doc_dir.glob("*.yml"):
        if not stale.name.startswith("_") and stale.stem not in keep:
            quarantine(stale)
    for frag in frags:
        frag["keywords"] = keywords_for(frag)
        frag["categories"] = CATEGORY_BY_FAMILY.get(family, ["legislacao"])
        frag["language"] = language
        frag["source_path"] = str(extracted_path.relative_to(ROOT))
        dump_yaml(doc_dir / f"{frag['id']}.yml", frag)

    section_ids = sorted({f["section_id"] for f in frags})
    dump_yaml(doc_dir / "_index.yml", {
        "document": code,
        "kind": kind,
        "title": item["title"],
        "ementa": item.get("ementa", ""),
        "family": family,
        "categories": CATEGORY_BY_FAMILY.get(family, ["legislacao"]),
        "page_url": page_url,
        "pdf_url": item.get("pdf_url", ""),
        "archive_url": used_url,
        "language": language,
        "foreign_annex": bool(foreign_annex),
        "sections": section_ids,
        "fragment_count": len(frags),
        "fragment_ids": [f["id"] for f in frags],
        "parser_version": PARSER_VERSION,
    })
    return {"sections": len(section_ids), "fragments": len(frags)}


def process_item(item: dict, force: bool = False) -> dict:
    kind = item["kind"]
    code = item["code"]
    family = item.get("family") or ""
    doc_dir = FRAGMENTS / kind / code
    extracted_path = EXTRACTED / kind / f"{code}.md"
    result = {
        **item,
        "status": "ok",
        "source_type": "",
        "archive_url": "",
        "chars": 0,
        "sections": 0,
        "fragments": 0,
        "language": "unknown",
        "foreign_annex": False,
        "error": "",
    }
    try:
        if not force and extracted_path.exists() and (doc_dir / "_index.yml").exists():
            meta = yaml.safe_load((doc_dir / "_index.yml").read_text(encoding="utf-8")) or {}
            cached_frags = meta.get("fragment_count") or 0
            if (
                meta.get("parser_version") == PARSER_VERSION
                and cached_frags >= 5
                and not cache_is_contaminated(meta, extracted_path)
            ):
                result.update({
                    "status": "ok",
                    "source_type": "cached",
                    "chars": extracted_path.stat().st_size,
                    "sections": len(meta.get("sections") or []),
                    "fragments": meta.get("fragment_count") or 0,
                })
                return result
        text = ""
        source_type = ""
        used_url = ""
        pdf_url = item.get("pdf_url") or ""
        page_url = item.get("page_url") or ""

        errors = []

        def try_pdf(url: str) -> None:
            nonlocal text, source_type, used_url, pdf_url
            pdf_name = slug(unquote(Path(urlparse(url).path).name)) or code
            if not pdf_name.endswith("pdf"):
                pdf_name += ".pdf"
            pdf_path = SOURCES_PDF / kind / pdf_name
            data, ctype, used = fetch_bytes(url, dest=pdf_path)
            if data[:4] == b"%PDF" or "pdf" in (ctype or "").lower():
                text = pdf_to_text(data)
                source_type = "pdf"
                used_url = used
                pdf_url = url
                result["pdf_url"] = url
                result["foreign_annex"] = is_foreign_annex(used or url)
            elif not text:
                text = html_to_text(data.decode("utf-8", "replace"))
                source_type = "html"
                used_url = used

        def try_page(url: str) -> None:
            nonlocal text, source_type, used_url, pdf_url
            html_path = SOURCES_HTML / kind / f"{code}.html"
            html, ctype, used = fetch_bytes(url, dest=html_path)
            if html[:4] == b"%PDF" or "pdf" in (ctype or "").lower():
                try_pdf(used or url)
                return
            html_s = html.decode("utf-8", "replace")
            found_pdf = find_pdf_on_page(html_s, url, code)
            page_text = html_to_text(html_s)
            if found_pdf:
                try:
                    try_pdf(found_pdf)
                    if source_type == "pdf" and len(text) >= 400:
                        return
                except Exception as exc:
                    errors.append(str(exc))
            if len(page_text) >= 400 and len(page_text) >= len(text):
                text = page_text
                source_type = "html"
                used_url = used

        fetch_plan = []
        if pdf_url and "pergamum" not in pdf_url.lower():
            fetch_plan.append(("pdf", pdf_url))
        if page_url:
            fetch_plan.append(("page", page_url))
        if pdf_url and "pergamum" in pdf_url.lower():
            fetch_plan.append(("pdf", pdf_url))

        for src_kind, src_url in fetch_plan:
            if text:
                break
            try:
                if src_kind == "pdf":
                    try_pdf(src_url)
                else:
                    try_page(src_url)
            except Exception as exc:
                errors.append(str(exc))

        text = clean_legal_text(text)
        if len(text) < 400:
            detail = "; ".join(errors[-3:]) if errors else "no fetch candidates"
            raise RuntimeError(f"extracted text too short ({len(text)} chars); {detail}")

        if not is_foreign_annex(used_url):
            result["foreign_annex"] = False
        language = "en" if result.get("foreign_annex") else detect_language(text)
        result["language"] = language

        stats = write_document(
            item, text, source_type, used_url, page_url,
            language, bool(result.get("foreign_annex")),
        )
        result.update({
            "source_type": source_type,
            "archive_url": used_url,
            "chars": len(text),
            "sections": stats["sections"],
            "fragments": stats["fragments"],
            "language": language,
        })
        return result
    except Exception as exc:
        result["status"] = "error"
        result["error"] = str(exc)
        return result


def build_keyword_index(catalog: list[dict]) -> None:
    keyword_map: dict[str, list[dict]] = {}
    category_map: dict[str, list[dict]] = {}
    cite_map: dict[str, dict] = {}
    for item in catalog:
        if item.get("status") != "ok":
            continue
        doc_dir = FRAGMENTS / item["kind"] / item["code"]
        index_path = doc_dir / "_index.yml"
        if not index_path.exists():
            continue
        meta = yaml.safe_load(index_path.read_text(encoding="utf-8")) or {}
        allowed = set(meta.get("fragment_ids") or [])
        for path in sorted(doc_dir.glob("*.yml")):
            if path.name.startswith("_"):
                continue
            frag = yaml.safe_load(path.read_text(encoding="utf-8"))
            if allowed and frag.get("id") not in allowed:
                continue
            rel = str(path.relative_to(ROOT))
            entry = {
                "id": frag["id"],
                "cite": frag.get("cite"),
                "title": frag.get("title"),
                "document": f"{item['kind']}:{item['code']}",
                "path": rel,
            }
            cite_map[frag["id"]] = entry
            for kw in frag.get("keywords") or []:
                keyword_map.setdefault(kw, []).append(entry)
            for cat in frag.get("categories") or []:
                category_map.setdefault(cat, []).append(entry)

    dump_yaml(INDEXES / "keyword-index.yml", {
        "generated": time.strftime("%Y-%m-%d"),
        "usage": "Look up a topic key, then read only the listed fragment YAML files.",
        "keywords": {k: v[:40] for k, v in sorted(keyword_map.items())},
    })
    dump_yaml(INDEXES / "category-index.yml", {
        "generated": time.strftime("%Y-%m-%d"),
        "categories": {k: v[:80] for k, v in sorted(category_map.items())},
    })
    dump_yaml(INDEXES / "fragment-index.yml", {
        "generated": time.strftime("%Y-%m-%d"),
        "fragments": cite_map,
    })

    md_lines = [
        "# Indice de recuperacao ANAC",
        "",
        "Use este indice antes de abrir textos integrais. Cada chave aponta para fragmentos YAML.",
        "",
        "## Como consultar",
        "",
        "1. Escolha uma categoria ou palavra-chave.",
        "2. Leia so os arquivos `path` listados.",
        "3. Se a resposta exigir contexto, abra a secao irma, nao o PDF inteiro.",
        "",
        "## Categorias",
        "",
    ]
    for cat, entries in sorted(category_map.items()):
        md_lines.append(f"### {cat}")
        md_lines.append("")
        for entry in entries[:25]:
            md_lines.append(f"- `{entry['cite']}` {entry['title']}: `{entry['path']}`")
        md_lines.append("")
    (INDEXES / "README.md").write_text("\n".join(md_lines), encoding="utf-8")


def load_or_fetch_listing(kind: str) -> tuple[str, str]:
    dest = SOURCES_HTML / f"listing-{kind}.html"
    url = LISTING_URLS[kind]
    if not LIVE and dest.exists() and dest.stat().st_size > 1000:
        return dest.read_text(encoding="utf-8", errors="replace"), url
    try:
        data, _ctype, used = fetch_bytes(url, dest=dest)
        return data.decode("utf-8", "replace"), used
    except Exception:
        if dest.exists() and dest.stat().st_size > 1000:
            return dest.read_text(encoding="utf-8", errors="replace"), url
        raise


def load_catalog(kinds: list[str]) -> list[dict]:
    items: list[dict] = []
    for kind in kinds:
        path = CATALOGS / f"{kind}.yml"
        if not path.exists():
            continue
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        items.extend(data.get("items") or [])
    return items


def load_report() -> dict:
    path = CATALOGS / "ingest-report.yml"
    if not path.exists():
        return {}
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def save_report(results: list[dict]) -> None:
    order = {"rbac": 0, "is": 1, "iac": 2}
    ordered = sorted(results, key=lambda r: (order.get(r.get("kind"), 9), r.get("code", "")))
    dump_yaml(CATALOGS / "ingest-report.yml", {
        "generated": time.strftime("%Y-%m-%d %H:%M:%S"),
        "ok": sum(1 for r in ordered if r["status"] == "ok"),
        "error": sum(1 for r in ordered if r["status"] == "error"),
        "results": ordered,
    })


def merge_report(results: list[dict]) -> list[dict]:
    """Overlay fresh results on the previous report so untouched kinds survive."""
    merged: dict[tuple, dict] = {}
    for row in (load_report().get("results") or []):
        merged[(row.get("kind"), row.get("code"))] = row
    for row in results:
        merged[(row.get("kind"), row.get("code"))] = row
    return list(merged.values())


def read_extracted_text(path: Path) -> str:
    text = path.read_text(encoding="utf-8", errors="replace")
    marker = "## Texto extraido"
    if marker in text:
        text = text.split(marker, 1)[1]
    return text.strip()


def refragment(results: list[dict]) -> list[dict]:
    """Rebuild fragments from stored extracted text, no network."""
    for row in results:
        if row.get("status") != "ok":
            continue
        path = EXTRACTED / row["kind"] / f"{row['code']}.md"
        if not path.exists():
            continue
        text = clean_legal_text(read_extracted_text(path))
        if len(text) < 400:
            continue
        foreign = bool(row.get("foreign_annex"))
        language = "en" if foreign else (row.get("language") or detect_language(text))
        stats = write_document(
            row, text, row.get("source_type") or "cached",
            row.get("archive_url") or "", row.get("page_url") or "",
            language, foreign,
        )
        row.update({
            "source_type": row.get("source_type") or "cached",
            "chars": len(text),
            "sections": stats["sections"],
            "fragments": stats["fragments"],
            "language": language,
        })
    return results


def clean_dead(results: list[dict]) -> int:
    """Quarantine fragment dirs and extracted files not backed by an ok row."""
    alive = {(r["kind"], r["code"]) for r in results if r.get("status") == "ok"}
    moved = 0
    for kind_dir in FRAGMENTS.iterdir():
        if not kind_dir.is_dir():
            continue
        for doc_dir in kind_dir.iterdir():
            if doc_dir.is_dir() and (kind_dir.name, doc_dir.name) not in alive:
                quarantine(doc_dir)
                moved += 1
    if EXTRACTED.exists():
        for kind_dir in EXTRACTED.iterdir():
            if not kind_dir.is_dir():
                continue
            for path in kind_dir.glob("*.md"):
                if (kind_dir.name, path.stem) not in alive:
                    quarantine(path)
                    moved += 1
    return moved


def main(argv: list[str]) -> int:
    ensure_dirs()
    global LIVE
    flags = {a for a in argv if a.startswith("--")}
    args = [a for a in argv if not a.startswith("--")]
    only: list[str] = []
    for a in argv:
        if a.startswith("--only="):
            only = [c for c in a[len("--only="):].split(",") if c]
    if "--live" in flags:
        LIVE = True
    kinds = [k for k in args if k in LISTING_URLS] or ["rbac", "is", "iac"]

    if "--refragment" in flags or "--clean" in flags:
        previous = load_report().get("results") or []
        if "--refragment" in flags:
            previous = refragment(previous)
            save_report(previous)
            print(f"[refragment] rebuilt {sum(1 for r in previous if r['status']=='ok')} docs", flush=True)
        if "--clean" in flags:
            moved = clean_dead(previous)
            print(f"[clean] quarantined {moved} dead artifact(s)", flush=True)
        build_keyword_index(previous)
        print("[done] indexes written", flush=True)
        return 0

    catalog: list[dict] = []
    for kind in kinds:
        html, used = load_or_fetch_listing(kind)
        items = parse_listing(kind, html, LISTING_URLS[kind])
        dump_yaml(CATALOGS / f"{kind}.yml", {
            "kind": kind,
            "source_url": LISTING_URLS[kind],
            "fetched_via": used,
            "count": len(items),
            "items": items,
        })
        print(f"[catalog] {kind}: {len(items)} items", flush=True)
        catalog.extend(items)
    if only:
        catalog = [item for item in catalog if item["code"] in only]
        if not catalog:
            print(f"[warn] no catalog match for {only}", flush=True)

    workers = 3
    results = []
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futs = {pool.submit(process_item, item, bool(only)): item for item in catalog}
        for fut in as_completed(futs):
            item = futs[fut]
            res = fut.result()
            results.append(res)
            print(
                f"[{res['status']}] {item['kind']}:{item['code']} "
                f"frags={res.get('fragments',0)} {res.get('error','')}",
                flush=True,
            )

    merged = merge_report(results)
    save_report(merged)
    build_keyword_index(merged)
    print("[done] indexes written", flush=True)
    return 0 if any(r["status"] == "ok" for r in results) else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
