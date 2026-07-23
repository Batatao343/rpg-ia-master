"""
Fase 4.1 — Progressão: XP, level up e árvore de habilidades.
Suíte offline (MockLLM forçado pelo conftest). Núcleo 100% Python: progression.py.
"""
import copy

import pytest

import progression as pg
from gamedata import XP_TABLE


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------

def make_player(**over):
    p = {
        "name": "Testo", "class_name": "Cavaleiro da Vigília", "race": "Humano",
        "level": 1, "xp": 0,
        "hp": 30, "max_hp": 30, "entropy": 14, "max_entropy": 14,
        "abyss_charge": 0,
        "gold": 0, "virtudes": {"forca": 4, "corpo": 3, "carisma": 2,
                                "mente": 1, "agilidade": 1},
        "inventory": [], "known_abilities": ["ataque_basico"],
        "defense": 17, "attack_bonus": 0,
        "active_conditions": [], "ability_cooldowns": {},
        "pending_choices": [],
    }
    p.update(over)
    return p


# Árvore sintética p/ testes de elegibilidade (independente da 4.1b)
FAKE_ABILITIES = {
    "ataque_basico": {"name": "Ataque Básico", "classes": ["all"],
                      "branch": None, "tier": 1, "level_req": 1, "requires": []},
    "improvisado": {"name": "Improvisado", "classes": ["all"],
                    "branch": None, "tier": 1, "level_req": 1, "requires": []},
    "tronco_1": {"name": "Tronco 1", "classes": ["Cavaleiro da Vigília"],
                 "branch": None, "tier": 1, "level_req": 1, "requires": []},
    "tronco_alto": {"name": "Tronco Alto", "classes": ["Cavaleiro da Vigília"],
                    "branch": None, "tier": 1, "level_req": 4, "requires": []},
    "ramo_a_1": {"name": "Ramo A 1", "classes": ["Cavaleiro da Vigília"],
                 "branch": "muralha", "tier": 2, "level_req": 2, "requires": []},
    "ramo_a_2": {"name": "Ramo A 2", "classes": ["Cavaleiro da Vigília"],
                 "branch": "muralha", "tier": 3, "level_req": 3,
                 "requires": ["ramo_a_1"]},
    "ramo_b_1": {"name": "Ramo B 1", "classes": ["Cavaleiro da Vigília"],
                 "branch": "lanca", "tier": 2, "level_req": 2, "requires": []},
    "outra_classe": {"name": "Alheia", "classes": ["Arcanista Cinzento"],
                     "branch": None, "tier": 1, "level_req": 1, "requires": []},
}

FAKE_CLASSES = {
    "Cavaleiro da Vigília": {
        # spec conflito-01: jogador ganha hp + Entropia por nível (mana/stamina saíram)
        "level_gains": {"hp": 7, "entropy": 2},
    },
}


# ---------------------------------------------------------------------------
# Etapa 1 — XP e level up
# ---------------------------------------------------------------------------

def test_xp_for_kills_por_tier():
    dead = [
        {"type": "Minion"}, {"type": "Elite"}, {"type": "BOSS"},
        {"type": "boss"}, {},  # sem type -> minion
    ]
    assert pg.xp_for_kills(dead) == 50 + 200 + 1000 + 1000 + 50


def test_xp_to_next():
    # spec conflito-01: nível máximo 10 (era 20)
    assert pg.xp_to_next(1) == XP_TABLE[2] == 300
    assert pg.xp_to_next(9) == XP_TABLE[10]
    assert pg.xp_to_next(10) is None


def test_grant_xp_sem_level():
    p = make_player()
    out, events = pg.grant_xp(p, 100, classes_db=FAKE_CLASSES)
    assert out["xp"] == 100
    assert out["level"] == 1
    assert out["pending_choices"] == []
    assert events == []


def test_grant_xp_level_up():
    p = make_player(hp=20)  # ferido: cura só o delta
    out, events = pg.grant_xp(p, 300, classes_db=FAKE_CLASSES)
    assert out["level"] == 2
    assert out["max_hp"] == 37          # 30 + 7
    assert out["hp"] == 27              # 20 + 7 (delta, não full heal)
    assert out["max_entropy"] == 16     # 14 + 2 (Entropia sobe pela curva)
    kinds = [(c["level"], c["kind"]) for c in out["pending_choices"]]
    assert (2, "ability") in kinds
    assert (2, "virtude") in kinds      # nível par -> escolha de Virtude
    assert len(events) == 1
    assert events[0]["type"] == "level_up"
    assert events[0]["payload"]["new_level"] == 2


def test_grant_xp_nivel_impar_sem_attr():
    p = make_player(level=2, xp=300)
    out, _ = pg.grant_xp(p, 600, classes_db=FAKE_CLASSES)  # 900 = nível 3
    assert out["level"] == 3
    kinds = [(c["level"], c["kind"]) for c in out["pending_choices"]]
    assert (3, "ability") in kinds
    assert (3, "virtude") not in kinds


def test_grant_xp_multi_level():
    p = make_player()
    out, events = pg.grant_xp(p, 1000, classes_db=FAKE_CLASSES)  # cruza 300 e 900
    assert out["level"] == 3
    assert out["max_hp"] == 30 + 7 + 7
    assert [e["payload"]["new_level"] for e in events] == [2, 3]
    # 2 escolhas de habilidade + 1 de atributo (só o nível 2 é par)
    kinds = [c["kind"] for c in out["pending_choices"]]
    assert kinds.count("ability") == 2
    assert kinds.count("virtude") == 1


def test_grant_xp_nivel_20_cap():
    p = make_player(level=20, xp=XP_TABLE[20])
    out, events = pg.grant_xp(p, 99999, classes_db=FAKE_CLASSES)
    assert out["level"] == 20
    assert out["xp"] == XP_TABLE[20] + 99999
    assert events == []


def test_grant_xp_classe_sem_gains_usa_default():
    p = make_player(class_name="Classe Fantasma")
    out, _ = pg.grant_xp(p, 300, classes_db=FAKE_CLASSES)
    assert out["level"] == 2
    assert out["max_hp"] > 30  # default aplicado, não crash


def test_grant_xp_nao_muta_original():
    p = make_player()
    snapshot = copy.deepcopy(p)
    pg.grant_xp(p, 300, classes_db=FAKE_CLASSES)
    assert p == snapshot


# ---------------------------------------------------------------------------
# Etapa 3 — Árvore: elegibilidade, ramo (subclasse), escolha
# ---------------------------------------------------------------------------

def test_player_branch_derivada():
    p = make_player()
    assert pg.player_branch(p, abilities_db=FAKE_ABILITIES) is None
    p2 = make_player(known_abilities=["ataque_basico", "ramo_a_1"])
    assert pg.player_branch(p2, abilities_db=FAKE_ABILITIES) == "muralha"


def test_eligible_filtra_classe_nivel_prereq():
    p = make_player(level=1)
    elig = pg.eligible_abilities(p, abilities_db=FAKE_ABILITIES)
    assert "tronco_1" in elig
    assert "improvisado" in elig            # universal, não conhecida
    assert "ataque_basico" not in elig      # já conhecida
    assert "outra_classe" not in elig       # classe errada
    assert "tronco_alto" not in elig        # level_req 4
    assert "ramo_a_2" not in elig           # requires não satisfeito
    assert "ramo_a_1" not in elig           # level_req 2


def test_lock_de_ramo():
    p = make_player(level=3, known_abilities=["ataque_basico", "ramo_a_1"])
    elig = pg.eligible_abilities(p, abilities_db=FAKE_ABILITIES)
    assert "ramo_a_2" in elig               # aprofunda o próprio ramo
    assert "ramo_b_1" not in elig           # ramo rival trancado
    assert "tronco_1" in elig               # tronco segue livre


def test_apply_choice_ability():
    p = make_player(level=2, pending_choices=[
        {"id": "lvl2-ability", "level": 2, "kind": "ability"}])
    out, err = pg.apply_choice(p, "lvl2-ability", ability_id="ramo_a_1",
                               abilities_db=FAKE_ABILITIES)
    assert err is None
    assert "ramo_a_1" in out["known_abilities"]
    assert out["pending_choices"] == []


def test_apply_choice_attr():
    # spec conflito-01: escolha de nível par vira +1 numa Virtude (teto 5)
    p = make_player(pending_choices=[
        {"id": "lvl2-virtude", "level": 2, "kind": "virtude"}])
    forca0 = p["virtudes"]["forca"]  # 4
    out, err = pg.apply_choice(p, "lvl2-virtude", virtude="mente",
                               abilities_db=FAKE_ABILITIES)
    assert err is None
    assert out["virtudes"]["mente"] == 2   # 1 + 1
    assert out["virtudes"]["forca"] == forca0
    assert out["pending_choices"] == []


def test_apply_choice_invalida():
    p = make_player(level=2, known_abilities=["ataque_basico", "ramo_a_1"],
                    pending_choices=[
                        {"id": "lvl2-ability", "level": 2, "kind": "ability"}])
    snapshot = copy.deepcopy(p)

    # habilidade de ramo rival
    out, err = pg.apply_choice(p, "lvl2-ability", ability_id="ramo_b_1",
                               abilities_db=FAKE_ABILITIES)
    assert err is not None
    assert p == snapshot  # intocado

    # choice_id inexistente
    out, err = pg.apply_choice(p, "nao-existe", ability_id="tronco_1",
                               abilities_db=FAKE_ABILITIES)
    assert err is not None

    # atributo inválido
    p2 = make_player(pending_choices=[
        {"id": "lvl2-attr", "level": 2, "kind": "attribute"}])
    out, err = pg.apply_choice(p2, "lvl2-attr", attr="sorte",
                               abilities_db=FAKE_ABILITIES)
    assert err is not None
    assert p2["pending_choices"]  # não consumiu


def test_level_up_event_shape():
    p = make_player()
    _, events = pg.grant_xp(p, 300, classes_db=FAKE_CLASSES)
    ev = events[0]
    assert ev["actor_id"] == "player" and ev["target_id"] == "player"
    assert ev["source"] == "progression"
    assert "detail" in ev


# ---------------------------------------------------------------------------
# Etapa 2a — Schema da árvore nos DADOS REAIS (conteúdo: spec 4.1b)
# ---------------------------------------------------------------------------

from gamedata import ABILITIES, CLASSES  # noqa: E402

VALID_EFFECT_KINDS = {"buff", "debuff", "dot", "control", "heal", "reduce_ally_abyss"}
VALID_EFFECT_STATS = {"damage", "ac", "attack", "save", None}


def test_schema_arvore():
    class_names = set(CLASSES.keys()) | {"all"}
    for aid, a in ABILITIES.items():
        classes = a.get("classes")
        assert isinstance(classes, list) and classes, f"{aid}: classes ausente"
        for c in classes:
            assert c in class_names, f"{aid}: classe desconhecida {c!r}"
        assert isinstance(a.get("tier"), int) and 1 <= a["tier"] <= 3, f"{aid}: tier"
        assert isinstance(a.get("level_req"), int) and a["level_req"] >= 1, f"{aid}: level_req"
        reqs = a.get("requires")
        assert isinstance(reqs, list), f"{aid}: requires"
        for r in reqs:
            assert r in ABILITIES, f"{aid}: requires id inexistente {r!r}"
        br = a.get("branch")
        if br is not None:
            # branch declarado precisa existir em alguma classe da habilidade
            owners = [c for c in classes if c != "all"]
            assert any(br in ((CLASSES.get(c) or {}).get("branches") or {})
                       for c in owners), f"{aid}: branch {br!r} sem dono"


def test_sem_ciclo_em_requires():
    def deps(aid, seen):
        assert aid not in seen, f"ciclo de requires envolvendo {aid}"
        seen = seen | {aid}
        for r in ABILITIES.get(aid, {}).get("requires") or []:
            deps(r, seen)
    for aid in ABILITIES:
        deps(aid, frozenset())


def test_effects_tipado():
    for aid, a in ABILITIES.items():
        for eff in a.get("effects") or []:
            assert eff.get("kind") in VALID_EFFECT_KINDS, f"{aid}: kind {eff.get('kind')!r}"
            assert eff.get("stat") in VALID_EFFECT_STATS, f"{aid}: stat {eff.get('stat')!r}"
            assert isinstance(eff.get("duration", 1), int), f"{aid}: duration"


def test_level_gains_presentes():
    for cname, c in CLASSES.items():
        gains = c.get("level_gains")
        assert isinstance(gains, dict), f"{cname}: level_gains ausente"
        for k in ("hp", "mana", "stamina"):
            assert isinstance(gains.get(k), int), f"{cname}: level_gains.{k}"
        assert gains["hp"] >= 1, f"{cname}: hp por nível deve ser >= 1"


def test_starting_abilities_validas():
    for cname, c in CLASSES.items():
        start = c.get("starting_abilities")
        assert isinstance(start, list) and start, f"{cname}: starting_abilities"
        for aid in start:
            assert aid in ABILITIES, f"{cname}: starting {aid!r} não existe"
            a = ABILITIES[aid]
            assert a.get("level_req", 1) == 1, f"{cname}: starting {aid} exige nível > 1"
            assert a.get("branch") is None, f"{cname}: starting {aid} não pode ter ramo"
            classes = a.get("classes") or []
            assert "all" in classes or cname in classes, \
                f"{cname}: starting {aid} não pertence à classe"


# ---------------------------------------------------------------------------
# Etapa 4 — Ids canônicos: creator, catálogo/gate do combate, backfill de save
# ---------------------------------------------------------------------------

def test_creator_ids_canonicos():
    from character_creator import create_player_character
    sheet = create_player_character({
        "name": "Teste", "class_name": "Devoto do Abismo", "race": "Humano",
        "region": "Nova Arcádia", "backstory": "x", "level": "1"})
    known = sheet["known_abilities"]
    assert known and all(k in ABILITIES for k in known), known
    assert "ataque_basico" in known
    assert not any(str(k).startswith("[Passiva]") for k in known)
    for aid in CLASSES["Devoto do Abismo"]["starting_abilities"]:
        assert aid in known
    assert sheet["pending_choices"] == []


def test_catalogo_por_id_exato():
    from agents.combat import _ability_catalog_for
    p = make_player(known_abilities=["ataque_basico", "provocacao_do_abismo"])
    cat = _ability_catalog_for(p)
    assert "provocacao_do_abismo" in cat
    # habilidade de outra classe NÃO entra (só conhecidas + universais)
    assert "corte_de_troca" not in cat
    # texto livre antigo não casa mais nada além das universais
    p2 = make_player(known_abilities=["Golpe Fantasma da Lua"])
    cat2 = _ability_catalog_for(p2)
    assert "ataque_basico" in cat2
    assert "Golpe Fantasma" not in cat2


def test_gate_uso_deterministico(monkeypatch):
    """LLM aprova habilidade que a ficha não tem -> gate Python nega."""
    from agents import combat as cbt

    class _FakeStructured:
        def invoke(self, msgs):
            # corte_exato é id REAL (Sangromante) que o Devoto não conhece.
            return cbt.CombatAction(ability_id="corte_exato", target="Orc",
                                    is_allowed=True, reason="")

    class _FakeLLM:
        def with_structured_output(self, model):
            return _FakeStructured()

    monkeypatch.setattr(cbt, "get_llm", lambda **kw: _FakeLLM())
    p = make_player(class_name="Devoto do Abismo", known_abilities=["ataque_basico"])
    out = cbt._parse_combat_action(p, [{"name": "Orc", "status": "ativo"}], "uso o corte")
    assert out["is_allowed"] is False
    assert "não conhece" in out["reason"]


# ---------------------------------------------------------------------------
# Etapa 5 — Hooks de XP no grafo (combate/beat/quest) + pipeline 2.6
# ---------------------------------------------------------------------------

def _pipeline_state(**over):
    base = {
        "world": {"turn_count": 5, "current_location": "nova_arcadia"},
        "world_projection": {}, "event_log": [], "pending_world_events": [],
        "chronicle": [], "quests": [], "player": make_player(),
        "campaign_plan": {"beats": [{"description": "b0", "status": "active"}]},
    }
    base.update(over)
    return base


def test_quest_completed_da_xp():
    from services.event_processor import process_pending_events
    quests = [{"id": "q1", "title": "Recuperar o medalhão", "status": "active",
               "created_turn": 1, "resolved_turn": 0}]
    state = _pipeline_state(quests=quests, pending_world_events=[
        {"type": "quest_completed", "target_id": "q1", "payload": {"quest_id": "q1"}}])
    out = process_pending_events(state)
    assert out["player"]["xp"] == pg.XP_PER_QUEST


def test_level_up_pipeline_vira_milestone():
    from services.event_processor import process_pending_events
    prop = {"type": "level_up", "actor_id": "player", "target_id": "player",
            "detail": "nível 2", "payload": {"new_level": 2}, "source": "progression"}
    out = process_pending_events(_pipeline_state(pending_world_events=[prop]))
    assert [e for e in out["event_log"] if e["type"] == "level_up"]
    texts = [e["text"] for e in out["chronicle"][-1]["entries"]]
    assert any("nível 2" in t for t in texts)


def test_llm_nao_propoe_level_up():
    """Proposta SEM source='progression' (como toda proposta de LLM) é rejeitada."""
    from services.world_validators import validate_proposal
    prop = {"type": "level_up", "actor_id": "player", "target_id": "player",
            "payload": {"new_level": 2}}
    res = validate_proposal(prop, _pipeline_state())
    assert not res.ok
    assert "motor" in res.reason


def test_multi_level_mesmo_turno_nao_e_duplicata():
    from services.event_processor import process_pending_events
    props = [
        {"type": "level_up", "actor_id": "player", "target_id": "player",
         "payload": {"new_level": n}, "source": "progression"} for n in (2, 3)]
    out = process_pending_events(_pipeline_state(pending_world_events=props))
    levels = [e["payload"]["new_level"] for e in out["event_log"]
              if e["type"] == "level_up"]
    assert levels == [2, 3]


def test_beat_da_xp(monkeypatch):
    import agents.storyteller as st

    class _FakeStoryLLM:
        def with_structured_output(self, model, *a, **k):
            self._m = model
            return self

        def invoke(self, _msgs):
            return self._m(narrative="Objetivo cumprido.", introduced_npcs=[],
                           beat_completed=True)

    monkeypatch.setattr(st, "get_llm", lambda *a, **k: _FakeStoryLLM())
    from langchain_core.messages import HumanMessage
    state = _pipeline_state(
        messages=[HumanMessage(content="executo o objetivo")],
        campaign_plan={"location": "x", "climax": "y", "current_step": 0,
                       "last_planned_turn": 0,
                       "beats": [{"description": "b0", "status": "pending"},
                                 {"description": "b1", "status": "pending"}]},
        factions=[], npcs={})
    out = st.storyteller_node(state)
    assert out["player"]["xp"] == pg.XP_PER_BEAT
    # nenhum level (150 < 300) -> fila sem level_up
    assert not [e for e in out.get("pending_world_events", [])
                if e.get("type") == "level_up"]


def test_combat_kill_da_xp(monkeypatch):
    from agents import combat as cbt

    monkeypatch.setattr(cbt, "_parse_combat_action",
                        lambda p, e, i: {"ability_id": "ataque_basico",
                                         "target": e[0]["name"], "is_allowed": True,
                                         "reason": ""})
    monkeypatch.setattr(cbt, "_narrate", lambda *a, **k: "Fim.")
    monkeypatch.setattr(cbt.cm, "roll_initiative",
                        lambda p, e, allies=None: [{"id": "player", "name": p.get("name"),
                                                    "side": "hero", "init": 20}] +
                                                  [{"id": x.get("id"), "name": x.get("name"),
                                                    "side": "enemy", "init": 1} for x in e])

    player = make_player(xp=250, attributes={"str": 18, "dex": 14, "con": 16,
                                             "int": 8, "wis": 12, "cha": 12})
    enemy = {"id": "enemy_rato_1", "name": "Rato", "type": "Minion",
             "hp": 1, "max_hp": 1, "defense": 1, "status": "ativo",
             "attributes": {"dex": 10}, "active_conditions": [],
             "attacks": [{"name": "Mordida", "bonus": 0, "damage": "1d1"}],
             "stamina": 0, "mana": 0, "attack_mod": 0, "abilities": []}
    from langchain_core.messages import HumanMessage
    state = _pipeline_state(
        player=player, enemies=[enemy], combat={"round": 1, "active": True},
        combat_target="Rato", messages=[HumanMessage(content="ataco o rato")],
        bestiary_knowledge={})
    out = cbt.combat_node(state)
    # minion morto: +50 XP (250+50=300 -> nível 2) e level_up na fila do motor
    assert out["player"]["xp"] == 300
    assert out["player"]["level"] == 2
    lvl = [e for e in out.get("pending_world_events", []) if e["type"] == "level_up"]
    assert lvl and lvl[0]["source"] == "progression"


# ---------------------------------------------------------------------------
# Etapa 6 — API: /game/levelup + state expõe progressão
# ---------------------------------------------------------------------------

def test_levelup_endpoint_aplica_e_invalida(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient
    import api as api_mod

    player = make_player(class_name="Devoto do Abismo", level=3, pending_choices=[
        {"id": "lvl3-ability", "level": 3, "kind": "ability"},
        {"id": "lvl4-virtude", "level": 4, "kind": "virtude"}])
    fake_state = _pipeline_state(player=player,
                                 messages=[], narrative_summary="")

    saved = {}
    monkeypatch.setattr(api_mod, "load_game_state", lambda f=None: dict(fake_state))
    monkeypatch.setattr(api_mod, "save_game_state", lambda s: saved.update(s))
    client = TestClient(api_mod.app)

    # habilidade elegível (ramo do Devoto, tier 2, level_req 3)
    r = client.post("/game/levelup", json={"choice_id": "lvl3-ability",
                                           "ability_id": "marca_consagrada"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert any(a["id"] == "marca_consagrada" for a in body["player_stats"]["abilities"])
    assert saved["player"]["known_abilities"][-1] == "marca_consagrada"

    # inelegível (tier 3, level_req 5 > nível) -> 400, save intocado
    saved.clear()
    r2 = client.post("/game/levelup", json={"choice_id": "lvl3-ability",
                                            "ability_id": "fervor_ritual"})
    assert r2.status_code == 400
    assert not saved

    # Virtude (nível par) — aceita nome PT/acento via normalize_virtude
    forca0 = player["virtudes"]["forca"]
    r3 = client.post("/game/levelup", json={"choice_id": "lvl4-virtude", "virtude": "força"})
    assert r3.status_code == 200, r3.text
    assert saved["player"]["virtudes"]["forca"] == forca0 + 1


def test_levelup_block_no_state():
    import api as api_mod
    p = make_player(class_name="Devoto do Abismo", level=3, pending_choices=[
        {"id": "lvl3-ability", "level": 3, "kind": "ability"}])
    block = api_mod._levelup_block(p)
    assert block["pending"]
    ids = [e["id"] for e in block["eligible"]]
    assert "marca_consagrada" in ids
    assert block["current_branch"] is None
    assert "consagrado" in block["branches"]
    # sem pendência -> bloco vazio (payload enxuto)
    assert api_mod._levelup_block(make_player(class_name="Devoto do Abismo")) == {}


def test_backfill_save_antigo():
    p = make_player(known_abilities=[
        "[Passiva] Muralha Humana: +2 Defesa",
        "Corte Exato",               # nome livre -> id (corte_exato)
        "esquiva_calculada",         # já canônico
        "Golpe do Dragão Celestial", # flavor não-mapeável -> descarta
    ])
    p.pop("pending_choices")
    out = pg.canonicalize_known_abilities(p)
    assert out["known_abilities"] == ["ataque_basico", "corte_exato", "esquiva_calculada"]
    assert out["pending_choices"] == []
    assert out["level"] == 1 and out["xp"] == 0
