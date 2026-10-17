"""SPEC-211 — dossiês vivos do Codex/Bestiário (offline, zero LLM)."""
from __future__ import annotations

import copy
import json

import pytest

from services import dossiers as dz
from services import memory_provenance as mp
from services.dossier_visibility import DossiersResponseModel

RATO = "enemy_rato_peste_anel_lama"
HIDDEN_LOC = "mon_verme_primordial_das_raizes_do_mundo"


def _state(**extra):
    base = {
        "game_id": "pytest_spec211", "narrative_summary": "", "messages": [],
        "player": {"name": "Tester", "class_name": "Devoto do Abismo", "race": "Humano"},
        "world": {"current_location": "Nova Arcádia", "current_location_id": "nova_arcadia",
                  "turn_count": 12, "visited": ["nova_arcadia"]},
        "npcs": {}, "factions": [], "faction_intel": {}, "bestiary_knowledge": {},
        "event_log": [], "world_projection": {}, "memory_facts": [], "chronicle": [],
    }
    base.update(extra)
    return base


def _grum(**over):
    npc = {"name": "Grum", "role": "Ferreiro", "location": "Nova Arcádia",
           "knowledge_source": "met", "known_by_player": True, "relationship": 5,
           "created_turn": 2, "last_seen_turn": 9,
           "hidden_traits": ["segredo_sombrio"], "revealed_traits": [],
           "memory": ["PRIVADO: Grum esconde a chave do cofre do Verme."]}
    npc.update(over)
    return npc


def _mem(text, provenance, *, turn=3, entities=("npc_grum",), source_id=None):
    return mp.make_memory_fact(text, provenance=provenance, source_id=source_id,
                               source_turn=turn, canonical_entity_ids=list(entities))


def _npc(state, name="Grum"):
    return next(d for d in dz.build_dossiers(state)["sections"]["npcs"] if d["title"] == name)


# --- NPC -------------------------------------------------------------------

def test_npc_dossier_exclui_hidden_traits():
    out = dz.build_dossiers(_state(npcs={"Grum": _grum()}))
    blob = json.dumps(out, ensure_ascii=False)
    assert "hidden_traits" not in blob and "segredo_sombrio" not in blob


def test_npc_nao_conhecido_nao_aparece():
    state = _state(npcs={"Grum": _grum(known_by_player=False)})
    assert dz.build_dossiers(state)["sections"]["npcs"] == []


def test_npc_sem_known_by_player_segue_spec206():
    # Ausência da chave = conhecido (regra do codex SPEC-206).
    npc = _grum()
    npc.pop("known_by_player")
    assert _npc(_state(npcs={"Grum": npc}))["id"] == "npc_grum"


def test_npc_oculto_some_inteiro(monkeypatch):
    from services import player_knowledge as pk
    real = pk._entity_visibility
    monkeypatch.setattr(pk, "_entity_visibility",
                        lambda eid: "hidden" if eid == "npc_grum" else real(eid))
    out = dz.build_dossiers(_state(npcs={"Grum": _grum()}))
    assert out["sections"]["npcs"] == []
    assert "Grum" not in json.dumps(out, ensure_ascii=False)


def test_appears_to_know_so_de_fatos_publicos():
    # Memória privada do NPC + relato/inferência: não alimentam a lista.
    state = _state(npcs={"Grum": _grum()}, memory_facts=[
        _mem("Grum ouviu um rumor distante.", "npc_claim", source_id="npc:x"),
        _mem("Talvez Grum saiba mais.", "inference"),
    ])
    d = _npc(state)
    assert d["appears_to_know"] == []
    assert "PRIVADO" not in json.dumps(d, ensure_ascii=False)


def test_appears_to_know_observacao_do_jogador_e_perception():
    state = _state(npcs={"Grum": _grum()}, memory_facts=[
        _mem("Contei a Grum sobre a ponte.", "player_observation", turn=8)])
    d = _npc(state)
    assert len(d["appears_to_know"]) == 1
    k = d["appears_to_know"][0]["knowledge"]
    assert k["knowledge_kind"] in ("perception", "suspicion")
    assert k["certainty"] != "confirmed"
    assert k["last_updated_turn"] == 8


def test_claims_trazem_knowledge_stamp():
    state = _state(npcs={"Grum": _grum()}, memory_facts=[
        _mem("Vi Grum forjar.", "player_observation")])
    claim = _npc(state)["claims"][0]
    assert set(claim) == {"text", "knowledge"}
    assert "source_turn" not in claim and "source_turn" not in claim["knowledge"]
    assert claim["knowledge"]["label"]


@pytest.mark.parametrize("rel,label", [
    (0, "Hostil"), (1, "Hostil"), (2, "Desconfiado"), (3, "Desconfiado"),
    (4, "Neutro"), (5, "Neutro"), (6, "Neutro"), (7, "Amistoso"), (8, "Amistoso"),
    (9, "Leal"), (10, "Leal"), (None, "Neutro"), ("x", "Neutro"), (99, "Leal"), (-4, "Hostil"),
])
def test_disposition_label_por_faixa(rel, label):
    assert dz.disposition_label(rel) == label


def test_encounters_teto_20():
    events = [{"event_id": f"e{i}", "type": "quest_completed", "target_id": "npc_grum",
               "turn": i, "payload": {}} for i in range(40)]
    d = _npc(_state(npcs={"Grum": _grum()}, event_log=events))
    assert len(d["encounters"]) == 20
    assert d["encounters"][-1]["turn"] == 39
    assert [e["turn"] for e in d["encounters"]] == sorted(e["turn"] for e in d["encounters"])


def test_dossie_nao_copia_last_memory():
    d = _npc(_state(npcs={"Grum": _grum()}))
    assert "last_memory" not in d and "memory" not in d
    assert "PRIVADO" not in json.dumps(d, ensure_ascii=False)


def test_version_igual_last_updated_turn_e_estavel():
    d = _npc(_state(npcs={"Grum": _grum()}))
    assert d["version"] == d["last_updated_turn"] == 9
    assert d["version"] == _npc(_state(npcs={"Grum": _grum()}))["version"]


def test_npc_arte_so_com_asset_publico():
    assert _npc(_state(npcs={"Grum": _grum()}))["art"] is not None
    sem_arte = _npc(_state(npcs={"Ze": _grum(name="Ze")}), "Ze")
    assert sem_arte["art"] is None


# --- Local / Facção / Crônica ---------------------------------------------

def test_local_nao_visitado_ausente():
    out = dz.build_dossiers(_state())
    assert [d["id"] for d in out["sections"]["locations"]] == ["nova_arcadia"]
    state = _state()
    state["world"]["visited"] = ["nova_arcadia", HIDDEN_LOC]
    out = dz.build_dossiers(state)
    assert [d["id"] for d in out["sections"]["locations"]] == ["nova_arcadia"]
    assert HIDDEN_LOC not in json.dumps(out)


def _faction_state(knows_goal, intel_turn=12, seen=40):
    return _state(
        factions=[{"id": "legiao_ferro", "name": "Legião de Ferro", "goal": "Proteger o norte",
                   "region": "norte", "disposition": "neutro", "reputation": 3}],
        faction_intel={"legiao_ferro": {"known": True, "knows_goal": knows_goal,
                                        "progress_seen": seen, "intel_turn": intel_turn}})


def test_faccao_goal_so_com_knows_goal():
    sem = dz.build_dossiers(_faction_state(False))["sections"]["factions"][0]
    assert sem["goal"] == "" and sem["knows_goal"] is False
    com = dz.build_dossiers(_faction_state(True))["sections"]["factions"][0]
    assert com["goal"] == "Proteger o norte"
    assert com["progress"] == 40 and com["intel_stale"] is False


def test_faccao_intel_stale_rotulada():
    d = dz.build_dossiers(_faction_state(True, intel_turn=3))["sections"]["factions"][0]
    assert d["intel_stale"] is True and d["progress"] is None
    assert d["stale_label"] == "informação defasada"


def test_faccao_desconhecida_ausente():
    state = _state(factions=[{"id": "legiao_ferro", "name": "Legião"}])
    assert dz.build_dossiers(state)["sections"]["factions"] == []


def test_cronica_indice_por_capitulo_com_entity_id_conhecido():
    state = _state(
        npcs={"Grum": _grum()},
        event_log=[{"event_id": "ev1", "type": "npc_killed", "target_id": "npc_grum", "turn": 5},
                   {"event_id": "ev2", "type": "npc_killed", "target_id": HIDDEN_LOC, "turn": 6}],
        chronicle=[{"chapter_id": "c1", "title": "Arco I", "started_turn": 1,
                    "location": "Nova Arcádia", "entries": [
                        {"text": "Grum tombou.", "turn": 5, "kind": "milestone", "event_id": "ev1"},
                        {"text": "Algo caiu.", "turn": 6, "kind": "milestone", "event_id": "ev2"}]}])
    cap = dz.build_dossiers(state)["sections"]["chronicle_index"][0]
    assert cap["arc_title"] == "Arco I" and cap["entry_count"] == 2
    assert cap["entity_ids"] == ["npc_grum"]  # oculto/desconhecido nunca vinculado


# --- Bestiário ---------------------------------------------------------------

TIER_COUNTS = {1: {"seen": 1}, 2: {"seen": 1, "fought": 1},
               3: {"seen": 1, "fought": 1, "defeated": 3},
               4: {"seen": 1, "fought": 1, "defeated": 7}}
ABOVE = {1: {"description", "type", "max_hp", "defense", "attacks", "behavior", "loot"},
         2: {"max_hp", "defense", "attacks", "behavior", "loot"},
         3: {"behavior", "loot"}, 4: set()}


@pytest.mark.parametrize("tier", [1, 2, 3, 4])
def test_criatura_chaves_acima_do_tier_ausentes(tier):
    state = _state(bestiary_knowledge={RATO: {**TIER_COUNTS[tier], "first_seen_turn": 2,
                                              "last_update_turn": 7}})
    c = dz.build_dossiers(state)["bestiary"][0]
    assert c["tier"] == tier
    for field in ABOVE[tier]:
        assert field not in c
    if tier >= 2:
        assert "description" in c and "type" in c
    if tier >= 3:
        assert "max_hp" in c and "attacks" in c
    if tier == 4:
        assert "behavior" in c and "loot" in c


def test_last_updated_turn_vem_de_last_update_turn():
    state = _state(bestiary_knowledge={RATO: {"seen": 1, "first_seen_turn": 2,
                                              "last_update_turn": 7}})
    c = dz.build_dossiers(state)["bestiary"][0]
    assert c["last_updated_turn"] == 7 == c["version"] and c["first_seen_turn"] == 2


def _overlay(monkeypatch, data):
    from services import bestiary_knowledge as bk
    monkeypatch.setattr(bk, "_load_all", lambda **kw: data)


def test_cartas_resistencias_so_reveladas(monkeypatch):
    _overlay(monkeypatch, {RATO: {"revealed_cards": ["bst_fuga_suja"],
                                  "revealed_resistances": ["fogo"]}})
    state = _state(bestiary_knowledge={RATO: TIER_COUNTS[2]})
    c = dz.build_dossiers(state)["bestiary"][0]
    assert [x["id"] for x in c["revealed_cards"]] == ["bst_fuga_suja"]
    assert c["revealed_resistances"] == ["fogo"]
    assert "bst_mordida_infecciosa" not in json.dumps(c)  # carta não revelada


def test_sem_revelacao_chaves_ausentes(monkeypatch):
    _overlay(monkeypatch, {})
    c = dz.build_dossiers(_state(bestiary_knowledge={RATO: TIER_COUNTS[3]}))["bestiary"][0]
    assert "revealed_cards" not in c and "revealed_resistances" not in c


def test_tier1_nunca_revela_cartas(monkeypatch):
    _overlay(monkeypatch, {RATO: {"revealed_cards": ["bst_fuga_suja"]}})
    c = dz.build_dossiers(_state(bestiary_knowledge={RATO: TIER_COUNTS[1]}))["bestiary"][0]
    assert "revealed_cards" not in c


def test_variante_exclusiva_oculta(monkeypatch):
    _overlay(monkeypatch, {RATO: {"revealed_cards": ["bst_fuga_suja"]}})
    db = copy.deepcopy(dz.discovery._bestiary_db())
    db[RATO]["variant_exclusive_cards"] = ["bst_fuga_suja"]
    monkeypatch.setattr(dz.discovery, "_bestiary_db", lambda: db)
    c = dz.build_dossiers(_state(bestiary_knowledge={RATO: TIER_COUNTS[2]}))["bestiary"][0]
    assert "revealed_cards" not in c


def test_criatura_adhoc_fora():
    state = _state(bestiary_knowledge={"enemy_inexistente": {"seen": 5, "fought": 5}})
    assert dz.build_dossiers(state)["bestiary"] == []


def test_payload_passa_no_modelo_estrito():
    state = _state(npcs={"Grum": _grum()}, bestiary_knowledge={RATO: TIER_COUNTS[4]})
    DossiersResponseModel.model_validate(dz.build_dossiers(state))


def test_perfil_com_banco_nao_le_overlay_legado_compartilhado(monkeypatch):
    """Revisão Sol: o overlay do bestiário é escopo do dono LEGADO (único jogador
    local). Em perfil com banco (multi-tenant) ler esse escopo mostraria a um
    jogador o que outro revelou — o dossiê não revela nada ali."""
    _overlay(monkeypatch, {RATO: {"revealed_cards": ["bst_fuga_suja"],
                                  "revealed_resistances": ["fogo"]}})
    base = {"id": RATO}
    assert dz._revealed_for(base, 3)[0]  # legacy: overlay do jogador local vale
    monkeypatch.setenv("RPG_RUNTIME_PROFILE", "local")
    assert dz._revealed_for(base, 3) == ([], [])
