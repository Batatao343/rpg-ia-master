"""SPEC-331 (revisão Sol): nó de combate real - round-trip save/load, objetivo, espólio, API e
byte-identidade do prompt com a flag `off`."""

from __future__ import annotations

import json
import random

import agents.combat as combat
import api
from services import cards
from services import encounter_preparation as prep
from services import scene_cards as sc
from tests.test_encounter_identity_repro import _BANDIT, _install_llm, _start_state
from tests.test_encounter_lifecycle_reload import _decl, _merge, _reload


def _start(monkeypatch):
    random.seed(9)
    _install_llm(monkeypatch)
    return _decl(
        _start_state(
            combat_encounter_hint={"enemy_id": _BANDIT, "reason": "random", "hint": "Bandido"},
            world={**_start_state()["world"], "danger_level": 1},
            continuity={"session_action_count": 4, "timeline_epoch": 0},
        )
    )


def _step(state):
    out = combat.combat_node(state)
    return out, _reload(_merge(state, out))


def _tanky(state):
    for e in state["enemies"]:
        e["vitalidade"] = e["max_vitalidade"] = 500
    return state


def test_off_prompt_byte_identico(monkeypatch):
    monkeypatch.setenv("RPG_SCENE_CARDS", "off")
    ctx = {"location": "Skallgard", "enemies": [{"id": "b1", "name": "Bandido"}], "narrative": "x"}
    ids = ["player", "b1"]
    expected = (
        "Prepare a cena de conflito JOGÁVEL de Valoria em JSON curto (sem prosa).\n"
        "Local: Skallgard. Inimigos: Bandido (b1).\n"
        "Cena: x\n"
        "Regras: 1-3 zonas (id curto, name, connections por id); 0-2 objetos "
        "interativos coerentes com o local, cada um com base_narrativa curta e 1 "
        "interação; 0-1 evento do Abismo cujo base_na_cena é o id de um objeto.\n"
        f"effect.kind SÓ de: {', '.join(sorted(prep.cs.EFFECT_KINDS))}. "
        "potency SÓ de: fraco, moderado, forte, devastador (nunca números).\n"
        f"params.target (obrigatório em damage/apply_condition/reposition) SÓ de: {', '.join(ids)}."
    )
    assert prep._prep_prompt(ctx) == expected


def test_roundtrip_save_load_com_campos_novos_e_presagio(monkeypatch):
    monkeypatch.setenv("RPG_SCENE_CARDS", "on")
    monkeypatch.setitem(
        sc.catalog(),
        "t_fim",
        {
            "id": "t_fim",
            "nome": "Teste",
            "regioes": [],
            "tags": [],
            "quando": "fim_rodada",
            "desde": 1,
            "escopo": "todos",
            "efeitos": [{"kind": "torpor", "valor": 1}],
            "acoes": [],
            "pressagio": "algo vem",
            "sabor": "s",
        },
    )
    state = _tanky(_start(monkeypatch))
    _, state = _step(state)
    state["combat"]["scene"]["cartas_de_cena"] = ["t_fim"]
    state["combat"]["scene"]["objetivo"] = {"tipo": "sobreviver_n_rodadas", "n": 9}
    state = _reload(state)
    _decl(state)
    _, state = _step(state)
    meta = json.loads(json.dumps(state["combat"], default=str))
    assert meta["scene"]["cena_estado"] is not None
    assert [p["id"] for p in meta["pressagios_cena"]] == ["t_fim"]
    view = api._combat_block({"combat": meta, "enemies": [], "player": {}})
    assert view["pressagios_cena"] == meta["pressagios_cena"]
    assert view["objetivo"]["tipo"] == "sobreviver_n_rodadas" and view["objetivo"]["n"] == 9
    monkeypatch.setenv("RPG_SCENE_CARDS", "off")
    off_view = api._combat_block({"combat": meta, "enemies": [], "player": {}})
    assert "pressagios_cena" not in off_view and "objetivo" not in off_view


def test_shadow_nao_grava_pressagio_no_estado(monkeypatch):
    monkeypatch.setenv("RPG_SCENE_CARDS", "shadow")
    state = _tanky(_start(monkeypatch))
    _, state = _step(state)
    assert "pressagios_cena" not in state["combat"]


def test_objetivo_cumprido_encerra_sem_espolio_sem_queda(monkeypatch):
    monkeypatch.setenv("RPG_SCENE_CARDS", "on")
    state = _tanky(_start(monkeypatch))
    _, state = _step(state)
    state["combat"]["scene"]["objetivo"] = {"tipo": "sobreviver_n_rodadas", "n": 2}
    _decl(state)
    out, state = _step(state)
    assert state["combat"].get("active") is False
    assert out.get("next") != "loot"  # ninguém caiu: nada a saquear


def test_objetivo_falho_vira_defeat_sem_loot(monkeypatch):
    monkeypatch.setenv("RPG_SCENE_CARDS", "on")
    state = _tanky(_start(monkeypatch))
    _, state = _step(state)
    foe = state["enemies"][0]["id"]
    state["combat"]["scene"]["objetivo"] = {"tipo": "interromper_ritual", "alvo": foe, "n": 2}
    _decl(state)
    out, state = _step(state)
    assert state["combat"].get("active") is False
    assert state["combat"].get("outcome") == "defeat"
    assert out.get("next") != "loot"


def test_carta_de_objeto_recriada_no_inicio_do_no_apos_processo_novo(monkeypatch):
    monkeypatch.setenv("RPG_SCENE_CARDS", "on")
    monkeypatch.setenv("RPG_CARD_DECK", "on")
    state = _tanky(_start(monkeypatch))
    _, state = _step(state)
    assert isinstance(state["combat"].get("pilhas"), dict)
    state["combat"]["scene"]["objects"] = [
        {
            "id": "barril",
            "name": "Barril",
            "uses_remaining": 1,
            "destroyed": False,
            "interactions": [
                {
                    "label": "derrubar",
                    "effect": {"kind": "damage", "params": {"amount": 2, "target": "x"}},
                }
            ],
        }
    ]
    cards.reload_cards()  # "processo novo": a carta temporária não existe mais
    state = _reload(state)
    _decl(state)
    out = combat.combat_node(state)
    mao = out["combat"]["pilhas"]["mao"]
    temp = [c for c in mao if str(c).startswith("cena_")]
    assert temp and all(cards.get_card(c) for c in temp)
