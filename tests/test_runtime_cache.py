"""Suíte da spec isolar-cache-runtime — overlay gitignored p/ caches gerados.

data/bestiary.json = curadoria READ-ONLY em runtime; inimigos/NPCs/artefatos
gerados vão p/ RPG_RUNTIME_CACHE_DIR (default data/runtime/). Suíte e playtest
redirecionam o overlay — zero diff em data/ após rodar.
Ver specs/isolar-cache-runtime.md.
"""
import json
import os

import agents.bestiary as ab
import agents.npc as npc
import gamedata


def _read(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _fake_enemy(name="Espectro de Teste", **over):
    e = {"name": name, "description": "fake", "type": "Minion", "hp": 5, "max_hp": 5,
         "ac": 10, "attacks": [], "attributes": {"str": 8}, "abilities": [],
         "loot": [], "regions": []}
    e.update(over)
    return e


# --- Etapa 1: overlay do bestiário ------------------------------------------

def test_save_enemy_nao_toca_curado(monkeypatch, tmp_path):
    monkeypatch.setenv("RPG_RUNTIME_CACHE_DIR", str(tmp_path))
    before = _read(ab.BESTIARY_FILE)
    ab.save_enemy(_fake_enemy())
    assert _read(ab.BESTIARY_FILE) == before          # curadoria intocada (R1)
    overlay = _read(tmp_path / "bestiary_runtime.json")
    assert "espectro_de_teste" in overlay


def test_load_bestiary_merge_curado_vence(monkeypatch, tmp_path):
    monkeypatch.setenv("RPG_RUNTIME_CACHE_DIR", str(tmp_path))
    curated = _read(ab.BESTIARY_FILE)
    curated_id = next(iter(curated))
    ab.save_enemy(_fake_enemy("Só do Overlay"))
    ab.save_enemy(_fake_enemy("Conflito", id=curated_id, hp=1))
    db = ab.load_bestiary()
    assert "só_do_overlay" in db                      # overlay aparece (R2)
    assert db[curated_id] == curated[curated_id]      # curadoria VENCE conflito


def test_env_resolvida_no_call(monkeypatch, tmp_path):
    a, b = tmp_path / "a", tmp_path / "b"
    monkeypatch.setenv("RPG_RUNTIME_CACHE_DIR", str(a))
    ab.save_enemy(_fake_enemy("Um"))
    monkeypatch.setenv("RPG_RUNTIME_CACHE_DIR", str(b))  # troca APÓS import (R4)
    ab.save_enemy(_fake_enemy("Dois"))
    assert "um" in _read(a / "bestiary_runtime.json")
    assert "dois" in _read(b / "bestiary_runtime.json")
    assert "um" not in _read(b / "bestiary_runtime.json")


# --- Etapa 2: NPC db no overlay + migração ----------------------------------

def test_npc_db_fallback_legado_e_migracao(monkeypatch, tmp_path):
    legacy = tmp_path / "legacy_npc.json"
    legacy.write_text(json.dumps({"npc_velho": {"name": "Velho", "id": "npc_velho"}}),
                      encoding="utf-8")
    monkeypatch.setattr(npc, "NPC_DB_FILE", str(legacy))
    monkeypatch.setenv("RPG_RUNTIME_CACHE_DIR", str(tmp_path / "runtime"))
    # overlay ausente → lê o legado (R3)
    assert "npc_velho" in npc.load_npc_db()
    # 1º save migra o legado inteiro pro overlay e NÃO regrava o legado
    before_legacy = legacy.read_text(encoding="utf-8")
    npc.save_npc_template({"name": "Nova Guia"})
    assert legacy.read_text(encoding="utf-8") == before_legacy
    overlay = _read(tmp_path / "runtime" / "npc_database.json")
    assert "npc_velho" in overlay and "npc_nova_guia" in overlay
    # com overlay presente, o load passa a ler dele
    assert "npc_nova_guia" in npc.load_npc_db()


def test_npc_db_repo_nao_e_gravado(monkeypatch, tmp_path):
    # O legado data/npc_database.json foi destrackeado (git rm --cached) — o save
    # vai p/ o overlay e NUNCA (re)cria o arquivo no repo.
    monkeypatch.setenv("RPG_RUNTIME_CACHE_DIR", str(tmp_path))
    repo_file = os.path.join(gamedata.DATA_DIR, "npc_database.json")
    existed = os.path.exists(repo_file)
    npc.save_npc_template({"name": "Fantasma do Teste"})
    assert "npc_fantasma_do_teste" in _read(tmp_path / "npc_database.json")  # overlay
    assert os.path.exists(repo_file) == existed        # não criou/alterou o repo


# --- Etapa 3: custom_artifacts + isolamento do playtest ---------------------

def test_custom_artifact_no_overlay(monkeypatch, tmp_path):
    monkeypatch.setenv("RPG_RUNTIME_CACHE_DIR", str(tmp_path))
    gamedata.save_custom_artifact("item_teste_overlay", {"name": "Item Teste"})
    try:
        overlay = _read(tmp_path / "custom_artifacts.json")
        assert "item_teste_overlay" in overlay
        assert not os.path.exists(os.path.join(gamedata.DATA_DIR,
                                               "custom_artifacts.json")) or \
            "item_teste_overlay" not in _read(
                os.path.join(gamedata.DATA_DIR, "custom_artifacts.json"))
    finally:
        gamedata.ARTIFACTS_DB.pop("item_teste_overlay", None)
        gamedata.CUSTOM_ARTIFACTS.pop("item_teste_overlay", None)
        if "item_teste_overlay" in gamedata.ALL_ARTIFACT_IDS:
            gamedata.ALL_ARTIFACT_IDS.remove("item_teste_overlay")


def test_runner_isola_cache_runtime(monkeypatch, tmp_path):
    from playtest import runner
    monkeypatch.setenv("RPG_RUNTIME_CACHE_DIR", str(tmp_path))
    with runner._isolated_runtime_cache():
        inside = os.environ["RPG_RUNTIME_CACHE_DIR"]
        assert runner.PLAYTEST_SAVES_DIR in inside     # overlay dentro do run (R6)
    assert os.environ["RPG_RUNTIME_CACHE_DIR"] == str(tmp_path)  # restaurado


# --- Etapa 4: leitores unificados -------------------------------------------

def test_discovery_ve_criatura_do_overlay(monkeypatch, tmp_path):
    from services import discovery as disc
    monkeypatch.setenv("RPG_RUNTIME_CACHE_DIR", str(tmp_path))
    ab.save_enemy(_fake_enemy("Larva do Overlay", regions=["nova_arcadia"]))
    bk = {"larva_do_overlay": {"seen": 1, "fought": 1, "defeated": 0}}
    view = disc.bestiary_view(bk)
    assert any(v["id"] == "larva_do_overlay" for v in view)
    assert disc.normalize_bestiary_id({"id": "larva_do_overlay_2"}) == "larva_do_overlay"
