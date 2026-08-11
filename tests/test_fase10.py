"""Fase 10 — hardening técnico local: save_path anti-traversal, schema_version
+ migrations, CORS por env, rate limit, log de turno.

Spec: specs/fase-10-hardening-tecnico.md.
"""

from __future__ import annotations

import json
import os
import uuid

import pytest

import persistence
from persistence import (
    SCHEMA_VERSION,
    migrate_state,
    save_game_state,
    load_game_state,
    save_path,
)


# ---------------------------------------------------------------------------
# Etapa 1 — save_path + validação de game_id
# ---------------------------------------------------------------------------

def test_save_path_uuid_valido():
    gid = str(uuid.uuid4())
    path = save_path(gid)
    assert path == os.path.join(persistence.SAVES_DIR, f"{gid}.json")


@pytest.mark.parametrize("malicioso", [
    "../.env", "..\\secrets", "a/b", "autosave", "", "None",
    "6f1c; rm -rf", "....//....//etc",
])
def test_save_path_rejeita_nao_uuid(malicioso):
    with pytest.raises(ValueError):
        save_path(malicioso)


def test_endpoint_400_com_game_id_invalido():
    from fastapi.testclient import TestClient
    import api

    client = TestClient(api.app)
    r = client.get("/game/state", params={"game_id": "../.env"})
    assert r.status_code == 400
    r = client.post("/game/action",
                    json={"input_text": "olá", "game_id": "../../x"})
    assert r.status_code == 400


def test_game_id_none_resolve_para_none():
    import api
    assert api._resolve_save_file(None) is None
    assert api._resolve_save_file("") is None


# ---------------------------------------------------------------------------
# Etapa 2 — schema_version + migrations
# ---------------------------------------------------------------------------

def _estado_minimo(gid: str) -> dict:
    return {
        "game_id": gid,
        "player": {"name": "Testa", "class_name": "Guerreiro", "hp": 10,
                   "max_hp": 10, "inventory": [], "known_abilities": []},
        "world": {"current_location": "Nova Arcádia"},
        "messages": [],
    }


def test_save_novo_tem_schema_version(tmp_path, monkeypatch):
    monkeypatch.setattr(persistence, "SAVES_DIR", str(tmp_path))
    gid = str(uuid.uuid4())
    assert save_game_state(_estado_minimo(gid))
    raw = json.load(open(tmp_path / f"{gid}.json", encoding="utf-8"))
    assert raw["schema_version"] == SCHEMA_VERSION


def test_save_v0_fica_arquivado_no_cutover_v4():
    raw_v0 = {
        "game_id": str(uuid.uuid4()),
        "chronicle": ["Era uma vez.", "Fim do turno 3."],  # formato pré-3.1
        "player": {"name": "Velho Save", "class_name": "Guerreiro",
                   "inventory": ["Espada Curta"],           # pré-4.3 (strings)
                   "known_abilities": ["Ataque Básico"]},   # pré-4.1 (nomes)
        "party": [],
    }
    migrado = migrate_state(raw_v0)
    assert migrado["schema_version"] == SCHEMA_VERSION
    assert migrado["archived"] is True
    assert "Sistema de Conflitos" in migrado["archived_reason"]


def test_migration_idempotente():
    raw_v0 = {"game_id": str(uuid.uuid4()), "chronicle": ["A."],
              "player": {"name": "X", "class_name": "Guerreiro",
                         "inventory": [], "known_abilities": []},
              "party": []}
    uma = migrate_state(dict(raw_v0))
    duas = migrate_state(json.loads(json.dumps(uma)))
    assert uma == duas


def test_save_versao_atual_nao_migra():
    raw = {"schema_version": SCHEMA_VERSION, "game_id": str(uuid.uuid4())}
    out = migrate_state(raw)
    assert out is raw
    assert "archived" not in out
    assert out["schema_version"] == SCHEMA_VERSION


def test_roundtrip_save_load_antigo_arquivado(tmp_path, monkeypatch):
    monkeypatch.setattr(persistence, "SAVES_DIR", str(tmp_path))
    gid = str(uuid.uuid4())
    v0 = {"game_id": gid, "chronicle": ["Primeira linha."],
          "player": {"name": "Antigo", "class_name": "Guerreiro",
                     "inventory": ["Adaga"], "known_abilities": []},
          "party": [], "message_history": []}
    caminho = tmp_path / f"{gid}.json"
    caminho.write_text(json.dumps(v0, ensure_ascii=False), encoding="utf-8")

    state = load_game_state(str(caminho))
    assert state is not None
    assert state["archived"] is True


# ---------------------------------------------------------------------------
# Etapa 3 — CORS + rate limit + log
# ---------------------------------------------------------------------------

def test_cors_default_nao_e_wildcard():
    import api
    assert "*" not in api._CORS_ORIGINS
    assert any("localhost" in o for o in api._CORS_ORIGINS)


def test_rate_limit_429_apos_janela(monkeypatch):
    from fastapi.testclient import TestClient
    import api

    monkeypatch.setenv("RPG_RATE_LIMIT", "2")
    api._rate_hits.clear()
    client = TestClient(api.app)
    corpo = {"input_text": "oi", "game_id": "../x"}  # 400 barato, conta na janela
    codes = [client.post("/game/action", json=corpo).status_code for _ in range(4)]
    assert 429 in codes
    api._rate_hits.clear()


def test_rate_limit_desligado(monkeypatch):
    from fastapi.testclient import TestClient
    import api

    monkeypatch.setenv("RPG_RATE_LIMIT", "0")
    api._rate_hits.clear()
    client = TestClient(api.app)
    corpo = {"input_text": "oi", "game_id": "../x"}
    codes = [client.post("/game/action", json=corpo).status_code for _ in range(5)]
    assert 429 not in codes


def test_log_de_turno_e_json_valido(caplog, monkeypatch):
    import api  # noqa: F401 — garante o handler do logger configurado
    import logging

    logger = logging.getLogger("rpg.turn")
    monkeypatch.setattr(logger, "propagate", True)  # deixa o caplog ver o record
    linha = json.dumps({"evt": "turn", "game_id": "x", "turn": 1,
                        "route": "STORY", "latency_ms": 10,
                        "events_applied": 0, "events_rejected": 0, "error": None})
    with caplog.at_level(logging.INFO, logger="rpg.turn"):
        logger.info(linha)
    registro = json.loads(caplog.records[-1].message)
    assert registro["evt"] == "turn" and registro["error"] is None
