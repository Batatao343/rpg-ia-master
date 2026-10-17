"""SPEC-211 R10 — não-vazamento de dossiês (fixtures; o eval protegido é à parte)."""
from __future__ import annotations

import copy
import json

from services import dossiers as dz
from services import memory_provenance as mp
from services import player_knowledge as pk
from services.dossier_visibility import assert_no_private_fields, leak_view

RATO = "enemy_rato_peste_anel_lama"
HIDDEN_LOC = "mon_verme_primordial_das_raizes_do_mundo"
HIDDEN_NAME = "Verme-Primordial das Raízes do Mundo"


def _state(**extra):
    base = {
        "game_id": "pytest_leak211", "narrative_summary": "", "messages": [],
        "player": {"name": "T", "class_name": "Devoto do Abismo", "race": "Humano"},
        "world": {"current_location_id": "nova_arcadia", "turn_count": 20,
                  "visited": ["nova_arcadia", HIDDEN_LOC]},
        "npcs": {"Grum": {"name": "Grum", "role": "Ferreiro", "location": "Nova Arcádia",
                          "knowledge_source": "met", "created_turn": 1, "last_seen_turn": 9,
                          "hidden_traits": ["traco_oculto_x"], "revealed_traits": [],
                          "memory": ["PRIVADO-NPC: o cofre misterioso"],
                          "npc_secrets": ["SEGREDO-NPC"]}},
        "factions": [], "faction_intel": {},
        "bestiary_knowledge": {RATO: {"seen": 2, "fought": 2, "defeated": 7,
                                      "first_seen_turn": 3, "last_update_turn": 15}},
        "event_log": [], "world_projection": {}, "chronicle": [],
        "memory_facts": [
            mp.make_memory_fact("Vi Grum fumar o cachimbo.", provenance="player_observation",
                                source_turn=4, canonical_entity_ids=["npc_grum"]),
            mp.make_memory_fact("Algo desperta sob a montanha.", provenance="player_observation",
                                source_turn=5, canonical_entity_ids=[HIDDEN_LOC]),
        ],
    }
    base.update(extra)
    return base


def test_oraculos_verdes_sobre_payload_completo():
    state = _state()
    payload = dz.build_dossiers(state)
    assert assert_no_private_fields(payload) == []
    assert pk.assert_no_player_leak(leak_view(payload), state) == []


def test_assert_no_player_leak_spec206_verde_apos_reveal():
    state = _state(
        event_log=[{"event_id": "r1", "type": "secret_revealed", "target_id": HIDDEN_LOC, "turn": 7,
                    "payload": {"detail": "x"}},
                   {"event_id": "r2", "type": "secret_revealed",
                    "target_id": "mon_rei_subterraneo", "payload": {}}],
        world_projection={"revealed_facts": {"r1": {
            "entity_id": HIDDEN_LOC, "fact": "Desperta sob a montanha.",
            "revealed_at_turn": 7, "revealed_by_event": "r1"}}})
    payload = dz.build_dossiers(state)
    assert HIDDEN_LOC in json.dumps(payload)  # revelado: agora visível
    assert pk.assert_no_player_leak(leak_view(payload), state) == []


def test_oculto_some_inteiro_nome_contagem_e_arte():
    payload = dz.build_dossiers(_state())
    blob = json.dumps(payload, ensure_ascii=False)
    assert HIDDEN_LOC not in blob and HIDDEN_NAME not in blob
    assert [d["id"] for d in payload["sections"]["locations"]] == ["nova_arcadia"]
    assert leak_view(payload)["meta"]["counts"]["locations"] == 1


def test_trait_oculto_e_memoria_privada_nunca_trafegam():
    blob = json.dumps(dz.build_dossiers(_state()), ensure_ascii=False)
    for needle in ("traco_oculto_x", "PRIVADO-NPC", "SEGREDO-NPC", "hidden_traits", "last_memory"):
        assert needle not in blob


def test_carta_nao_revelada_nao_trafega(monkeypatch):
    from services import bestiary_knowledge as bk
    monkeypatch.setattr(bk, "_load_all", lambda **kw: {})
    blob = json.dumps(dz.build_dossiers(_state()), ensure_ascii=False)
    assert "bst_mordida_infecciosa" not in blob and "tactical_profile" not in blob


def test_assert_no_private_fields_pega_campo_extra_e_chave_proibida():
    payload = dz.build_dossiers(_state())
    bad = copy.deepcopy(payload)
    bad["sections"]["npcs"][0]["hidden_traits"] = ["x"]
    assert any("hidden_traits" in p for p in assert_no_private_fields(bad))
    bad2 = copy.deepcopy(payload)
    bad2["sections"]["npcs"][0]["campo_novo"] = 1
    assert any(p.startswith("schema:") for p in assert_no_private_fields(bad2))


def test_oraculo_pega_vazamento_de_entidade_oculta_no_payload():
    state = _state()
    payload = dz.build_dossiers(state)
    payload["sections"]["npcs"][0]["role"] = HIDDEN_NAME
    assert pk.assert_no_player_leak(leak_view(payload), state)


def test_projecao_nao_muta_o_estado():
    state = _state()
    before = copy.deepcopy(state)
    dz.build_dossiers(state)
    assert state == before


def test_sem_llm_na_projecao(monkeypatch):
    import llm_setup

    def boom(*a, **k):
        raise AssertionError("LLM chamado")
    monkeypatch.setattr(llm_setup, "get_llm", boom)
    dz.build_dossiers(_state())
