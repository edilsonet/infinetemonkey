#!/usr/bin/env python3
"""Look up ANAC fragment paths by keyword or category."""

from __future__ import annotations

import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
INDEXES = ROOT / "knowledge" / "anac-legislacao" / "support" / "indexes"


def load(name: str) -> dict:
    path = INDEXES / name
    if not path.exists():
        return {}
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def main(argv: list[str]) -> int:
    if not argv:
        print("usage: query.py <keyword> [keyword...]")
        return 2
    keywords = load("keyword-index.yml").get("keywords") or {}
    categories = load("category-index.yml").get("categories") or {}
    seen = set()
    hits = []
    for raw in argv:
        key = raw.strip().lower()
        for pool in (categories.get(key) or [], keywords.get(key) or []):
            for entry in pool:
                ident = entry.get("id")
                if ident in seen:
                    continue
                seen.add(ident)
                hits.append(entry)
    if not hits:
        print("no fragments for:", ", ".join(argv))
        print("hint: read knowledge/anac-legislacao/support/indexes/keyword-index.yml")
        return 1
    print(f"{len(hits)} fragment(s):")
    for entry in hits:
        print(f"- {entry.get('cite')} | {entry.get('title')} | {entry.get('path')}")
    print("\nRead only those YAML files. Do not open the full PDF first.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
