"""Suíte da Fase 5.2 — invariantes de estado (offline, MockLLM)."""
import copy
import uuid

import pytest

from playtest import invariants as inv
from playtest.runner import run_campaign, _build_initial_state


def _base() -> dict:
    """Estado inicial válido (mesmo shape de /game/new), sem passar pelo grafo."""
    return _build_initial_state("teste", 0)


def _ids(violations):
    return {v.check_id for v in violations}


# --- Etapa 1 — vitals + economia -------------------------------------------

def test_estado_saudavel_zero_violacoes():
    assert inv.check_all(_base()) == []


def test_hp_negativo_acusa():
    st = _base()
    st["player"]["hp"] = -3
    assert "vitals.hp_bounds" in _ids(inv.check_all(st))


def test_hp_zero_sem_game_over_acusa():
    st = _base()
    st["player"]["hp"] = 0
    st["game_over"] = False
    ids = _ids(inv.check_all(st))
    assert "vitals.dead_no_game_over" in ids
    assert "vitals.hp_bounds" not in ids  # 0 está dentro de [0, max]


def test_ouro_negativo_acusa():
    st = _base()
    st["player"]["gold"] = -50
    assert "economy.gold_negative" in _ids(inv.check_all(st))


def test_unique_duplicado_acusa():
    from gamedata import ARTIFACTS_DB
    uid = next(iid for iid, a in ARTIFACTS_DB.items() if isinstance(a, dict) and a.get("unique"))
    st = _base()
    st["player"]["inventory"] = [{"id": uid, "qty": 2}]  # unique não empilha
    assert "economy.unique_dupe" in _ids(inv.check_all(st))


# --- Etapa 2 — entidades + mundo -------------------------------------------

def test_npc_morto_em_cena_acusa():
    st = _base()
    st["event_log"] = [{"type": "npc_killed", "target_id": "npc_x", "event_id": "e1", "turn": 1}]
    st["npcs"] = {"Fulano": {"id": "npc_x", "name": "Fulano", "in_scene": True}}
    assert "entities.dead_npc_in_scene" in _ids(inv.check_all(st))


def test_faccao_derrotada_no_controle_acusa():
    st = _base()
    loc = st["world"]["current_location_id"]
    st["factions"] = [{"id": "fac_x", "defeated": True}]
    st["world_projection"] = {"dynamic_edges": [
        {"id": "dyn_t", "type": "controls", "source": "fac_x", "target": loc,
         "visibility": "public"}]}
    assert "world.defeated_controls" in _ids(inv.check_all(st))


def test_local_inexistente_acusa():
    st = _base()
    st["world"]["current_location_id"] = "lugar_que_nao_existe_123"
    assert "world.location_unknown" in _ids(inv.check_all(st))


def test_relogio_regressivo_acusa():
    prev = _base()
    prev["world"]["world_clock"] = {"day": 5, "period": "Amanhecer"}
    cur = copy.deepcopy(prev)
    cur["world"]["world_clock"] = {"day": 3, "period": "Amanhecer"}
    assert "world.clock_regressed" in _ids(inv.check_all(cur, prev, turn=2))


# --- Etapa 3 — conhecimento + roundtrip ------------------------------------

def test_assinatura_de_segredo_em_mensagem_acusa():
    from langchain_core.messages import AIMessage
    st = _base()
    st["messages"].append(AIMessage(content=
        "O velho sussurra: Valerius fez o pacto com Daruun que consumiu a família dele."))
    ids = _ids(inv.check_all(st))
    assert "knowledge.secret_leak" in ids


def test_segredo_revelado_nao_acusa():
    from langchain_core.messages import AIMessage
    st = _base()
    frase = "consumiu a família"
    st["event_log"] = [{"type": "secret_revealed", "target_id": "pacto",
                        "payload": {"detail": frase}, "event_id": "e1", "turn": 1}]
    st["messages"].append(AIMessage(content=f"Enfim a verdade: {frase} em troca de poder."))
    # 'consumiu a família' está no corpus revelado → desarmado
    leaks = [v for v in inv.check_all(st) if v.check_id == "knowledge.secret_leak"
             and v.details.get("phrase") == frase]
    assert leaks == []


def test_roundtrip_save_load_equivalente(monkeypatch, tmp_path):
    import persistence
    monkeypatch.setattr(persistence, "SAVES_DIR", str(tmp_path))
    st = _base()
    st["game_id"] = str(uuid.uuid4())
    persistence.save_game_state(st)
    loaded = persistence.load_game_state(persistence.save_path(st["game_id"]))
    # loaded já passou pelas migrations; um 2º roundtrip é ponto fixo.
    v = inv.check_roundtrip(loaded)
    assert v == [], [x.message for x in v]


# --- Etapa 4 — integração no runner ----------------------------------------

def test_campanha_com_invariantes_zero_errors():
    for profile in ("explorador", "comerciante"):
        res = run_campaign(profile, turns=10, seed=13, invariants=True)
        erros = [v for v in res.violations if v.get("severity") == "error"]
        assert erros == [], (profile, erros)


def test_violacao_plantada_aparece_no_result(monkeypatch):
    import main

    class _Corrupt:
        def __init__(self, real):
            self.real, self.n = real, 0

        def invoke(self, state, *a, **k):
            self.n += 1
            out = self.real.invoke(state, *a, **k)
            if self.n == 3:  # turno 2 (call 1 = abertura)
                out["player"]["gold"] = -100
            return out

    monkeypatch.setattr(main, "app", _Corrupt(main.app))
    res = run_campaign("explorador", turns=4, seed=1, invariants=True)
    assert res.turns_completed == 4
    assert any(v.get("check_id") == "economy.gold_negative" for v in res.violations)
