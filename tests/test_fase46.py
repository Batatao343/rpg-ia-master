"""
Fase 4.6 — Dificuldade, IA de combate e morte.
Spec: specs/fase-4.6-dificuldade-ia-morte.md. 100% offline.
"""
import pytest

import combat_mechanics as cm
import encounter_budget as eb
from gamedata import load_json_data


def minion(i=1):
    return {"id": f"enemy_rato_{i}", "name": f"Rato {i}", "type": "Minion",
            "hp": 8, "max_hp": 8, "defense": 10, "status": "ativo",
            "attributes": {"dex": 10}, "active_conditions": [],
            "attacks": [{"name": "Mordida", "bonus": 2, "damage": "1d4"}],
            "stamina": 5, "mana": 0, "attack_mod": 0}


def elite(i=1, **over):
    e = {"id": f"enemy_capitao_{i}", "name": f"Capitão {i}", "type": "Elite",
         "hp": 30, "max_hp": 30, "defense": 14, "status": "ativo",
         "attributes": {"str": 14, "dex": 12}, "active_conditions": [],
         "attacks": [{"name": "Espada", "type": "melee", "bonus": 5, "damage": "1d8+2"}],
         "stamina": 12, "mana": 10, "attack_mod": 3,
         "behavior": {"profile": "tatico"}}
    e.update(over)
    return e


def player(**over):
    p = {"name": "H", "class_name": "", "level": 3, "hp": 40, "max_hp": 40,
         "mana": 10, "max_mana": 10, "stamina": 20, "max_stamina": 20,
         "attributes": {"str": 14, "dex": 12, "con": 14, "int": 10, "wis": 10, "cha": 10},
         "inventory": [], "equipment": {"weapon": None, "armor": None, "accessory": None},
         "known_abilities": ["ataque_basico"], "defense": 13, "attack_bonus": 0,
         "active_conditions": [], "ability_cooldowns": {}, "pending_choices": []}
    p.update(over)
    return p


# ---------------------------------------------------------------------------
# Etapa 1 — orçamento
# ---------------------------------------------------------------------------

def test_budget_formula():
    assert eb.encounter_budget(1, 1, 0) == 3      # 2 + 1
    assert eb.encounter_budget(5, 4, 3) == 21     # 10 + 5 + 6
    assert eb.encounter_budget(1, 99, 0) == 11    # danger clampa em 4


def test_clamp_corta_excedente_e_mantem_1():
    horda = [minion(i) for i in range(1, 11)]  # 20 pontos
    kept, logs = eb.clamp_encounter(horda, eb.encounter_budget(1, 1, 0))  # 3
    assert len(kept) == 1  # 1 minion (2pts) cabe; segundo estouraria
    assert logs  # log de corte alimenta o narrador


def test_clamp_prioriza_variedade():
    mix = [minion(1), minion(2), minion(3), elite(1)]
    kept, _ = eb.clamp_encounter(mix, 7)  # elite(5) + 1 minion(2) = 7
    ids = [e["id"] for e in kept]
    assert "enemy_capitao_1" in ids
    assert len(kept) == 2


def test_boss_nao_e_cortado():
    boss = dict(elite(1), type="BOSS", id="enemy_boss_1")
    kept, _ = eb.clamp_encounter([boss] + [minion(i) for i in range(2, 6)], 3)
    assert any(e["id"] == "enemy_boss_1" for e in kept)


def test_fill_completa_piso():
    loc = {"id": "skallgard", "region": "Skallgard", "danger": 4, "tags": []}
    fake_entry = {"id": "enemy_reforco", "name": "Reforço", "type": "Minion",
                  "hp": 10, "max_hp": 10, "ac": 11, "attributes": {"dex": 10},
                  "attacks": [{"name": "Golpe", "bonus": 2, "damage": "1d6"}]}
    import world_utils as wu
    orig = wu.pick_encounter_enemy
    wu.pick_encounter_enemy = lambda *a, **k: dict(fake_entry)
    try:
        def make(entry, i):
            inst = dict(entry)
            inst["id"] = f"{entry['id']}_{i}"
            inst["status"] = "ativo"
            return inst
        kept, logs = eb.fill_encounter([minion(1)], 12, loc, 4, make_instance=make)
    finally:
        wu.pick_encounter_enemy = orig
    assert len(kept) > 1 and logs


# ---------------------------------------------------------------------------
# Etapa 2 — habilidades de inimigo
# ---------------------------------------------------------------------------

def _fear_ability():
    return {"id": "rugido", "name": "Rugido", "cost": 5, "resource_type": "Estamina",
            "damage_formula": "0", "damage_type": "Controle", "save_stat": None,
            "cooldown": 3,
            "effects": [{"kind": "control", "stat": None, "delta": 0,
                         "duration": 2, "control": "fear"}]}


def test_enemy_ability_custo_cooldown(monkeypatch):
    monkeypatch.setattr(cm.random, "randint", lambda a, b: 10)
    e = elite(abilities=[_fear_ability()], behavior={"profile": "tatico"})
    p = player()
    logs = cm.resolve_enemy_turn(e, p)
    assert any("Rugido" in l for l in logs)
    assert e["stamina"] == 7  # pagou 5
    assert e["ability_cooldowns"]["rugido"] == 3
    # fear chegou ao player (condição de controle 4.2)
    assert cm.has_control(p, "fear")
    # próximo turno: em cooldown -> não usa de novo
    assert cm.usable_enemy_abilities(e) == []


def test_minion_sem_ability_segue_attacks(monkeypatch):
    monkeypatch.setattr(cm.random, "randint", lambda a, b: 10)
    e = minion()
    e["abilities"] = ["decorativa antiga"]  # string legada é ignorada
    p = player()
    logs = cm.resolve_enemy_turn(e, p)
    assert cm.usable_enemy_abilities(e) == []
    assert logs  # atacou normal


def test_feroz_usa_maior_dano(monkeypatch):
    monkeypatch.setattr(cm.random, "randint", lambda a, b: 15)
    big = {"id": "esmagar", "name": "Esmagar", "cost": 4, "resource_type": "Estamina",
           "damage_formula": "3d8", "damage_type": "Físico", "save_stat": None,
           "cooldown": 2, "effects": []}
    e = elite(abilities=[big], behavior={"profile": "feroz"})
    p = player(hp=100, max_hp=100)
    logs = cm.resolve_enemy_turn(e, p)
    assert any("Esmagar" in l for l in logs)
    assert p["hp"] < 100


# ---------------------------------------------------------------------------
# Etapa 3 — curadoria
# ---------------------------------------------------------------------------

def test_abilities_bestiario_schema_valido():
    best = load_json_data("bestiary.json")
    mech_count = 0
    for eid, e in best.items():
        for ab in e.get("abilities") or []:
            if not isinstance(ab, dict):
                continue
            mech_count += 1
            assert ab.get("id") and ab.get("name"), eid
            for eff in ab.get("effects") or []:
                assert eff.get("kind") in ("buff", "debuff", "dot", "control", "heal"), eid
    assert mech_count >= 15  # leva R4


def test_bosses_tem_fases():
    best = load_json_data("bestiary.json")
    bosses = [e for e in best.values() if str(e.get("type", "")).lower() == "boss"]
    assert bosses
    for b in bosses:
        phases = (b.get("behavior") or {}).get("phases")
        assert phases and phases[0]["below"] <= 1.0, b.get("id")


# ---------------------------------------------------------------------------
# Etapa 4 — boss phases
# ---------------------------------------------------------------------------

def test_fase_troca_perfil_e_once_log():
    b = elite(type="BOSS", behavior={
        "profile": "implacavel",
        "phases": [{"below": 0.5, "profile": "feroz",
                    "add_abilities": [_fear_ability()],
                    "once_log": "Ele desperta."}]})
    b["hp"] = 10  # 33%
    log1 = cm.apply_boss_phase(b)
    assert log1 == "Ele desperta."
    assert b["behavior"]["profile"] == "feroz"
    assert any(isinstance(a, dict) and a["id"] == "rugido" for a in b["abilities"])
    # once: segunda chamada não repete
    assert cm.apply_boss_phase(b) is None


def test_boss_sem_phases_ok():
    assert cm.apply_boss_phase(elite()) is None


# ---------------------------------------------------------------------------
# Etapa 5 — morte do player
# ---------------------------------------------------------------------------

def test_morte_gera_evento_e_memorial(monkeypatch):
    from agents import combat as cbt
    from langchain_core.messages import HumanMessage

    monkeypatch.setattr(cbt, "_parse_combat_action",
                        lambda p, e, i: {"ability_id": "ataque_basico", "target": "",
                                         "is_allowed": True, "reason": ""})
    monkeypatch.setattr(cbt.cm, "roll_initiative",
                        lambda p, e, allies=None: [
                            {"id": x.get("id"), "name": x.get("name"),
                             "side": "enemy", "init": 20} for x in e] +
                        [{"id": "player", "name": "H", "side": "hero", "init": 1}])

    killer = elite(attacks=[{"name": "Golpe Final", "type": "melee",
                             "bonus": 50, "damage": "10d10+50"}],
                   behavior={"profile": "implacavel"})
    p = player(hp=5)
    state = {"messages": [HumanMessage(content="luto")], "player": p,
             "enemies": [killer], "combat": {"round": 1, "active": True},
             "combat_target": "Capitão", "world": {"turn_count": 3,
                                                   "current_location": "Skallgard",
                                                   "world_clock": {"day": 2}},
             "bestiary_knowledge": {}, "pending_world_events": [], "party": []}
    out = cbt.combat_node(state)
    assert out.get("game_over") is True
    deaths = [e for e in out["pending_world_events"] if e["type"] == "player_died"]
    assert deaths and deaths[0]["source"] == "combat"
    # narrativa de fecho presente (template determinístico no mock/fallback)
    assert "crônica" in out["messages"][0].content.lower() or "☠" in out["messages"][0].content


def test_template_morte_digno():
    from agents.combat import _death_template
    txt = _death_template(player(name="Kael", class_name="Sangromante"),
                          [elite(status="ativo")],
                          {"current_location": "Brekmar", "world_clock": {"day": 7}})
    assert "Kael" in txt and "Brekmar" in txt and "7" in txt


def test_llm_nao_propoe_player_died():
    from services.world_validators import validate_proposal
    prop = {"type": "player_died", "actor_id": "player", "target_id": "player",
            "payload": {}}
    res = validate_proposal(prop, {"world": {"turn_count": 1}, "event_log": [],
                                   "world_projection": {}})
    assert not res.ok and "motor" in res.reason


def test_player_died_vira_milestone():
    from services.event_processor import process_pending_events
    state = {"world": {"turn_count": 9}, "world_projection": {}, "event_log": [],
             "chronicle": [], "quests": [], "player": player(),
             "pending_world_events": [{
                 "type": "player_died", "actor_id": "player", "target_id": "player",
                 "detail": "Kael caiu em combate diante do Capitão",
                 "payload": {}, "source": "combat"}]}
    out = process_pending_events(state)
    texts = [e["text"] for e in out["chronicle"][-1]["entries"]]
    assert any("termina a saga" in t for t in texts)


def test_save_morto_marca_game_over(tmp_path, monkeypatch):
    import persistence as pers
    monkeypatch.setattr(pers, "SAVES_DIR", str(tmp_path))
    state = {"game_id": "morto1", "player": player(hp=0), "world": {},
             "messages": [], "game_over": True}
    pers.save_game_state(state)
    loaded = pers.load_game_state(str(tmp_path / "morto1.json"))
    assert loaded["game_over"] is True


def test_action_em_save_morto_409(monkeypatch):
    from fastapi.testclient import TestClient
    import api as api_mod
    dead_state = {"game_id": "g", "player": player(hp=0), "world": {},
                  "messages": [], "game_over": True}
    monkeypatch.setattr(api_mod, "load_game_state", lambda f=None: dict(dead_state))
    client = TestClient(api_mod.app)
    r = client.post("/game/action", json={"input_text": "olá"})
    assert r.status_code == 409
    assert "memorial" in r.json()["detail"]
