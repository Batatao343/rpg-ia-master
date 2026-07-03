"""
codex_loader.py — Ingestão do Codex (data/codex/**/*.md) no índice FAISS de lore,
preservando metadados (id, type, name, tags, visibility) em cada chunk.

O split roda offline (não usa embeddings); só `ingest_codex` precisa de chave.
Spec: specs/fase-2.5-codex-world-state.md §3.
"""

from __future__ import annotations

import os
from typing import List, Tuple

import yaml
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

CODEX_DIR = os.path.join("data", "codex")
CAMPOS_OBRIGATORIOS = ("id", "type", "name", "tags", "visibility")


def parse_codex_file(path: str) -> Tuple[dict, str]:
    """Lê um .md do Codex → (frontmatter, corpo).

    Levanta ValueError se o frontmatter faltar ou não tiver campo obrigatório.
    """
    with open(path, "r", encoding="utf-8") as f:
        text = f.read()

    if not text.startswith("---"):
        raise ValueError(f"{path}: sem frontmatter YAML (---)")
    parts = text.split("---", 2)
    if len(parts) < 3:
        raise ValueError(f"{path}: frontmatter não fechado")

    frontmatter = yaml.safe_load(parts[1])
    if not isinstance(frontmatter, dict):
        raise ValueError(f"{path}: frontmatter inválido")
    for campo in CAMPOS_OBRIGATORIOS:
        if campo not in frontmatter:
            raise ValueError(f"{path}: frontmatter sem campo obrigatório '{campo}'")

    return frontmatter, parts[2].strip()


def load_codex(codex_dir: str = CODEX_DIR) -> List[Document]:
    """1 Document por chunk (500/50) com metadata do frontmatter. Offline."""
    splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=50)
    docs: List[Document] = []

    for root, _dirs, files in os.walk(codex_dir):
        for fname in sorted(files):
            if not fname.endswith(".md"):
                continue
            path = os.path.join(root, fname)
            frontmatter, body = parse_codex_file(path)
            metadata = {
                "id": frontmatter["id"],
                "type": frontmatter["type"],
                "name": frontmatter["name"],
                "tags": frontmatter.get("tags", []),
                "visibility": frontmatter.get("visibility", "public"),
            }
            for chunk in splitter.split_text(body):
                docs.append(Document(page_content=chunk, metadata=dict(metadata)))
    return docs


def ingest_codex(codex_dir: str = CODEX_DIR) -> None:
    """Gera faiss_lore_index/ a partir do Codex (substitui ingest_file p/ lore)."""
    from langchain_community.vectorstores import FAISS

    from rag import get_embeddings, get_global_db_path

    embeddings = get_embeddings()
    if embeddings is None:
        print("[CODEX] Sem embeddings (chave ausente) — ingestão abortada.")
        return

    docs = load_codex(codex_dir)
    if not docs:
        print(f"[CODEX] Nenhum documento em {codex_dir}.")
        return

    print(f"--- INGESTÃO DO CODEX: {codex_dir} ({len(docs)} chunks) → índice 'lore' ---")
    db = FAISS.from_documents(docs, embeddings)
    db.save_local(get_global_db_path("lore"))
    print("✅ Codex indexado em 'faiss_lore_index'.")
