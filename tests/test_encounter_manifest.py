"""SPEC-203 — manifesto do encontro: schema/funções puras, spawn canônico,
composição por evento, API e normalização aditiva de saves (sem bump)."""
from __future__ import annotations

import json
import random

import pytest
from langchain_core.messages import AIMessage, HumanMessage

import agents.combat as combat
import encounter_budget as eb
import gamedata
import persistence
from llm_setup import ModelTier
from services import encounter_manifest as em
from tests.test_encounter_identity_repro import (
    _BANDIT,
    _CROW,
    _bestiary_factory,
    _install_llm,
    _scan,
    _start_state,
)

_WOLF = "enemy_lobo_sombrio"


def _enemy(bid, n=1, **extra):
    return {**gamedata.BESTIARY[bid], "id": f"{bid}_{n}",
            "name": gamedata.BESTIARY[bid]["name"], "status": "ativo", **extra}


def _manifest(*enemies, source="systemic"):
    return em.build_manifest(list(enemies), source=source, origin="travel_encounter",
                             encounter_id="g:0:1", target_ref=_BANDIT)


# --- Etapa 1: schema e funções puras ----------------------------------------
def test_build_manifest_campos():
    m = _manifest(_enemy(_BANDIT))
    assert m["frozen"] is True and m["schema"] == 1
    p = m["participants"][0]
    assert p == {"participant_id": f"{_BANDIT}_1", "bestiary_id": _BANDIT,
                 "species_label": "Bandido", "faction_id": "", "categoria": "lacaio",
                 "role": "hostile", "presence": "present", "zone_id": "z0",
                 "status": "ativo"}
    em.EncounterManifest.model_validate(m)


def test_participante_imutavel_apos_freeze():
    before = _manifest(_enemy(_BANDIT))
    after = json.loads(json.dumps(before))
    after["participants"][0]["species_label"] = "Corvo de Gelo Negro"
    with pytest.raises(ValueError):
        em.assert_immutable(before, after)
    em.assert_immutable(before, em.apply_composition(before, "dead", f"{_BANDIT}_1", "x", 1))


def test_validate_roster_intruso():
    m = _manifest(_enemy(_BANDIT))
    assert em.validate_roster(m, [_enemy(_BANDIT)]) == []
    assert em.validate_roster(m, [_enemy(_BANDIT), _enemy(_CROW)]) == [f"intruder:{_CROW}_1"]
    drift = {**_enemy(_BANDIT), "name": "Corvo de Gelo Negro", "id": f"{_BANDIT}_1"}
    drift_bad = dict(drift)
    # espécie derivada do id curado prevalece: sem drift pelo nome só
    assert em.validate_roster(m, [drift_bad]) == []
    kept_manifest, kept, violations = em.reconcile_roster(m, [_enemy(_BANDIT), _enemy(_CROW)], 2)
    assert [e["id"] for e in kept] == [f"{_BANDIT}_1"]
    assert violations and kept_manifest["events"][-1]["cause"] == "roster_violation"


def test_apply_composition_idempotente():
    m = _manifest(_enemy(_BANDIT))
    once = em.apply_composition(m, "dead", f"{_BANDIT}_1", "combat_round", 2)
    twice = em.apply_composition(once, "dead", f"{_BANDIT}_1", "combat_round", 2)
    assert once == twice and len(twice["events"]) == 1
    assert twice["participants"][0]["status"] == "morto"


def test_transicoes_validas_e_invalidas():
    c = em.transition({}, "entering")
    c = em.transition(c, "active")
    c = em.transition(c, "resolving")
    c = em.transition(c, "ended", "victory")
    assert (c["phase"], c["outcome"]) == ("ended", "victory")
    with pytest.raises(em.InvalidEncounterTransition):
        em.transition(c, "active")                     # sem retorno de ended
    with pytest.raises(em.InvalidEncounterTransition):
        em.transition({"phase": "entering"}, "ended", "victory")
    assert em.transition({"phase": "entering"}, "ended", "expired")["outcome"] == "expired"
    with pytest.raises(em.InvalidEncounterTransition):
        em.transition({"phase": "active"}, "ended", "victory")
    logged = em.safe_transition({"phase": "ended"}, "active")
    assert logged["phase"] == "ended" and logged["phase_violations"]


def test_public_view_nao_vaza_oculto():
    m = _manifest(_enemy(_BANDIT), _enemy(_BANDIT, 2))
    scene = {"positions": {f"{_BANDIT}_2": {"hidden_from": ["player"]}}}
    view = em.public_view(m, scene)
    ids = [p["participant_id"] for p in view["participants"]]
    assert ids == [f"{_BANDIT}_1"]
    assert "bestiary_id" not in view["participants"][0]
    assert "faction_id" not in view["participants"][0]


def test_hint_count_e_resolucao():
    assert em.resolve_bestiary_name("bandidos") == _BANDIT
    assert em.resolve_bestiary_name("Lobos Sombrios") == _WOLF
    assert em.resolve_bestiary_name("Inimigos") is None
    assert em.hint_count("3 bandidos") == 3 and em.hint_count("dois lobos") == 2
    assert em.hint_count("Bandido") == 1 and em.hint_count("bandidos") == 2


# --- Etapa 2: spawn por fonte canônica --------------------------------------
def test_spawn_usa_enemy_id_sistemico_sem_scanner(monkeypatch):
    random.seed(4)
    calls = _install_llm(monkeypatch, scan=_scan(("Goblin", 1)))
    state = _start_state(hint="Bandido", combat_encounter_hint={
        "enemy_id": _BANDIT, "reason": "random", "hint": "Bandido"})
    meta = {}
    enemies, _ = combat._spawn_v4_enemies(state["messages"], "Bandido", state, meta)
    assert meta["source"] == "systemic" and meta["target_ref"] == _BANDIT
    assert enemies[0]["id"] == f"{_BANDIT}_1"
    assert not [c for c in calls if c[1] == ModelTier.CLASSIFY]


def test_spawn_npc_em_cena_vira_participante(monkeypatch):
    calls = _install_llm(monkeypatch, scan=_scan(("Goblin", 1)))
    state = _start_state(
        hint="Varg", combat_target_ref="npc:Varg",
        npcs={"Varg": {"name": "Varg", "in_scene": True, "role": "mercenário"}})
    meta = {}
    enemies, _ = combat._spawn_v4_enemies(state["messages"], "Varg", state, meta)
    assert meta["source"] == "npc_in_scene" and meta["target_ref"] == "Varg"
    assert enemies[0]["name"] == "Varg"
    assert not [c for c in calls if c[0] == "EncounterScanner"]


def test_scanner_so_como_fallback_validado(monkeypatch):
    calls = _install_llm(monkeypatch, scan=_scan(("Cultista Encapuzado", 2),
                                                 ("Corvo de Gelo Negro", 3)))
    created = []

    def factory(name, **_kw):
        created.append(name)
        return {"id": "enemy_cultista_encapuzado", "name": name,
                "virtudes": {"forca": 2, "agilidade": 2, "corpo": 2, "mente": 1, "carisma": 1}}

    monkeypatch.setattr(combat, "generate_new_enemy", factory)
    meta = {}
    enemies, _ = combat._spawn_v4_enemies([], "os encapuzados", None, meta)
    assert [c for c in calls if c[0] == "EncounterScanner"]
    assert meta["source"] == "scanner"
    assert created == ["Cultista Encapuzado"]          # corvo fora da dica descartado
    assert all("Corvo" not in e["name"] for e in enemies)


def test_fallback_sombrio_marca_source(monkeypatch):
    _install_llm(monkeypatch, scan=None)               # scanner falha
    meta = {}
    enemies, _ = combat._spawn_v4_enemies([], "Inimigos", None, meta)
    assert enemies[0]["name"] == "Inimigo Sombrio" and meta["source"] == "fallback"


# --- Etapa 3: composição por evento e leitura por rodada --------------------
def test_budget_emite_eventos_cut_joined():
    state = {"player": {"level": 1}, "world": {"current_location_id": "pantano_melancolia",
                                               "danger_level": 2, "turn_count": 0},
             "party": [], "combat_target": "Bandido"}
    report = {}
    enemies = [_enemy(_BANDIT, i) for i in (1, 2, 3)] + [_enemy(_CROW)]
    kept, _ = combat._apply_encounter_budget(enemies, state, "", report=report)
    kept_ids = [e["id"] for e in kept]
    assert set(report["cut_ids"]) == {e["id"] for e in enemies} - set(kept_ids) - set(
        report["joined_ids"])
    m = em.build_manifest(kept, source="threat", origin="unknown", encounter_id="x",
                          joined_ids=report["joined_ids"], cut_ids=report["cut_ids"])
    kinds = {(ev["kind"], ev["participant_id"]) for ev in m["events"]}
    for pid in report["cut_ids"]:
        assert ("cut", pid) in kinds
    for pid in report["joined_ids"]:
        assert ("joined", pid) in kinds


def test_clamp_regra_numerica_inalterada_sem_protecao():
    enemies = [_enemy(_BANDIT, i) for i in (1, 2, 3)] + [_enemy(_CROW)]
    kept, _ = eb.clamp_encounter(enemies, 4, player_level=1)
    assert sorted(e["id"] for e in kept) == sorted([f"{_BANDIT}_1", f"{_CROW}_1"])


def _merge(state, out):
    merged = {**state, **{k: v for k, v in out.items() if k != "messages"}}
    merged["messages"] = list(state["messages"]) + list(out.get("messages") or [])
    return merged


def test_rodada_sem_llm_classify(monkeypatch):
    random.seed(21)
    calls = _install_llm(monkeypatch)
    enemy = _enemy(_BANDIT)
    state = _start_state(combat_encounter_hint={"enemy_id": _BANDIT, "reason": "random",
                                                "hint": "Bandido"},
                         combat_declaration={"actor_id": "player", "acao": {"kind": "pass"}})
    out = combat.combat_node(state)
    assert not [c for c in calls if c[1] == ModelTier.CLASSIFY]
    state = _merge(state, out)
    rounds = 0
    while state["combat"].get("active") and rounds < 3:
        calls.clear()
        state["combat_declaration"] = {"actor_id": "player", "acao": {"kind": "pass"}}
        out = combat.combat_node(state)
        assert not [c for c in calls if c[1] == ModelTier.CLASSIFY]
        if out["combat"].get("active"):
            assert em.validate_roster(out["combat"]["encounter"], out["enemies"]) == []
        state = _merge(state, out)
        rounds += 1
    assert enemy["id"]


def test_saida_so_com_evento():
    m = _manifest(_enemy(_BANDIT), _enemy(_BANDIT, 2), _enemy(_BANDIT, 3))
    gone = [_enemy(_BANDIT, 1, status="morto", dead=True),
            _enemy(_BANDIT, 2, status="fugiu", fled=True),
            _enemy(_BANDIT, 3, status="rendido", surrendered=True)]
    m2 = em.sync_statuses(m, gone, 3)
    assert {(e["kind"], e["participant_id"]) for e in m2["events"]} == {
        ("dead", f"{_BANDIT}_1"), ("fled", f"{_BANDIT}_2"), ("surrendered", f"{_BANDIT}_3")}
    assert em.sync_statuses(m2, gone, 3) == m2       # idempotente
    # Sumir sem status → evento `departed` explícito.
    m3, kept, _v = em.reconcile_roster(m, [_enemy(_BANDIT)], 4)
    assert [p["presence"] for p in m3["participants"]][1:] == ["departed", "departed"]


# --- Etapa 5: API, normalização de save e prosa ------------------------------
def _fmt_state(**over):
    from tests.test_fase43 import make_player
    s = {"game_id": "g", "player": make_player(hp=10, inventory=[]),
         "world": {"current_location": "Nova Arcadia", "current_location_id": "nova_arcadia"},
         "messages": [HumanMessage(content="a"), AIMessage(content="Fim.")],
         "enemies": [], "npcs": {}}
    s.update(over)
    return s


def test_combat_block_expoe_phase_e_view():
    import api
    m = _manifest(_enemy(_BANDIT))
    state = _fmt_state(enemies=[_enemy(_BANDIT)],
                       combat={"active": True, "phase": "active", "outcome": None,
                               "encounter": m, "round": 1})
    block = api._combat_block(state)
    assert block["phase"] == "active" and block["encounter_id"] == "g:0:1"
    assert block["encounter_view"]["participants"][0]["species_label"] == "Bandido"


def test_combat_result_xp_do_evento_spec199():
    import api
    from persistence import _raw_to_state, _state_to_save_data
    m = em.sync_statuses(_manifest(_enemy(_BANDIT)),
                         [_enemy(_BANDIT, status="morto", dead=True)], 2)
    combat_meta = em.end_combat({"phase": "active", "encounter": m, "round": 2,
                                 "active": False}, "victory")
    combat_meta["result"] = em.build_result(m, "victory", 2, loot=True)
    lo = {"receipt_id": "rcp1", "turn": 4, "xp_delta": 50, "level_delta": 0,
          "level_after": 1, "gold_delta": 0, "items_gained": {}, "quests_completed": [],
          "player_message": "O bandido tomba."}
    from agents.turn_finalizer import turn_finalizer_node  # noqa: F401 (contrato)
    combat_meta["result"]["xp_event_ref"] = "rcp1"
    state = _fmt_state(combat=combat_meta, last_turn_outcome=lo, continuity={}, party=[])
    resp = api.format_response(state)
    assert resp.combat_result["xp_event_ref"] == resp.turn_outcome["receipt_id"] == "rcp1"
    assert "xp" not in json.dumps(resp.combat_result).replace("xp_event_ref", "")
    assert resp.combat_result["participants"][0]["final_status"] == "morto"
    assert "50" not in resp.message
    raw = json.loads(json.dumps(_state_to_save_data(state, "g")))
    again = api.format_response({**state, **_raw_to_state(raw)})
    assert again.combat_result == resp.combat_result      # reaparece após reload
    newer = {**lo, "receipt_id": "rcp2"}
    assert api.format_response({**state, "last_turn_outcome": newer}).combat_result == {}


def test_turn_finalizer_carimba_receipt_uma_vez():
    from agents.turn_finalizer import turn_finalizer_node
    m = _manifest(_enemy(_BANDIT))
    meta = em.end_combat({"phase": "active", "encounter": m, "round": 1}, "fled")
    meta["result"] = em.build_result(m, "fled", 1)
    state = {"game_id": "g", "combat": meta, "player": {"xp": 0}, "world": {"turn_count": 2},
             "messages": [AIMessage(content="Você escapa.")], "enemies": []}
    out = turn_finalizer_node(state)
    receipt = out["last_turn_outcome"]["receipt_id"]
    assert out["combat"]["result"]["xp_event_ref"] == receipt
    again = turn_finalizer_node({**state, "combat": out["combat"]})
    assert "combat" not in again                         # nunca reescreve


def _v8_raw(combat, enemies):
    return {"schema_version": 8, "game_id": "legacy-g",
            "player": {"name": "Kael", "vitalidade": 20, "max_vitalidade": 20},
            "world": {"current_location": "X", "turn_count": 9},
            "enemies": enemies, "combat": combat, "message_history": []}


def test_migracao_v8_combate_ativo():
    enemies = [_enemy(_BANDIT), _enemy(_BANDIT, 2)]
    state = persistence._raw_to_state(_v8_raw(
        {"active": True, "round": 2, "instance_id": "legacy-g:0:7"}, enemies))
    combat_meta = state["combat"]
    assert persistence.SCHEMA_VERSION == 8
    assert combat_meta["phase"] == "active" and combat_meta["outcome"] is None
    assert combat_meta["encounter"]["source"] == "legacy_migrated"
    assert combat_meta["encounter"]["encounter_id"] == "legacy-g:0:7"
    assert [p["participant_id"] for p in combat_meta["encounter"]["participants"]] == \
        [e["id"] for e in enemies]
    # round-trip v8 → v8 (idempotente)
    raw2 = json.loads(json.dumps(persistence._state_to_save_data(state, "legacy-g"),
                                 default=str))
    assert raw2["schema_version"] == 8
    state2 = persistence._raw_to_state(raw2)
    assert state2["combat"]["encounter"] == combat_meta["encounter"]


def test_migracao_v8_sem_combate():
    state = persistence._raw_to_state(_v8_raw({"active": False, "round": 4}, []))
    assert state["combat"]["phase"] == "ended" and state["combat"]["outcome"] is None
    assert "encounter" not in state["combat"]
    assert persistence._raw_to_state(_v8_raw({}, []))["combat"] == {}
    corrupt = persistence._raw_to_state(_v8_raw(
        {"active": True, "encounter": {"bogus": 1}}, [_enemy(_BANDIT)]))
    assert corrupt["combat"]["encounter"]["source"] == "legacy_migrated"


def test_prose_guard_especie_divergente(monkeypatch):
    random.seed(7)
    _install_llm(monkeypatch, scan=_scan(("Bandido", 1)),
                 narration="O corvo mergulha sobre você, bicando seu ombro.")
    monkeypatch.setattr(combat, "generate_new_enemy", _bestiary_factory)
    out = combat.combat_node(_start_state())
    text = out["messages"][0].content
    assert "corvo mergulha" not in text                # neutralizada (texto determinístico)
