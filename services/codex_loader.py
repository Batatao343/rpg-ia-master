"""
codex_loader.py — Ingestão do Codex (data/codex/**/*.md) no índice FAISS de lore,
preservando metadados (id, type, name, tags, visibility) em cada chunk.

O split roda offline (não usa embeddings); só `ingest_codex` precisa de chave.
Spec: specs/SPEC-001-fase-2.5-codex-world-state.md §3.
"""

from __future__ import annotations

import os
from typing import Dict, List, Optional, Tuple

import yaml
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

CODEX_DIR = os.path.join("data", "codex")
CAMPOS_OBRIGATORIOS = ("id", "type", "name", "tags", "visibility")
CODEX_BODY_MAX_CHARS = 2000

_codex_index_cache: Optional[Dict[str, str]] = None


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


def codex_index(codex_dir: str = CODEX_DIR) -> Dict[str, str]:
    """id -> path do .md do Codex (cache em módulo; varre o frontmatter 1x).

    Fase 3.2: usado por `codex_body` para achar o documento de uma entidade
    descoberta sem reindexar o FAISS. Mesmo padrão de `graph_resolver.load_entities`.
    """
    global _codex_index_cache
    if _codex_index_cache is None:
        index: Dict[str, str] = {}
        for root, _dirs, files in os.walk(codex_dir):
            for fname in sorted(files):
                if not fname.endswith(".md"):
                    continue
                path = os.path.join(root, fname)
                try:
                    frontmatter, _body = parse_codex_file(path)
                except ValueError as exc:
                    print(f"⚠️ [CODEX] {exc}")
                    continue
                index[frontmatter["id"]] = path
        _codex_index_cache = index
    return _codex_index_cache


def codex_body(entity_id: Optional[str], codex_dir: str = CODEX_DIR) -> str:
    """Corpo do .md de `entity_id`, truncado (~2000 chars), só se `visibility: public`.

    Documento `hidden`/`secret` (ou id sem entrada no Codex) -> "" — não-onisciência.
    """
    if not entity_id:
        return ""
    path = codex_index(codex_dir).get(entity_id)
    if not path:
        return ""
    frontmatter, body = parse_codex_file(path)
    if frontmatter.get("visibility", "public") != "public":
        return ""
    return body[:CODEX_BODY_MAX_CHARS]


def clear_codex_index_cache() -> None:
    """Invalida o cache de `codex_index` (testes / edição de data/codex/ em runtime)."""
    global _codex_index_cache
    _codex_index_cache = None


def ingest_codex(codex_dir: str = CODEX_DIR) -> None:
    """Gera faiss_lore_index/ a partir do Codex (substitui ingest_file p/ lore)."""
    from langchain_community.vectorstores import FAISS

    from rag import _resolve_provider, _save_index, get_embeddings, get_global_db_path

    embeddings = get_embeddings()
    if embeddings is None:
        print("[CODEX] Sem embeddings (chave ausente) — ingestão abortada.")
        return

    docs = load_codex(codex_dir)
    if not docs:
        print(f"[CODEX] Nenhum documento em {codex_dir}.")
        return

    provider = _resolve_provider()
    print(f"--- INGESTÃO DO CODEX: {codex_dir} ({len(docs)} chunks) → índice 'lore' "
          f"(provider: {provider}) ---")
    db = FAISS.from_documents(docs, embeddings)
    _save_index(db, get_global_db_path("lore"), provider)
    print("✅ Codex indexado em 'faiss_lore_index'.")
