"""Auditoria 2026-07-13 (A1–A8) — regressão dos fixes de bugs/hardening.

A1 level sem bound · A2 memorial em equip/levelup · A3 save_game_state com
game_id cru · A4 flag simulated · A6 500 vazando str(e) · A7 input gigante ·
A8 dict do rate limit sem teto. (A5 = default de bind, linha de config.)
"""
import time
import uuid
from collections import deque

import pytest
from fastapi.testclient import TestClient

import persistence


@pytest.fixture()
def client():
    import api
    api._rate_hits.clear()
    return TestClient(api.app)


@pytest.fixture()
def saves_dir(tmp_path, monkeypatch):
    """Isola os saves do teste (mesmo knob que o playtest usa)."""
    monkeypatch.setattr(persistence, "SAVES_DIR", str(tmp_path))
    return tmp_path


def _estado_minimo(game_id: str, game_over: bool = False) -> dict:
    return {
        "game_id": game_id,
        "player": {"name": "T", "class_name": "Guerreiro", "level": 1,
                   "inventory": [], "known_abilities": ["ataque_basico"],
                   "equipment": {"weapon": None, "armor": None, "accessory": None}},
        "world": {"current_location": "Nova Arcádia", "current_location_id": "nova_arcadia",
                  "turn_count": 1},
        "messages": [],
        "game_over": game_over,
    }


# --- A1: /game/new valida level na borda ------------------------------------

def _payload_new(level):
    return {"name": "Teste", "race": "Humano", "class_name": "Guerreiro",
            "region": "Nova Arcádia", "level": level}


def test_new_game_level_negativo_e_422(client):
    r = client.post("/game/new", json=_payload_new(-5))
    assert r.status_code == 422  # antes: criava save com ouro NEGATIVO (50×level)


def test_new_game_level_zero_e_gigante_sao_422(client):
    assert client.post("/game/new", json=_payload_new(0)).status_code == 422
    assert client.post("/game/new", json=_payload_new(999)).status_code == 422


# --- A2: memorial (game_over) barra equip/levelup ---------------------------

def test_equip_e_levelup_em_memorial_devolvem_409(client, saves_dir):
    gid = str(uuid.uuid4())
    assert persistence.save_game_state(_estado_minimo(gid, game_over=True))

    r = client.post("/game/equip", json={"item_id": "espada_curta", "game_id": gid})
    assert r.status_code == 409
    r = client.post("/game/levelup", json={"choice_id": "x", "game_id": gid})
    assert r.status_code == 409


def test_equip_em_save_vivo_nao_e_409(client, saves_dir):
    gid = str(uuid.uuid4())
    assert persistence.save_game_state(_estado_minimo(gid, game_over=False))
    r = client.post("/game/equip", json={"item_id": "nao_existe", "game_id": gid})
    assert r.status_code == 400  # rejeitado pelo inventário, não pelo memorial


# --- A3: save_game_state nunca escreve fora de saves/ -----------------------

def test_save_game_state_sanitiza_game_id_malicioso(saves_dir, tmp_path):
    assert persistence.save_game_state(_estado_minimo("../../evil"))
    escritos = list(saves_dir.glob("*.json"))
    assert len(escritos) == 1
    assert escritos[0].name == "evil.json"          # separadores/dots removidos
    assert not (saves_dir.parent / "evil.json").exists()


def test_save_game_state_uuid_continua_no_caminho_canonico(saves_dir):
    gid = str(uuid.uuid4())
    assert persistence.save_game_state(_estado_minimo(gid))
    assert (saves_dir / f"{gid}.json").exists()


def test_save_game_state_legado_autosave_preservado(saves_dir):
    assert persistence.save_game_state(_estado_minimo("autosave"))
    assert (saves_dir / "autosave.json").exists()


# --- A4: flag simulated espelha o get_llm -----------------------------------

def _limpa_env_llm(monkeypatch):
    from llm_setup import PROVIDER_KEY_ENV
    for var in ("RPG_FORCE_MOCK", "RPG_NO_MOCK", "LLM_PROVIDER", *PROVIDER_KEY_ENV.values()):
        monkeypatch.delenv(var, raising=False)


def test_is_simulated_sem_key_nenhuma(monkeypatch):
    from llm_setup import is_simulated
    _limpa_env_llm(monkeypatch)
    assert is_simulated() is True


def test_is_simulated_groq_sem_google_e_real(monkeypatch):
    # O bug A4: só GROQ_API_KEY (jogo 100% real no Groq) reportava simulated=True.
    from llm_setup import is_simulated
    _limpa_env_llm(monkeypatch)
    monkeypatch.setenv("GROQ_API_KEY", "gsk_fake")
    assert is_simulated() is False


def test_is_simulated_force_mock_vence(monkeypatch):
    from llm_setup import is_simulated
    _limpa_env_llm(monkeypatch)
    monkeypatch.setenv("GROQ_API_KEY", "gsk_fake")
    monkeypatch.setenv("RPG_FORCE_MOCK", "1")
    assert is_simulated() is True


def test_is_simulated_provider_legado_gemini_sem_key(monkeypatch):
    from llm_setup import is_simulated
    _limpa_env_llm(monkeypatch)
    monkeypatch.setenv("LLM_PROVIDER", "gemini")
    assert is_simulated() is True   # LLM_PROVIDER=gemini sem GOOGLE_API_KEY → MockLLM
    monkeypatch.setenv("GOOGLE_API_KEY", "fake")
    assert is_simulated() is False


# --- A6: 500 não vaza detalhe interno ---------------------------------------

def test_500_no_action_nao_vaza_excecao(client, saves_dir, monkeypatch):
    import api

    gid = str(uuid.uuid4())
    assert persistence.save_game_state(_estado_minimo(gid))

    class _Boom:
        def invoke(self, *_a, **_k):
            raise RuntimeError("segredo-interno-c:\\caminho\\privado")

    monkeypatch.setattr(api, "game_graph", _Boom())
    r = client.post("/game/action", json={"input_text": "olá", "game_id": gid})
    assert r.status_code == 500
    assert "segredo-interno" not in r.text


# --- A7: input_text com teto -------------------------------------------------

def test_action_input_gigante_e_422(client):
    r = client.post("/game/action", json={"input_text": "a" * 5000})
    assert r.status_code == 422


# --- A8: dict do rate limit tem teto ----------------------------------------

def test_rate_hits_poda_ips_vencidos(monkeypatch):
    import api
    monkeypatch.setenv("RPG_RATE_LIMIT", "30")
    api._rate_hits.clear()
    velho = time.monotonic() - 2 * api._RATE_WINDOW_S
    for i in range(1200):
        api._rate_hits[f"10.0.{i // 256}.{i % 256}"] = deque([velho])

    client = TestClient(api.app)
    client.post("/game/action", json={"input_text": "oi", "game_id": "../x"})  # 400 barato
    assert len(api._rate_hits) < 1200
    api._rate_hits.clear()
