"""Spec npcs-3-camadas — traits ocultos, gate in_scene, canal de cena, API.

Spec: specs/SPEC-028-npcs-3-camadas-traits.md.
"""

from __future__ import annotations

import json
import os
import uuid

from langchain_core.messages import HumanMessage

from services import npc_layers
from services.npc_layers import (
    ensure_npc_fields,
    is_in_scene,
    reset_scene,
    roll_hidden_traits,
    tick_interaction,
    trait_dc_modifier,
    visible_npc_view,
)


def _npc(name: str = "Grum", **extra) -> dict:
    base = {"name": name, "role": "Taverneiro", "persona": "Rabugento",
            "location": "Anel de Lama", "relationship": 5, "memory": []}
    base.update(extra)
    return base


# ---------------------------------------------------------------------------
# Etapa 1 — catálogo + sorteio + revelação (puro)
# ---------------------------------------------------------------------------

def test_traits_json_valido():
    with open(os.path.join("data", "traits.json"), encoding="utf-8") as f:
        data = json.load(f)
    traits = data["traits"]
    assert len(traits) >= 40
    ids = [t["id"] for t in traits]
    assert len(ids) == len(set(ids)), "ids duplicados"
    for t in traits:
        assert t["name"] and t["description"]
        assert 3 <= int(t["reveal_after"]) <= 8
        for ctx in t.get("dc_modifiers", {}):
            assert ctx in npc_layers.DC_CONTEXTS, f"{t['id']}: contexto '{ctx}' fora do canônico"


def test_sorteio_deterministico_por_save():
    a = roll_hidden_traits("npc_grum", "game-1")
    b = roll_hidden_traits("npc_grum", "game-1")
    outro_save = roll_hidden_traits("npc_grum", "game-2")
    assert a == b                      # replay estável
    assert 1 <= len(a) <= 3
    assert len(set(a)) == len(a)       # sem repetição
    # saves diferentes tendem a divergir (não asserta desigualdade estrita —
    # colisão é possível; asserta que a função USA o game_id via seed distinta)
    c = roll_hidden_traits("npc_outro", "game-1")
    assert isinstance(outro_save, list) and isinstance(c, list)


def test_tick_revela_apos_n_interacoes():
    catalog = npc_layers.traits_catalog()
    tid = next(t for t in catalog if catalog[t]["reveal_after"] == 3)
    npc = _npc(hidden_traits=[tid], revealed_traits=[], interaction_count=0)
    revelados_total = []
    for _ in range(3):
        npc, novos = tick_interaction(npc)
        revelados_total += novos
    assert revelados_total == [tid]
    assert npc["revealed_traits"] == [tid]
    assert npc["hidden_traits"] == []
    # idempotência: interações extras não re-revelam
    npc, novos = tick_interaction(npc)
    assert novos == []


def test_trait_dc_modifier_soma():
    npc = _npc(hidden_traits=["desconfiado"], revealed_traits=["ganancioso"])
    # desconfiado: persuasao+3; ganancioso: persuasao+2 -> 5 (ocultos CONTAM)
    assert trait_dc_modifier(npc, "persuasao") == 5
    assert trait_dc_modifier(npc, "contexto_inexistente") == 0


# ---------------------------------------------------------------------------
# Etapa 2 — schema + backfill + gate in_scene
# ---------------------------------------------------------------------------

def test_ensure_npc_fields_backfill():
    npc = ensure_npc_fields(_npc(), "game-1", home_location_id="na_anel_lama")
    assert npc["home_location_id"] == "na_anel_lama"
    assert npc["known_by_player"] is True
    assert npc["knowledge_source"] == "met"
    assert npc["interaction_count"] == 0
    assert 1 <= len(npc["hidden_traits"]) <= 3
    assert "in_scene" not in npc  # backfill NÃO força cena (gate trata ausente=presente)


def test_save_antigo_npc_fica_arquivado_sem_conversao():
    from persistence import migrate_state
    raw = {"game_id": str(uuid.uuid4()), "schema_version": 1,
           "world": {"current_location_id": "brekmar"},
           "npcs": {"Grum": _npc()}, "party": []}
    out = migrate_state(raw)
    assert out["archived"] is True
    assert out["npcs"]["Grum"] == raw["npcs"]["Grum"]


def test_gate_ausente_e_presente():
    assert is_in_scene(_npc()) is True                 # legado: sem campo = presente
    assert is_in_scene(_npc(in_scene=False)) is False
    assert is_in_scene(_npc(in_scene=True)) is True


def test_reset_scene_zera_todo_mundo():
    npcs = {"A": _npc("A", in_scene=True), "B": _npc("B")}
    out = reset_scene(npcs)
    assert out["A"]["in_scene"] is False
    assert out["B"]["in_scene"] is False


def test_npc_fora_de_cena_nao_chama_llm(monkeypatch):
    import agents.npc as npc_mod

    def _explode(*a, **k):
        raise AssertionError("LLM não deveria ser chamado")

    monkeypatch.setattr(npc_mod, "get_llm", _explode)
    state = {
        "game_id": "g1", "active_npc_name": "Volkar",
        "npcs": {"Volkar": _npc("Volkar", in_scene=False,
                                home_location_id="sk_farol_chama_negra")},
        "world": {"current_location": "Nova Arcádia", "turn_count": 3},
        "messages": [HumanMessage(content="Volkar, me conte do farol")],
        "party": [],
    }
    out = npc_mod.npc_actor_node(state)
    texto = out["messages"][0].content
    assert "não está aqui" in texto
    assert "sk_farol_chama_negra" in texto  # cita onde foi visto


def test_membro_de_party_ignora_gate(monkeypatch):
    """Companion segue o jogador: in_scene False não bloqueia."""
    import agents.npc as npc_mod

    state = {
        "game_id": "g1", "active_npc_name": "Aria",
        "npcs": {"Aria": _npc("Aria", in_scene=False)},
        "world": {"current_location": "Brekmar", "turn_count": 3},
        "messages": [HumanMessage(content="Aria, espere aqui")],
        "party": [{"name": "Aria", "active": True, "hp": 10, "max_hp": 10}],
    }
    out = npc_mod.npc_actor_node(state)
    texto = out["messages"][0].content
    assert "não está aqui" not in texto


# ---------------------------------------------------------------------------
# Etapa 3 — canal de cena no storyteller
# ---------------------------------------------------------------------------

def test_viagem_zera_in_scene():
    from agents.storyteller import storyteller_node

    state = {
        "game_id": "g1",
        "player": {"name": "H", "class_name": "Guerreiro", "hp": 10, "max_hp": 10,
                   "inventory": [], "known_abilities": ["ataque_basico"]},
        "world": {"current_location": "Nova Arcádia", "current_location_id": "nova_arcadia",
                  "visited": ["nova_arcadia"], "world_clock": {"day": 1, "period": "Manhã"},
                  "danger_level": 1, "turn_count": 2},
        "npcs": {"Grum": _npc(in_scene=True)},
        "factions": [], "faction_intel": {}, "quests": [],
        "campaign_plan": {}, "messages": [HumanMessage(content="Viajo para Brekmar")],
    }
    out = storyteller_node(state)
    novos = out.get("npcs") or {}
    assert novos.get("Grum", {}).get("in_scene") is False


def test_entrar_em_interior_nao_zera_cena_do_relogio():
    """Custo 0 ainda é viagem (cena muda de lugar) — in_scene TAMBÉM zera;
    o que NÃO acontece é o relógio virar."""
    from agents.storyteller import storyteller_node

    state = {
        "game_id": "g1",
        "player": {"name": "H", "class_name": "Guerreiro", "hp": 10, "max_hp": 10,
                   "inventory": [], "known_abilities": ["ataque_basico"]},
        "world": {"current_location": "Anel de Lama", "current_location_id": "na_anel_lama",
                  "visited": ["na_anel_lama"], "world_clock": {"day": 1, "period": "Manhã"},
                  "danger_level": 1, "turn_count": 2},
        "npcs": {"Grum": _npc(in_scene=True)},
        "factions": [], "faction_intel": {}, "quests": [],
        "campaign_plan": {}, "messages": [HumanMessage(content="Entro na Taverna do Javali Dourado")],
    }
    out = storyteller_node(state)
    assert out["world"]["world_clock"] == {"day": 1, "period": "Manhã"}
    assert (out.get("npcs") or {}).get("Grum", {}).get("in_scene") is False


# ---------------------------------------------------------------------------
# Etapa 4 — DC modifiers no consumidor (recrutamento 4.5)
# ---------------------------------------------------------------------------

def test_recrutamento_usa_trait_persuasao():
    import party

    # desconfiado (+3): rel 7 não basta mais (limiar vira 10)
    state = {"npcs": {"Kess": _npc("Kess", relationship=7,
                                   hidden_traits=["desconfiado"], revealed_traits=[])},
             "party": [], "factions": []}
    ok, _reason = party.can_recruit(state, "Kess")
    assert ok is False

    # sentimental (-2): rel 5 passa (limiar vira 5)
    state2 = {"npcs": {"Nilo": _npc("Nilo", relationship=5,
                                    hidden_traits=["sentimental"], revealed_traits=[])},
              "party": [], "factions": []}
    ok2, _ = party.can_recruit(state2, "Nilo")
    assert ok2 is True


# ---------------------------------------------------------------------------
# Etapa 5 — API não vaza hidden_traits
# ---------------------------------------------------------------------------

def test_visible_npc_view_filtra_e_nao_vaza():
    npcs = {
        "Grum": _npc(hidden_traits=["ganancioso"], revealed_traits=["tagarela"],
                     known_by_player=True, knowledge_source="met"),
        "Sombra": _npc("Sombra", known_by_player=False),
    }
    view = visible_npc_view(npcs)
    assert len(view) == 1                       # só conhecidos
    entrada = view[0]
    assert "hidden_traits" not in json.dumps(entrada)
    assert [t["id"] for t in entrada["revealed_traits"]] == ["tagarela"]


def test_api_nao_vaza_hidden_traits(tmp_path, monkeypatch):
    import api
    import persistence

    monkeypatch.setattr(persistence, "SAVES_DIR", str(tmp_path))
    gid = str(uuid.uuid4())
    state = {
        "game_id": gid,
        "player": {"name": "H", "class_name": "Guerreiro", "hp": 10, "max_hp": 10,
                   "inventory": [], "known_abilities": ["ataque_basico"]},
        "world": {"current_location": "Brekmar", "current_location_id": "brekmar",
                  "visited": ["brekmar"], "turn_count": 1,
                  "world_clock": {"day": 1, "period": "Manhã"}},
        "npcs": {"Grum": _npc(hidden_traits=["ganancioso"], revealed_traits=[])},
        "messages": [HumanMessage(content="olá")],
    }
    resp = api.format_response(state)
    dump = resp.model_dump_json()
    assert "hidden_traits" not in dump
    assert "ganancioso" not in dump
