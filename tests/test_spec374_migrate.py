"""SPEC-374 Etapa 5 — o migrate não apaga doc curado (R16/R17) e o validador cobre o segredo."""

from __future__ import annotations

import importlib.util
import json
import os
import shutil
import sys
from pathlib import Path

import pytest

from services import content_validator as cv

ROOT = Path(__file__).resolve().parent.parent


def _mds(codex: Path) -> set[str]:
    return {p.relative_to(codex).as_posix() for p in codex.rglob("*.md")}


def _ids(path: Path) -> set[str]:
    return set(json.loads(path.read_text(encoding="utf-8"))) if path.exists() else set()


@pytest.fixture()
def copia(tmp_path, monkeypatch):
    """Cópia de lore_nova + codex + grafo + overrides: o migrate roda AQUI, nunca no worktree."""
    shutil.copytree(ROOT / "lore_nova", tmp_path / "lore_nova")
    shutil.copytree(ROOT / "data" / "codex", tmp_path / "data" / "codex")
    shutil.copytree(ROOT / "data" / "graph", tmp_path / "data" / "graph")
    shutil.copy(ROOT / "data" / "codex_overrides.yaml", tmp_path / "data" / "codex_overrides.yaml")
    spec = importlib.util.spec_from_file_location(
        "migrate_lore_nova_374", ROOT / "scripts" / "migrate_lore_nova.py"
    )
    mod = importlib.util.module_from_spec(spec)
    sys.modules["migrate_lore_nova_374"] = mod  # dataclasses resolvem o módulo por aqui
    spec.loader.exec_module(mod)
    monkeypatch.chdir(tmp_path)  # LORE_DIR/CODEX_DIR/GRAPH_DIR são relativos ao cwd
    return mod, tmp_path


def test_migrate_nao_apaga_curados(copia, capsys):
    mod, raiz = copia
    codex, grafo = raiz / "data" / "codex", raiz / "data" / "graph"
    antes_md = _mds(codex)
    antes_ids = _ids(grafo / "entities.json") | _ids(grafo / "entities_extra.json")
    mod.main()
    assert _mds(codex) >= antes_md, sorted(antes_md - _mds(codex))[:10]
    depois_ids = _ids(grafo / "entities.json") | _ids(grafo / "entities_extra.json")
    assert depois_ids >= antes_ids, sorted(antes_ids - depois_ids)[:10]
    # os docs de segredo escritos à mão (SPEC-350) sobreviveram
    assert (codex / "npcs" / "segredos" / "npc_tr_bento_juros_segredo.md").exists()
    assert (codex / "npcs" / "segredos" / "npc_mv_teo_chamine_segredo.md").exists()


def test_migrate_idempotente(copia, capsys):
    mod, raiz = copia
    codex, grafo = raiz / "data" / "codex", raiz / "data" / "graph"
    mod.main()
    a_md = {p: p.read_bytes() for p in codex.rglob("*.md")}
    a_ent = (grafo / "entities.json").read_bytes()
    a_extra = (grafo / "entities_extra.json").read_bytes()
    mod.main()
    assert {p: p.read_bytes() for p in codex.rglob("*.md")} == a_md
    assert (grafo / "entities.json").read_bytes() == a_ent
    assert (grafo / "entities_extra.json").read_bytes() == a_extra


def test_segredos_de_entidade_curada_levam_curated():
    """No repo real: nenhum npc_secret de entidade só-em-extra sem a marca."""
    codex, grafo = str(ROOT / "data" / "codex"), str(ROOT / "data" / "graph")
    assert cv.validate_curated_secrets(codex, grafo) == []


def _fm(**campos) -> str:
    linhas = ["---"]
    for k, v in campos.items():
        if isinstance(v, list):
            linhas.append(f"{k}:")
            linhas += [f"- {x}" for x in v]
        else:
            linhas.append(f"{k}: {v}")
    return "\n".join(linhas) + "\n---\n\nTexto.\n"


def test_validator_segredo_de_curada_exige_curated(tmp_path):
    codex, grafo = tmp_path / "codex", tmp_path / "graph"
    (codex / "npcs" / "segredos").mkdir(parents=True)
    grafo.mkdir()
    ent = {
        "id": "npc_x",
        "type": "npc",
        "name": "X",
        "aliases": [],
        "tags": [],
        "visibility": "public",
    }
    (grafo / "entities.json").write_text(json.dumps({}), encoding="utf-8")
    (grafo / "entities_extra.json").write_text(json.dumps({"npc_x": ent}), encoding="utf-8")
    base = dict(
        id="npc_x_segredo",
        type="npc_secret",
        name="X - Segredos",
        aliases=["x"],
        tags=["t"],
        visibility="hidden",
        related_entities=["npc_x"],
    )
    doc = codex / "npcs" / "segredos" / "npc_x_segredo.md"
    doc.write_text(_fm(**base), encoding="utf-8")
    achados = cv.validate_curated_secrets(str(codex), str(grafo))
    assert [(f.severity, f.validator, f.entity_id) for f in achados] == [
        ("error", "curated_secrets", "npc_x_segredo")
    ]
    assert "validate_curated_secrets" in cv.validate_all.__code__.co_names
    # com a marca, passa; entidade do canônico (entities.json) não exige
    doc.write_text(_fm(**base, curated="true"), encoding="utf-8")
    assert cv.validate_curated_secrets(str(codex), str(grafo)) == []
    doc.write_text(_fm(**base), encoding="utf-8")
    (grafo / "entities.json").write_text(json.dumps({"npc_x": ent}), encoding="utf-8")
    assert cv.validate_curated_secrets(str(codex), str(grafo)) == []
    assert os.path.exists(doc)


def test_roundtrip_gerador_migrate_um_dono(copia, monkeypatch, capsys):
    """P1-1: gerador (npc_mv_*) -> migrate na cópia: os 36 ids ficam na união e em UM só arquivo."""
    mod, raiz = copia
    monkeypatch.setenv("RPG_ROOT", str(raiz))
    spec = importlib.util.spec_from_file_location(
        "gen_world_living_npcs_374", ROOT / "scripts" / "gen_world_living_npcs.py"
    )
    gen = importlib.util.module_from_spec(spec)
    sys.modules["gen_world_living_npcs_374"] = gen
    spec.loader.exec_module(gen)
    grafo = raiz / "data" / "graph"
    assert gen.main() == 0
    mod.main()
    base, extra = _ids(grafo / "entities.json"), _ids(grafo / "entities_extra.json")
    mv = {i for i in base | extra if i.startswith("npc_mv_")}
    assert len(mv) == 36
    assert not any(i.startswith("npc_mv_") for i in base)
    assert not base & extra
    assert (raiz / "data" / "codex" / "npcs" / "mundo_vivo" / "npc_mv_teo_chamine.md").exists()
