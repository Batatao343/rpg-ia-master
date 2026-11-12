"""SPEC-416 Bloco A: `docs/guias/DECISOES_FIXAS.md` existe, é verificável e é lido pelos agentes.

Teste de documento (caso permitido em `docs/guias/TESTES.md`): o arquivo é contrato de processo.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DOC = ROOT / "docs" / "guias" / "DECISOES_FIXAS.md"
HEADER = "| ID | Item | Decisão | Fonte | Gatilho de revisão |"
PATH_RE = re.compile(r"(?:specs|docs)/[\w./-]+?\.md")


def _rows() -> list[list[str]]:
    rows: list[list[str]] = []
    for line in DOC.read_text(encoding="utf-8").splitlines():
        if re.match(r"\| D-", line):
            cells = [c.strip() for c in re.split(r"(?<!\\)\|", line.strip())[1:-1]]
            rows.append(cells)
    return rows


def test_arquivo_existe_e_tem_colunas() -> None:
    assert DOC.exists(), "docs/guias/DECISOES_FIXAS.md ausente"
    assert HEADER in DOC.read_text(encoding="utf-8").splitlines()
    assert all(len(r) == 5 for r in _rows())


def test_ids_unicos_e_no_formato() -> None:
    ids = [r[0] for r in _rows()]
    assert ids, "tabela vazia"
    assert all(re.fullmatch(r"D-\d{2,}", i) for i in ids), ids
    assert len(ids) == len(set(ids)), "ID repetido"


def test_fonte_aponta_para_arquivo_existente() -> None:
    for row in _rows():
        paths = PATH_RE.findall(row[3])
        assert paths, f"{row[0]}: fonte sem caminho versionado"
        for p in paths:
            assert (ROOT / p).exists(), f"{row[0]}: fonte inexistente {p}"


def test_gatilho_nao_vazio() -> None:
    generic = {"se mudar", "n/a", "-", "—"}
    for row in _rows():
        assert row[4] and row[4].lower() not in generic, f"{row[0]}: gatilho vazio/genérico"


def test_teto() -> None:
    assert len(_rows()) <= 60
    assert DOC.stat().st_size <= 12 * 1024


def test_agentes_mandam_ler() -> None:
    for name in ("audit-reader", "spec-author"):
        text = (ROOT / ".claude" / "agents" / f"{name}.md").read_text(encoding="utf-8")
        assert "DECISOES_FIXAS.md" in text, name
