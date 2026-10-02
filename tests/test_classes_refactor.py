"""Suíte da spec refatoracao-sistema-classes (Cinco Posturas diante do Abismo).

Etapa 1: recurso Entropia. Offline/determinístico.
Ver specs/SPEC-048-refatoracao-sistema-classes.md.
"""
import combat_mechanics as cm
import world_utils as wu


# --- Etapa 1: recurso Entropia ----------------------------------------------

def test_cards_tem_custo_de_entropia():
    from services import cards
    assert int(cards.get_card("dev_provocacao")["custo_entropia"]) == 2


def test_pay_from_entropy():
    from services import cards
    player = {"entropy": 10, "prepared_cards": ["dev_provocacao"],
              "virtue_cards": [], "card_usage": {}}
    result = cards.use_card({"player": player}, "dev_provocacao")
    assert result["ok"] is True
    assert player["entropy"] == 8


def test_pay_from_entropy_insuficiente():
    from services import cards
    player = {"entropy": 1, "prepared_cards": ["dev_provocacao"],
              "virtue_cards": [], "card_usage": {}}
    result = cards.use_card({"player": player}, "dev_provocacao")
    assert result["ok"] is False
    assert player["entropy"] == 1


def test_rest_refills_entropy_full():
    player = {"hp": 10, "max_hp": 40, "entropy": 3, "max_entropy": 16,
              "active_conditions": []}
    world = wu.ensure_world({"current_location_id": "nova_arcadia"})
    p2, _w = wu.apply_rest(player, world)
    assert p2["entropy"] == 16          # Entropia INTEGRAL
    assert p2["hp"] < p2["max_hp"]      # HP só ~metade (não integral)


def test_rest_nao_derruba_carga_do_abismo():
    player = {"hp": 10, "max_hp": 40, "entropy": 3, "max_entropy": 16,
              "abyss_charge": 5, "active_conditions": []}
    world = wu.ensure_world({})
    p2, _w = wu.apply_rest(player, world)
    assert p2["abyss_charge"] == 5      # Carga do Abismo NÃO cai no descanso


# --- Etapa 2: dados das 5 classes -------------------------------------------

FIVE_CLASSES = {
    "Devoto do Abismo", "Sangromante", "Corruptor",
    "Arcanista Cinzento", "Médico de Campo",
}


def test_five_classes_load():
    from gamedata import CLASSES
    assert set(CLASSES.keys()) == FIVE_CLASSES


def test_each_class_three_branches():
    from gamedata import CLASSES
    for cn in FIVE_CLASSES:
        branches = CLASSES[cn].get("branches") or {}
        assert len(branches) == 3, f"{cn} deveria ter 3 subclasses, tem {len(branches)}"


def test_base_stats_have_entropy():
    from gamedata import CLASSES
    for cn in FIVE_CLASSES:
        base = CLASSES[cn].get("base_stats") or {}
        assert int(base.get("entropy", 0)) > 0, f"{cn} sem entropy no base_stats"
        # mana/stamina base viram 0 (recurso morto p/ jogador)
        assert int(base.get("mana", 0)) == 0
        assert int(base.get("stamina", 0)) == 0


def test_typed_config_blocks_present():
    from gamedata import CLASSES
    kinds = {"on_damage_taken", "on_self_harm", "on_decay_nearby",
             "on_channel", "on_ally_suffer"}
    seen_kinds = set()
    for cn in FIVE_CLASSES:
        cd = CLASSES[cn]
        assert "entropy_trigger" in cd and "kind" in cd["entropy_trigger"]
        assert "special_rule" in cd and "kind" in cd["special_rule"]
        assert "abyss" in cd and "consequence" in cd["abyss"]
        seen_kinds.add(cd["entropy_trigger"]["kind"])
    assert seen_kinds == kinds  # cada classe usa um gatilho distinto


def test_onboarding_matches_classes():
    from gamedata import CLASSES, load_json_data
    onb = load_json_data("onboarding.json") or {}
    assert set((onb.get("classes") or {}).keys()) == set(CLASSES.keys())
    themes = load_json_data("class_themes.json") or {}
    assert set(themes.keys()) == set(CLASSES.keys())


def test_class_attr_map_covers_five():
    # spec conflito-01: CLASS_ATTR_MAP (atributo D&D) virou CLASS_PRIMARY_VIRTUE.
    from character_creator import CLASS_PRIMARY_VIRTUE
    import gamedata
    assert set(CLASS_PRIMARY_VIRTUE.keys()) == FIVE_CLASSES
    assert all(v in gamedata.VIRTUDES for v in CLASS_PRIMARY_VIRTUE.values())


def test_class_cards_exist():
    from services import cards
    for cn in FIVE_CLASSES:
        assert len(cards.cards_for_class(cn)) >= 16


def test_all_player_cards_use_entropy():
    from services import cards
    assert all(int(card.get("custo_entropia", 0) or 0) >= 0
               for card in cards.all_cards().values())


def test_creator_fills_entropy():
    """create_player_character preenche entropy/max_entropy e zera mana/stamina."""
    import os
    os.environ["RPG_FORCE_MOCK"] = "1"
    from character_creator import create_player_character
    sheet = create_player_character({
        "name": "Vael", "class_name": "Sangromante", "race": "Humano",
        "region": "Nova Arcádia", "level": 1,
    })
    assert sheet["max_entropy"] > 0
    assert sheet["entropy"] == sheet["max_entropy"]
    # spec conflito-01: mana/stamina saíram do schema do jogador
    assert "mana" not in sheet and "stamina" not in sheet
    assert sheet["abyss_charge"] == 0


# --- Etapas 3/4: gatilhos, regras especiais e consequências -----------------

DEVOTO = "Devoto do Abismo"


def _p(cls, **over):
    p = {
        "name": "Ava", "class_name": cls,
        "hp": 30, "max_hp": 30, "entropy": 0, "max_entropy": 16, "abyss_charge": 0,
        "attributes": {"str": 12, "dex": 14, "con": 12, "int": 14, "wis": 14, "cha": 10},
        "known_cards": [], "prepared_cards": [], "card_usage": {},
        "virtue_cards": [], "evolved_cards": {},
        "active_conditions": [], "equipment": {"weapon": None},
    }
    p.update(over)
    return p


def _alvo(**over):
    e = {"id": "e1", "name": "Alvo", "hp": 60, "max_hp": 60, "defense": 1,
         "status": "ativo", "attributes": {"dex": 8, "con": 10},
         "active_conditions": [], "attacks": [{"name": "Golpe", "bonus": 20, "damage": "2d6"}]}
    e.update(over)
    return e


# gatilhos (§3.4)
def test_devoto_entropy_on_damage():
    p = _p(DEVOTO, entropy=0, max_entropy=16)
    cm.apply_entropy_trigger(p, {"kind": "on_damage_taken", "amount": 8})
    assert p["entropy"] == 2          # 8 // divisor(4)
    assert p["abyss_charge"] == 1     # gatilho SEMPRE soma Carga


def test_trigger_per_turn_cap():
    p = _p(DEVOTO)
    cm.apply_entropy_trigger(p, {"kind": "on_damage_taken", "amount": 8})
    cm.apply_entropy_trigger(p, {"kind": "on_damage_taken", "amount": 8})
    assert p["abyss_charge"] == 1     # per_turn_cap = 1
    cm.reset_entropy_turn(p)
    cm.apply_entropy_trigger(p, {"kind": "on_damage_taken", "amount": 8})
    assert p["abyss_charge"] == 2     # novo turno → nova ativação


def test_sangromante_entropy_on_self_harm():
    p = _p("Sangromante", entropy=0, max_entropy=16)
    cm.apply_entropy_trigger(p, {"kind": "on_self_harm", "amount": 3})
    assert p["entropy"] >= 3
    assert p["abyss_charge"] == 1
    assert p.get("_blood_entropy", 0) >= 3


def test_corruptor_entropy_on_decay_filtra_por_dominio():
    p = _p("Corruptor", entropy=0, max_entropy=18,
           known_cards=["cor_bio_gangrena"])  # domínio biologia (flesh)
    cm.apply_entropy_trigger(p, {"kind": "on_decay_nearby", "decay_kind": "gear"})
    assert p["entropy"] == 0          # metal não é o domínio dele
    cm.apply_entropy_trigger(p, {"kind": "on_decay_nearby", "decay_kind": "flesh"})
    assert p["entropy"] == 1 and p["abyss_charge"] == 1


def test_arcanista_entropy_on_channel_e_caldeira():
    p = _p("Arcanista Cinzento", entropy=10, max_entropy=20)
    cm.apply_entropy_trigger(p, {"kind": "on_channel"})
    cm.arm_boiler(p, {"cools": False})
    assert p["abyss_charge"] == 1
    assert p.get("_cool_deadline") == 3


def test_boiler_overload():
    p = _p("Arcanista Cinzento", hp=22, max_hp=22)
    p["_cool_deadline"] = 1
    logs = cm.tick_boiler(p)
    assert p["hp"] < 22               # venceu o prazo sem vazão → estoura
    assert "_cool_deadline" not in p


def test_medico_entropy_on_ally_suffer():
    p = _p("Médico de Campo", entropy=0, max_entropy=16)
    cm.apply_entropy_trigger(p, {"kind": "on_ally_suffer"})
    assert p["entropy"] == 1 and p["abyss_charge"] == 1


def test_gatilhos_passivos_nao_alcancam_severo_sem_escolha_deliberada():
    for class_name, event in (
        (DEVOTO, {"kind": "on_damage_taken", "amount": 8}),
        ("Médico de Campo", {"kind": "on_ally_suffer"}),
    ):
        p = _p(class_name, entropy=0, abyss_charge=0)
        for _ in range(12):
            cm.reset_entropy_turn(p)
            cm.apply_entropy_trigger(p, event)
        assert p["abyss_charge"] == 6
        assert cm.abyss_tier(p) == "moderado"


# abyss_tier + regras especiais (§3.5)
def test_abyss_tier():
    assert cm.abyss_tier(_p(DEVOTO, abyss_charge=0)) == "nenhum"
    assert cm.abyss_tier(_p(DEVOTO, abyss_charge=2)) == "leve"
    assert cm.abyss_tier(_p(DEVOTO, abyss_charge=5)) == "moderado"
    assert cm.abyss_tier(_p(DEVOTO, abyss_charge=9)) == "severo"


def test_taunt_scales_with_entropy():
    assert cm.taunt_aggro_multiplier(_p(DEVOTO, entropy=0)) == 1.0
    assert cm.taunt_aggro_multiplier(_p(DEVOTO, entropy=10)) == 1.5   # 10 * 0.05
    assert cm.taunt_aggro_multiplier(_p(DEVOTO, entropy=100)) == 1.6  # teto cap 0.6


def test_blood_leak():
    p = _p("Sangromante", entropy=10, max_entropy=16)
    p["_blood_entropy"] = 8
    cm.apply_blood_leak(p)
    assert p["entropy"] == 8          # vaza 25% de 8 = 2
    assert p["_blood_entropy"] == 6
    outro = _p(DEVOTO, entropy=10)
    outro["_blood_entropy"] = 8
    cm.apply_blood_leak(outro)
    assert outro["entropy"] == 10     # só Sangromante vaza


def test_reduce_ally_abyss_so_medico():
    medic = _p("Médico de Campo", entropy=10)
    ally = {"name": "Bru", "abyss_charge": 5}
    ok, _log = cm.reduce_ally_abyss(medic, ally, 2)
    assert ok and ally["abyss_charge"] == 3 and medic["entropy"] == 8
    nope, _l2 = cm.reduce_ally_abyss(_p("Sangromante", entropy=10),
                                     {"abyss_charge": 5}, 2)
    assert nope is False


# consequências (§3.6)
def test_insonia_reduces_rest_and_ally_mitigates():
    world = wu.ensure_world({})
    devoto = _p(DEVOTO, hp=10, max_hp=40, abyss_charge=4)   # moderado → -25% cura
    p_dev, _ = wu.apply_rest(devoto, world)
    corr = _p("Corruptor", hp=10, max_hp=40, abyss_charge=4)  # sem Insônia
    p_cor, _ = wu.apply_rest(corr, wu.ensure_world({}))
    assert p_dev["hp"] < p_cor["hp"]                       # Insônia curou menos
    # aliado ativo mitiga a Carga
    mit, _ = wu.apply_rest(_p(DEVOTO, hp=10, max_hp=40, abyss_charge=4),
                           wu.ensure_world({}), allies=[{"active": True, "status": "ativo", "hp": 5}])
    assert mit["abyss_charge"] == 3


def test_cicatriz_reduces_max_hp():
    p = _p("Sangromante", hp=26, max_hp=26, entropy=10,
           known_cards=["san_exp_credencial"])
    cm.apply_scar(p, {"peak": True})
    assert p["max_hp"] == 23          # peak → -3 max_hp permanente
    assert p["abyss_charge"] >= 1


def test_dependencia_raises_cost():
    sem = _p("Arcanista Cinzento", abyss_charge=5, equipment={"weapon": None})   # moderado
    assert cm.dependencia_cost(sem, 4) == 8
    com = _p("Arcanista Cinzento", abyss_charge=5, equipment={"weapon": "cajado_rachado"})
    assert cm.dependencia_cost(com, 4) == 4
    leve = _p("Arcanista Cinzento", abyss_charge=1, equipment={"weapon": None})  # leve < moderado
    assert cm.dependencia_cost(leve, 4) == 4


def test_transformacao_debuff_by_domain():
    p = _p("Corruptor", abyss_charge=4,
           known_cards=["cor_alm_duvida"])  # domínio alma → save_penalty
    cm.apply_transformacao(p)
    assert any(c.get("stat") == "save" for c in p["active_conditions"])


def test_recidiva_hidden_then_collapse():
    p = _p("Médico de Campo", abyss_charge=7)   # severo
    _logs, ev = cm.check_recidiva(p)
    assert ev and ev["type"] == "abyss_collapse"
    assert p["_recidiva_fired"]
    assert any(c.get("name") == "Colapso" for c in p["active_conditions"])
    _l2, ev2 = cm.check_recidiva(p)              # dispara UMA vez só
    assert ev2 is None
    _l3, ev3 = cm.check_recidiva(_p("Médico de Campo", abyss_charge=3))  # abaixo de severo
    assert ev3 is None


def test_rest_entropy_full_never_adds_charge():
    p = _p(DEVOTO, entropy=0, max_entropy=14, abyss_charge=2, hp=10, max_hp=40)
    p2, _ = wu.apply_rest(p, wu.ensure_world({}))
    assert p2["entropy"] == 14
    assert p2["abyss_charge"] == 2


# --- Etapa 6: migração + limpeza --------------------------------------------

def test_old_class_save_is_archived_without_conversion():
    import persistence as ps
    raw = {"schema_version": 2, "player": {
        "class_name": "Cavaleiro da Vigília", "level": 2,
        "mana": 5, "max_mana": 5, "stamina": 10, "max_stamina": 10,
        "known_abilities": ["estocada_renal"],  # id morto → descartado
    }}
    out = ps.migrate_state(dict(raw))
    assert out["archived"] is True
    assert out["player"]["class_name"] == "Cavaleiro da Vigília"


def test_old_save_loads_archived_sem_crash(tmp_path, monkeypatch):
    import json
    import persistence as ps
    monkeypatch.setattr(ps, "SAVES_DIR", str(tmp_path))
    gid = "11111111-1111-1111-1111-111111111111"
    raw = {"schema_version": 1, "game_id": gid,
           "player": {"class_name": "Batedor das Fronteiras", "level": 3,
                      "hp": 20, "max_hp": 30, "known_abilities": []},
           "world": {"current_location_id": "nova_arcadia"}, "message_history": []}
    with open(f"{tmp_path}/{gid}.json", "w", encoding="utf-8") as f:
        json.dump(raw, f)
    state = ps.load_game_state(f"{tmp_path}/{gid}.json")
    assert state is not None
    assert state["archived"] is True
    assert state["player"]["class_name"] == "Batedor das Fronteiras"


def test_no_old_class_in_active_data():
    from gamedata import CLASSES, load_json_data
    import json
    import os
    old = {"Cavaleiro da Vigília", "Batedor das Fronteiras", "Inquisidor da Cinza",
           "Pastor de Pragas", "Guardião Selvagem", "Sombra da Corte",
           "Sapador da Fuligem"}
    assert not (set(CLASSES.keys()) & old)
    themes = load_json_data("class_themes.json") or {}
    assert not (set(themes.keys()) & old)
    onb = (load_json_data("onboarding.json") or {}).get("classes") or {}
    assert not (set(onb.keys()) & old)
