"""Fase 7.2 — pipeline de autoria: overrides migration-safe, curated preservado,
lint de overrides, gate no reindex, templates.

Spec: specs/fase-7.2-autoria-curadoria.md.
"""

from __future__ import annotations

import json
import os
import re

import pytest
import yaml

from scripts.migrate_lore_nova import (
    apply_overrides,
    is_curated,
    load_overrides,
)
from services.codex_loader import parse_codex_file
from services.content_validator import validate_overrides


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _write_md(codex_dir, fname: str, front: dict, body: str = "Corpo.") -> str:
    os.makedirs(codex_dir, exist_ok=True)
    path = os.path.join(codex_dir, fname)
    fm = yaml.safe_dump(front, allow_unicode=True, sort_keys=False).strip()
    with open(path, "w", encoding="utf-8") as f:
        f.write(f"---\n{fm}\n---\n\n{body}\n")
    return path


def _front(entity_id: str, **extra) -> dict:
    base = {"id": entity_id, "type": "npc", "name": entity_id.title(),
            "aliases": [], "tags": ["gerada"], "visibility": "public"}
    base.update(extra)
    return base


def _ent(entity_id: str, etype: str = "npc") -> dict:
    return {"id": entity_id, "type": etype, "name": entity_id.title(),
            "aliases": [], "tags": ["gerada"], "visibility": "public",
            "components": {}}


# ---------------------------------------------------------------------------
# Etapa 1 — overrides no migrate
# ---------------------------------------------------------------------------

def test_override_aliases_sobrevive_regeracao(tmp_path):
    codex = str(tmp_path / "codex")
    path = _write_md(codex, "npc_grum.md", _front("npc_grum"))
    entities = {"npc_grum": _ent("npc_grum")}
    orfaos = apply_overrides(entities, {"npc_grum": {"aliases": ["O Taverneiro"]}}, codex)
    assert orfaos == []
    fm, _body = parse_codex_file(path)
    assert fm["aliases"] == ["O Taverneiro"]


def test_override_tags_extra_nao_remove(tmp_path):
    codex = str(tmp_path / "codex")
    path = _write_md(codex, "npc_grum.md", _front("npc_grum", tags=["taverna"]))
    entities = {"npc_grum": _ent("npc_grum")}
    apply_overrides(entities, {"npc_grum": {"tags_extra": ["lendario", "taverna"]}}, codex)
    fm, _body = parse_codex_file(path)
    assert fm["tags"] == ["taverna", "lendario"]  # adiciona sem duplicar/remover


def test_override_append_body(tmp_path):
    codex = str(tmp_path / "codex")
    path = _write_md(codex, "npc_grum.md", _front("npc_grum"), body="Original.")
    apply_overrides({}, {"npc_grum": {"append_body": "Nota de curadoria."}}, codex)
    _fm, body = parse_codex_file(path)
    assert body.startswith("Original.") and body.endswith("Nota de curadoria.")


def test_override_patcha_entities_dict(tmp_path):
    codex = str(tmp_path / "codex")
    _write_md(codex, "npc_grum.md", _front("npc_grum"))
    entities = {"npc_grum": _ent("npc_grum")}
    apply_overrides(entities, {"npc_grum": {
        "aliases": ["O Taverneiro"], "visibility": "hidden",
        "tags_extra": ["Lendário Demais"],
    }}, codex)
    ent = entities["npc_grum"]
    assert ent["aliases"] == ["O Taverneiro"]
    assert ent["visibility"] == "hidden"
    assert "lendario_demais" in ent["tags"]  # slugificada como no register()


def test_override_orfao_retornado(tmp_path):
    codex = str(tmp_path / "codex")
    _write_md(codex, "npc_grum.md", _front("npc_grum"))
    orfaos = apply_overrides({}, {"npc_fantasma": {"aliases": ["X"]}}, codex)
    assert orfaos == ["npc_fantasma"]


def test_load_overrides_ausente_devolve_vazio(tmp_path):
    assert load_overrides(str(tmp_path / "nao_existe.yaml")) == {}


def test_load_overrides_le_yaml(tmp_path):
    path = str(tmp_path / "ov.yaml")
    with open(path, "w", encoding="utf-8") as f:
        f.write("npc_grum:\n  aliases: [Taverneiro]\n")
    assert load_overrides(path) == {"npc_grum": {"aliases": ["Taverneiro"]}}


# ---------------------------------------------------------------------------
# Etapa 2 — curated preservado
# ---------------------------------------------------------------------------

def test_curated_detectado(tmp_path):
    codex = str(tmp_path / "codex")
    path_curated = _write_md(codex, "npc_manual.md", _front("npc_manual", curated=True))
    path_gerado = _write_md(codex, "npc_gerado.md", _front("npc_gerado"))
    assert is_curated(path_curated) is True
    assert is_curated(path_gerado) is False


def test_curated_sobrevive_ao_delete_loop(tmp_path, monkeypatch):
    # reproduz o loop de delete do main() sobre um codex dir temporário
    import scripts.migrate_lore_nova as migrate
    codex = str(tmp_path / "codex")
    path_curated = _write_md(codex, "npc_manual.md", _front("npc_manual", curated=True))
    path_gerado = _write_md(codex, "npc_gerado.md", _front("npc_gerado"))

    for root, _dirs, files in os.walk(codex):
        for fname in files:
            if not fname.endswith(".md"):
                continue
            path = os.path.join(root, fname)
            if migrate.is_curated(path):
                continue
            os.remove(path)

    assert os.path.exists(path_curated)
    assert not os.path.exists(path_gerado)


def test_override_em_curated_e_ignorado(tmp_path):
    codex = str(tmp_path / "codex")
    path = _write_md(codex, "npc_manual.md", _front("npc_manual", curated=True),
                     body="Manual.")
    entities = {"npc_manual": _ent("npc_manual")}
    apply_overrides(entities, {"npc_manual": {"aliases": ["Hackeado"],
                                              "append_body": "Não entra."}}, codex)
    fm, body = parse_codex_file(path)
    assert fm["aliases"] == []          # intacto
    assert body == "Manual."            # intacto
    assert entities["npc_manual"]["aliases"] == []


# ---------------------------------------------------------------------------
# Etapa 3 — lint de overrides
# ---------------------------------------------------------------------------

def _write_graph(graph_dir, entities=None, extra=None) -> str:
    os.makedirs(graph_dir, exist_ok=True)
    for fname, conteudo in (("entities.json", entities or {}),
                            ("entities_extra.json", extra or {}),
                            ("components.json", {}), ("edges.json", []),
                            ("relation_types.json", {})):
        with open(os.path.join(graph_dir, fname), "w", encoding="utf-8") as f:
            json.dump(conteudo, f, ensure_ascii=False)
    return str(graph_dir)


def _write_yaml(tmp_path, data: dict) -> str:
    path = str(tmp_path / "overrides.yaml")
    with open(path, "w", encoding="utf-8") as f:
        yaml.safe_dump(data, f, allow_unicode=True)
    return path


def test_validate_overrides_id_orfao_erro(tmp_path):
    codex = str(tmp_path / "codex")
    _write_md(codex, "npc_grum.md", _front("npc_grum"))
    graph = _write_graph(tmp_path / "graph", entities={"npc_grum": _ent("npc_grum")})
    ov = _write_yaml(tmp_path, {"npc_fantasma": {"aliases": ["X"]}})
    findings = validate_overrides(codex, ov, graph)
    assert any(f.severity == "error" and "órfão" in f.message for f in findings)


def test_validate_overrides_ok(tmp_path):
    codex = str(tmp_path / "codex")
    _write_md(codex, "npc_grum.md", _front("npc_grum"))
    graph = _write_graph(tmp_path / "graph", entities={"npc_grum": _ent("npc_grum")})
    ov = _write_yaml(tmp_path, {"npc_grum": {"aliases": ["Taverneiro"]}})
    assert validate_overrides(codex, ov, graph) == []


def test_override_em_curated_vira_aviso(tmp_path):
    codex = str(tmp_path / "codex")
    _write_md(codex, "npc_manual.md", _front("npc_manual", curated=True))
    graph = _write_graph(tmp_path / "graph",
                         extra={"npc_manual": _ent("npc_manual")})
    ov = _write_yaml(tmp_path, {"npc_manual": {"aliases": ["X"]}})
    findings = validate_overrides(codex, ov, graph)
    assert any(f.severity == "warning" and "curated" in f.message for f in findings)


def test_curated_sem_entidade_gera_aviso(tmp_path):
    codex = str(tmp_path / "codex")
    _write_md(codex, "npc_manual.md", _front("npc_manual", curated=True))
    graph = _write_graph(tmp_path / "graph")  # entidade NÃO registrada
    ov = _write_yaml(tmp_path, {})
    findings = validate_overrides(codex, ov, graph)
    assert any(f.severity == "warning" and "sem entidade" in f.message for f in findings)


def test_curated_agregador_nao_gera_aviso(tmp_path):
    codex = str(tmp_path / "codex")
    _write_md(codex, "story_notas.md",
              _front("story_notas", type="world_story", curated=True))
    graph = _write_graph(tmp_path / "graph")
    ov = _write_yaml(tmp_path, {})
    assert validate_overrides(codex, ov, graph) == []


# ---------------------------------------------------------------------------
# Etapa 4 — gate no reindex
# ---------------------------------------------------------------------------

def test_reindex_aborta_com_erro_de_lint(monkeypatch, capsys):
    import rag
    from services import content_validator
    from services.content_validator import Finding

    monkeypatch.setattr(content_validator, "validate_all", lambda: [
        Finding("references", "error", "data/graph/edges.json", "e_x",
                "target 'nada' não existe nas entidades"),
    ])
    chamado = {"embeddings": False}
    monkeypatch.setattr(rag, "get_embeddings",
                        lambda: chamado.__setitem__("embeddings", True))

    with pytest.raises(SystemExit) as exc:
        rag.reindex_global()
    assert exc.value.code == 1
    assert chamado["embeddings"] is False  # abortou antes de tocar embeddings
    assert "abortada" in capsys.readouterr().out


# ---------------------------------------------------------------------------
# Etapa 5 — templates
# ---------------------------------------------------------------------------

_TEMPLATES_DIR = os.path.join("docs", "templates", "codex")
_TEMPLATES = ("local.md", "faccao.md", "raca.md", "npc.md", "monstro.md", "artefato.md")


def test_templates_existem_e_tem_frontmatter_valido():
    for fname in _TEMPLATES:
        path = os.path.join(_TEMPLATES_DIR, fname)
        assert os.path.isfile(path), f"template ausente: {path}"
        with open(path, encoding="utf-8") as f:
            text = f.read()
        assert text.startswith("---"), f"{fname}: sem frontmatter"
        for campo in ("id:", "type:", "name:", "tags:", "visibility:", "curated: true"):
            assert re.search(rf"^{campo}", text, re.MULTILINE), \
                f"{fname}: frontmatter sem '{campo}'"


def test_templates_fora_do_codex_dir():
    from services.codex_loader import CODEX_DIR
    for root, _dirs, files in os.walk(CODEX_DIR):
        for fname in files:
            with open(os.path.join(root, fname), encoding="utf-8") as f:
                inicio = f.read(400)
            assert "<slug" not in inicio, \
                f"template vazou para dentro de {CODEX_DIR}: {fname}"
