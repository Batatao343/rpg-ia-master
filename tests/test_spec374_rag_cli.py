"""SPEC-374 Etapa 6 — ``rag.py --only rules|lore|all`` (R18)."""

from __future__ import annotations

import pytest

import rag
from services import codex_loader, content_validator


@pytest.fixture()
def chamadas(monkeypatch):
    visto: dict[str, list] = {"codex": [], "arquivo": [], "lint": []}
    monkeypatch.setattr(content_validator, "validate_all", lambda: visto["lint"].append(1) or [])
    monkeypatch.setattr(codex_loader, "ingest_codex", lambda *a, **k: visto["codex"].append(1))
    monkeypatch.setattr(rag, "ingest_file", lambda path, name: visto["arquivo"].append(name))
    return visto


def test_default_e_all(chamadas):
    assert rag.parse_args([]).only == "all"
    rag.reindex_global()
    assert chamadas["codex"] == [1] and chamadas["arquivo"] == ["rules"]


def test_only_rules_nao_chama_ingest_codex(chamadas):
    rag.reindex_global(rag.parse_args(["--only", "rules"]).only)
    assert chamadas["codex"] == []
    assert chamadas["arquivo"] == ["rules"]
    assert chamadas["lint"] == [1]  # o lint de conteúdo segue valendo


def test_only_lore_nao_toca_regras(chamadas):
    rag.reindex_global("lore")
    assert chamadas["codex"] == [1] and chamadas["arquivo"] == []


def test_all_chama_os_dois(chamadas):
    rag.reindex_global("all")
    assert chamadas["codex"] == [1] and chamadas["arquivo"] == ["rules"]


def test_only_invalido_falha():
    with pytest.raises(SystemExit):
        rag.parse_args(["--only", "tudo"])


def test_lint_com_erro_aborta_sem_indexar(monkeypatch, chamadas):
    erro = content_validator.Finding
    achado = erro(validator="v", severity="error", path="p", entity_id="", message="m")
    monkeypatch.setattr(content_validator, "validate_all", lambda: [achado])
    with pytest.raises(SystemExit):
        rag.reindex_global("rules")
    assert chamadas["arquivo"] == [] and chamadas["codex"] == []


def test_only_desconhecido_levanta_erro(chamadas):
    with pytest.raises(ValueError):
        rag.reindex_global("regras")
    assert chamadas["arquivo"] == [] and chamadas["codex"] == []
