"""SPEC-348 — helpers compartilhados pelos testes de coerência da lore."""

from __future__ import annotations

import json
import unicodedata
from functools import lru_cache
from pathlib import Path

from services.codex_loader import parse_codex_file

ROOT = Path(__file__).resolve().parent.parent
CODEX = ROOT / "data" / "codex"
LORE = ROOT / "lore_nova"


def fold(text: str) -> str:
    """minúsculas, sem acento, espaços colapsados (comparação de frases-chave)."""
    plain = "".join(
        ch for ch in unicodedata.normalize("NFD", str(text)) if unicodedata.category(ch) != "Mn"
    )
    return " ".join(plain.lower().split())


@lru_cache(maxsize=1)
def codex_docs() -> tuple[dict, ...]:
    """Todos os docs do Codex: id, visibility, type, folder, frontmatter, body, text (fm+corpo)."""
    docs = []
    for path in sorted(CODEX.rglob("*.md")):
        fm, body = parse_codex_file(str(path))
        raw = path.read_text(encoding="utf-8")
        docs.append(
            {
                "id": fm["id"],
                "visibility": fm.get("visibility", "public"),
                "type": fm["type"],
                "path": path,
                "fm": fm,
                "body": body,
                "text": fold(raw),
            }
        )
    return tuple(docs)


def public_docs() -> list[dict]:
    return [d for d in codex_docs() if d["visibility"] == "public"]


def hidden_docs() -> list[dict]:
    return [d for d in codex_docs() if d["visibility"] in ("hidden", "secret")]


def doc(doc_id: str) -> dict:
    for d in codex_docs():
        if d["id"] == doc_id:
            return d
    raise KeyError(doc_id)


def lore_text(name: str) -> str:
    return (LORE / name).read_text(encoding="utf-8")


def lore_lines(name: str) -> list[str]:
    return lore_text(name).splitlines()


def load_json(rel: str):
    return json.loads((ROOT / rel).read_text(encoding="utf-8"))


def docs_containing(phrase: str, docs: list[dict]) -> list[str]:
    needle = fold(phrase)
    return [d["id"] for d in docs if needle in d["text"]]
