#!/usr/bin/env python3
"""Stdlib-only parsing primitives for ANAC legal text.

Extracted from ingest.py so that offline consumers (chunk.py, and the
ingest.py --refragment path) share exactly one implementation of section
detection and legal-text cleanup. This module must never import a third
party package: the repository venv ships PyYAML only, and the network and
parsing stacks in ingest.py are not needed to read the corpus back.

Everything here was moved verbatim from ingest.py. Behaviour must not drift.
"""

from __future__ import annotations

import hashlib
import re
import unicodedata
from pathlib import Path

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


def clean_legal_text(text: str) -> str:
    text = text.replace(" ", " ").replace("", "-")
    text = text.replace("–", "-").replace("—", "-")
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


def fragment_blocks(kind: str, code: str, family: str, text: str) -> list[dict]:
    """Sectionize a document into citation blocks, in document order.

    The dedupe that fragment_document applies afterwards is deliberately not
    done here: consumers that need the raw document sequence (the chunker)
    must be able to see repeated blocks so it can attribute each window to the
    right cite.
    """
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
    return fragments


def fragment_document(kind: str, code: str, family: str, text: str) -> list[dict]:
    """Deduplicated fragments: a sumario or a repeated page header can emit the
    same section twice, which used to overwrite the real body fragment. Keep the
    longest text, preserving first-seen document position."""
    deduped: dict[str, dict] = {}
    for frag in fragment_blocks(kind, code, family, text):
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


def read_extracted_text(path: Path) -> str:
    text = path.read_text(encoding="utf-8", errors="replace")
    marker = "## Texto extraido"
    if marker in text:
        text = text.split(marker, 1)[1]
    return text.strip()


def read_extracted_header(path: Path) -> dict:
    """Parse the bullet header write_document() writes above '## Texto extraido'.

    The ementa field is free text and can wrap onto several lines, so the block
    is read as YAML rather than line by line. Values arrive as strings, which is
    what the callers expect.
    """
    raw = path.read_text(encoding="utf-8", errors="replace")
    marker = "## Texto extraido"
    head = raw.split(marker, 1)[0] if marker in raw else raw
    lines = [ln for ln in head.splitlines() if ln.strip()]
    title = ""
    fields: dict[str, str] = {}
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("# "):
            title = stripped[2:].strip()
            continue
        if stripped.startswith("- ") and ":" in stripped:
            key, _, value = stripped[2:].partition(":")
            fields[key.strip()] = value.strip()
    return {"title": title, **fields}