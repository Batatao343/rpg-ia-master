"""Suíte da spec polish-sessao — saves na API (R1/R2), chips de combate
mecânicos (R4) e export da crônica (R5). Offline/MockLLM."""
from __future__ import annotations

import json
import os
import time
import uuid

import pytest

import persistence


# ---------------------------------------------------------------------------
# Etapa 1 — saves na API (R1/R2)
# ---------------------------------------------------------------------------

def _write_save(dirpath, gid, name="Herói", level=2, game_over=False, mtime=None):
    os.makedirs(dirpath, exist_ok=True)
    data = {
        "schema_version": persistence.SCHEMA_VERSION,
        "game_id": gid, "game_over": game_over,
        "player": {"name": name, "class_name": "Batedor das Fronteiras",
                   "level": level, "inventory": [], "known_abilities": []},
        "world": {"current_location": "Nova Arcádia",
                  "world_clock": {"day": 3, "period": "Tarde"}},
        "message_history": [],
    }
    path = os.path.join(dirpath, f"{gid}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)
    if mtime:
        os.utime(path, (mtime, mtime))
    return path


def test_list_saves_ordena_por_mtime(tmp_path, monkeypatch):
    monkeypatch.setattr(persistence, "SAVES_DIR", str(tmp_path))
    old, new = str(uuid.uuid4()), str(uuid.uuid4())
    now = time.time()
    _write_save(str(tmp_path), old, name="Antigo", mtime=now - 1000)
    _write_save(str(tmp_path), new, name="Recente", mtime=now)
    saves = persistence.list_saves()
    assert [s["name"] for s in saves] == ["Recente", "Antigo"]
    s = saves[0]
    for campo in ("game_id", "name", "class_name", "level", "location", "day",
                  "game_over", "updated_at"):
        assert campo in s, campo
    assert s["day"] == 3 and s["location"] == "Nova Arcádia"


def test_list_saves_pula_corrompido(tmp_path, monkeypatch):
    monkeypatch.setattr(persistence, "SAVES_DIR", str(tmp_path))
    gid = str(uuid.uuid4())
    _write_save(str(tmp_path), gid)
    with open(os.path.join(str(tmp_path), "lixo.json"), "w") as f:
        f.write("{nao é json")
    saves = persistence.list_saves()
    assert len(saves) == 1 and saves[0]["game_id"] == gid


def test_delete_save_remove_save_e_memoria(tmp_path, monkeypatch):
    saves_dir = tmp_path / "saves"
    mem_dir = tmp_path / "mem"
    monkeypatch.setattr(persistence, "SAVES_DIR", str(saves_dir))
    monkeypatch.setattr(persistence, "SESSION_MEMORY_DIR", str(mem_dir))
    gid = str(uuid.uuid4())
    _write_save(str(saves_dir), gid)
    os.makedirs(mem_dir / gid, exist_ok=True)
    (mem_dir / gid / "index.faiss").write_bytes(b"x")

    assert persistence.delete_save(gid) is True
    assert not os.path.exists(os.path.join(str(saves_dir), f"{gid}.json"))
    assert not os.path.exists(str(mem_dir / gid))


def test_delete_save_uuid_invalido_e_inexistente(tmp_path, monkeypatch):
    monkeypatch.setattr(persistence, "SAVES_DIR", str(tmp_path))
    with pytest.raises(ValueError):
        persistence.delete_save("../.env")
    assert persistence.delete_save(str(uuid.uuid4())) is False


@pytest.fixture()
def client(monkeypatch):
    import api
    monkeypatch.setenv("RPG_RATE_LIMIT", "0")
    api._rate_hits.clear()
    from fastapi.testclient import TestClient
    return TestClient(api.app)


def test_endpoints_saves_delete(client, tmp_path, monkeypatch):
    monkeypatch.setattr(persistence, "SAVES_DIR", str(tmp_path))
    gid = str(uuid.uuid4())
    _write_save(str(tmp_path), gid, name="ViaAPI")
    r = client.get("/game/saves")
    assert r.status_code == 200
    assert any(s["game_id"] == gid for s in r.json())

    assert client.delete("/game/save/nao-uuid").status_code == 400
    assert client.delete(f"/game/save/{uuid.uuid4()}").status_code == 404
    assert client.delete(f"/game/save/{gid}").status_code == 200
    assert all(s["game_id"] != gid for s in client.get("/game/saves").json())


# ---------------------------------------------------------------------------
# Etapa 2 — chips de combate (R4)
# ---------------------------------------------------------------------------

def _fighter(**over):
    p = {
        "name": "Chip", "class_name": "Sangromante", "level": 2,
        "hp": 20, "max_hp": 27, "mana": 0, "max_mana": 0,
        "stamina": 0, "max_stamina": 0,
        "entropy": 16, "max_entropy": 16, "abyss_charge": 0,
        "known_cards": ["san_corte_troca", "san_finta"],
        "prepared_cards": ["san_corte_troca", "san_finta"],
        "card_usage": {}, "virtue_cards": [], "evolved_cards": {},
        "active_conditions": [],
        "inventory": [{"id": "pocao_cura", "qty": 2}],
        "equipment": {"weapon": "adaga_ferro", "armor": None, "accessory": None},
    }
    p.update(over)
    return p


_ENEMY = [{"id": "e1", "name": "Lobo", "status": "ativo", "hp": 10, "max_hp": 10}]
_COMBAT = {"active": True, "round": 1, "order": []}


def test_combat_suggestions_carta_pronta_vira_chip():
    from services import cards
    chips = cards.combat_card_suggestions(_fighter(), _ENEMY, _COMBAT)
    nomes = {cards.get_card("san_corte_troca")["name"],
             cards.get_card("san_finta")["name"]}
    assert nomes & set(chips)
    assert "Fugir" in chips
    assert any(c.startswith("Beber ") for c in chips)
    assert len(chips) <= 5


def test_carta_usada_no_turno_ou_sem_recurso_nao_vira_chip():
    from services import cards
    nome_finta = cards.get_card("san_finta")["name"]
    chips = cards.combat_card_suggestions(
        _fighter(card_usage={"san_finta": {"used_this_turn": 1}}),
        _ENEMY, _COMBAT)
    assert nome_finta not in chips
    chips2 = cards.combat_card_suggestions(_fighter(entropy=0), _ENEMY, _COMBAT)
    assert nome_finta not in chips2


def test_pocao_no_inventario_vira_chip():
    from services import cards
    chips = cards.combat_card_suggestions(_fighter(inventory=[]), _ENEMY, _COMBAT)
    assert not any(c.startswith("Beber ") for c in chips)
    chips2 = cards.combat_card_suggestions(_fighter(), _ENEMY, _COMBAT)
    assert any(c.startswith("Beber ") for c in chips2)


def test_fugir_some_quando_enredado():
    from services import cards
    enredado = _fighter(active_conditions=[
        {"name": "Enredado", "dot": 0, "duration": 2, "source": "teia",
         "control": "root"}])
    chips = cards.combat_card_suggestions(enredado, _ENEMY, _COMBAT)
    assert "Fugir" not in chips


def test_fora_de_combate_lista_vazia():
    from services import cards
    assert cards.combat_card_suggestions(_fighter(), [], _COMBAT) == []
    assert cards.combat_card_suggestions(_fighter(), _ENEMY, {"active": False}) == []
    assert cards.combat_card_suggestions(_fighter(), _ENEMY, None) == []


def test_sugestoes_no_combat_block_da_api():
    import api
    state = {"combat": dict(_COMBAT), "enemies": list(_ENEMY),
             "player": _fighter()}
    block = api._combat_block(state)
    assert "suggestions" in block and block["suggestions"]
    vazio = api._combat_block({"combat": {"active": False}, "enemies": [],
                               "player": _fighter()})
    assert vazio["suggestions"] == []


def test_chip_clicado_resolve_no_parser():
    """Texto do chip (nome exibível) → TurnDeclaration mapeia pro card_id certo."""
    from agents.combat import _parse_turn_declaration
    from services import cards
    player = _fighter()
    nome = cards.get_card("san_corte_troca")["name"]
    action = _parse_turn_declaration(player, list(_ENEMY), f"uso {nome}", {})
    assert action.acao.card_id == "san_corte_troca"


# ---------------------------------------------------------------------------
# Etapa 3 — crônica: export (R5)
# ---------------------------------------------------------------------------

def _save_com_cronica(dirpath, gid):
    os.makedirs(dirpath, exist_ok=True)
    data = {
        "schema_version": persistence.SCHEMA_VERSION,
        "game_id": gid, "game_over": False,
        "player": {"name": "Cronista", "class_name": "Batedor das Fronteiras",
                   "level": 1, "inventory": [], "known_abilities": []},
        "world": {"current_location": "Nova Arcádia",
                  "world_clock": {"day": 1, "period": "Manhã"}},
        "chronicle": [
            {"title": "O início", "started_turn": 0, "location": "Nova Arcádia",
             "entries": [{"text": "A jornada começou.", "turn": 1, "kind": "prose"},
                          {"text": "O herói alcançou o nível 2.", "turn": 4,
                           "kind": "milestone"}]},
            {"title": "Sombras no pântano", "started_turn": 6,
             "location": "Pântano", "entries": []},
        ],
        "message_history": [],
    }
    with open(os.path.join(dirpath, f"{gid}.json"), "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)


def test_chronicle_export_txt(client, tmp_path, monkeypatch):
    monkeypatch.setattr(persistence, "SAVES_DIR", str(tmp_path))
    gid = str(uuid.uuid4())
    _save_com_cronica(str(tmp_path), gid)
    r = client.get("/game/chronicle/export", params={"game_id": gid})
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/plain")
    assert "attachment" in r.headers.get("content-disposition", "")
    body = r.text
    assert "O início" in body and "Sombras no pântano" in body
    assert "A jornada começou." in body
    assert "=" * 60 in body  # separador de capítulo


def test_chronicle_export_game_id_invalido_400(client):
    r = client.get("/game/chronicle/export", params={"game_id": "../.env"})
    assert r.status_code == 400
