"""Suíte da spec itens-vivos-e-luz — passivas/ativas de item + sistema de luz.

Offline/determinístico. Ver specs/itens-vivos-e-luz.md.
"""
import combat_mechanics as cm
import world_utils as wu


# --- fake artifacts DB (não depende da curadoria real) ----------------------
_FAKE_DB = {
    "anel_ac": {"name": "Anel de Aço", "type": "accessory",
                "combat_stats": {"ac_bonus": 0, "attack_bonus": 0, "damage_dice": "0"},
                "mechanics": {"passive_effects": [{"trigger": "always", "stat": "ac", "delta": 1}]}},
    "capa_medo": {"name": "Capa do Bravo", "type": "accessory",
                  "combat_stats": {"ac_bonus": 0, "attack_bonus": 0, "damage_dice": "0"},
                  "mechanics": {"passive_effects": [{"trigger": "resist", "name": "medo"}]}},
    "oculos_batedor": {"name": "Óculos de Batedor", "type": "accessory",
                       "combat_stats": {"ac_bonus": 0, "attack_bonus": 0, "damage_dice": "0"},
                       "mechanics": {"passive_effects": [{"trigger": "perception", "delta": 2}]}},
    "tocha": {"name": "Tocha", "type": "consumable",
              "combat_stats": {"ac_bonus": 0, "attack_bonus": 0, "damage_dice": "0"},
              "mechanics": {"passive_effects": [{"trigger": "light"}]}},
    "espada": {"name": "Espada", "type": "weapon",
               "combat_stats": {"attack_bonus": 0, "damage_dice": "1d6", "attribute": "str", "ac_bonus": 0},
               "mechanics": {"passive_effects": []}},
}


def _player(**over):
    p = {"name": "Kael", "class_name": "Guerreiro", "hp": 30, "max_hp": 30,
         "attributes": {"str": 14, "dex": 12, "con": 12, "int": 10, "wis": 14, "cha": 10},
         "known_abilities": ["ataque_basico"], "active_conditions": [],
         "equipment": {"weapon": "espada", "armor": None, "accessory": "anel_ac"},
         "inventory": []}
    p.update(over)
    return p


# --- Etapa 1: passiva de item fiada -----------------------------------------

def test_item_passives_le_slots(monkeypatch):
    monkeypatch.setattr(cm, "ARTIFACTS_DB", _FAKE_DB)
    p = _player()
    passives = cm.item_passives(p)
    assert any(pe.get("stat") == "ac" and pe.get("delta") == 1 for pe in passives)


def test_item_passive_entra_no_player_passives(monkeypatch):
    monkeypatch.setattr(cm, "ARTIFACTS_DB", _FAKE_DB)
    p = _player()
    pp = cm.player_passives(p)
    assert any(pe.get("trigger") == "always" and pe.get("stat") == "ac" for pe in pp)


def test_item_resist(monkeypatch):
    monkeypatch.setattr(cm, "ARTIFACTS_DB", _FAKE_DB)
    p = _player(equipment={"weapon": "espada", "armor": None, "accessory": "capa_medo"})
    assert cm.is_condition_resisted(p, "medo") is True
    assert cm.is_condition_resisted(p, "veneno") is False


def test_inimigo_nao_ganha_passiva_de_item(monkeypatch):
    monkeypatch.setattr(cm, "ARTIFACTS_DB", _FAKE_DB)
    enemy = {"name": "Goblin", "hp": 10, "attributes": {"str": 10},
             "equipment": {"accessory": "anel_ac"}}  # inimigo não é jogador
    # item_passives lê equipment, mas class_passives(enemy)=[] e learned=[].
    # o inimigo NÃO deve herdar AC de item via o pipeline do jogador:
    # player_passives inclui item_passives — porém o enemy resolver usa
    # class_passives, não player_passives (contrato existente). Garante que
    # class_passives do inimigo é vazio.
    assert cm.class_passives(enemy) == []


def test_item_perception_na_deteccao(monkeypatch):
    import random
    monkeypatch.setattr(cm, "ARTIFACTS_DB", _FAKE_DB)
    p = _player(equipment={"weapon": "espada", "armor": None, "accessory": "oculos_batedor"})
    p_sem = _player()  # anel de AC, sem percepção
    # mesma seed → o roll base é igual; +2 percepção sobe o total
    random.seed(1)
    com = wu.detection_check(p, danger=2)
    random.seed(1)
    sem = wu.detection_check(p_sem, danger=2)
    assert com["roll"] == sem["roll"] + 2


# --- Etapa 2: sistema de luz ------------------------------------------------

def _loc(monkeypatch, tags):
    import gamedata
    monkeypatch.setattr(gamedata, "get_location", lambda _id: {"tags": tags})


def test_noite_sem_luz_penaliza_percepcao(monkeypatch):
    monkeypatch.setattr(cm, "ARTIFACTS_DB", _FAKE_DB)
    _loc(monkeypatch, [])
    w = {"current_location_id": "ermo", "time_of_day": "Noite"}
    ll = wu.light_level(w, _player())          # sem fonte de luz
    assert ll["dark"] and ll["perception_mod"] < 0


def test_luz_anula_escuro(monkeypatch):
    monkeypatch.setattr(cm, "ARTIFACTS_DB", _FAKE_DB)
    _loc(monkeypatch, [])
    w = {"current_location_id": "ermo", "time_of_day": "Noite"}
    p = _player(inventory=[{"id": "tocha", "qty": 1}])  # carrega tocha (light)
    ll = wu.light_level(w, p)
    assert not ll["dark"] and ll["lit"] and ll["perception_mod"] == 0


def test_cidade_iluminada_a_noite(monkeypatch):
    monkeypatch.setattr(cm, "ARTIFACTS_DB", _FAKE_DB)
    _loc(monkeypatch, ["cidade"])              # abrigo/urbano
    w = {"current_location_id": "nova_arcadia", "time_of_day": "Noite"}
    ll = wu.light_level(w, _player())
    assert not ll["dark"]                       # cidade tem tochas → iluminada


def test_masmorra_dark_de_dia(monkeypatch):
    monkeypatch.setattr(cm, "ARTIFACTS_DB", _FAKE_DB)
    _loc(monkeypatch, ["dark"])                 # interior escuro
    w = {"current_location_id": "cripta", "time_of_day": "Manhã"}
    ll = wu.light_level(w, _player())
    assert ll["dark"]                           # masmorra é escura mesmo de dia


def test_dia_claro_sem_penalidade(monkeypatch):
    monkeypatch.setattr(cm, "ARTIFACTS_DB", _FAKE_DB)
    _loc(monkeypatch, [])
    w = {"current_location_id": "campo", "time_of_day": "Tarde"}
    ll = wu.light_level(w, _player())
    assert not ll["dark"] and ll["perception_mod"] == 0 and ll["combat_mod"] == 0


# --- Etapa 3: item ativo ofensivo -------------------------------------------

_ITEM_DB = {
    "bomba_atordoante": {"name": "Bomba Atordoante", "type": "consumable",
                         "combat_stats": {"ac_bonus": 0, "attack_bonus": 0, "damage_dice": "0"},
                         "mechanics": {"passive_effects": [],
                                       "effects": [{"kind": "control", "control": "stun", "duration": 1}]}},
    "po_do_sono": {"name": "Pó do Sono", "type": "consumable",
                   "combat_stats": {"ac_bonus": 0, "attack_bonus": 0, "damage_dice": "0"},
                   "mechanics": {"passive_effects": [], "save_stat": "con", "save_dc": 30,
                                 "effects": [{"kind": "control", "control": "stun", "duration": 2}]}},
    "elixir_forca": {"name": "Elixir de Força", "type": "consumable",
                     "combat_stats": {"ac_bonus": 0, "attack_bonus": 0, "damage_dice": "0"},
                     "mechanics": {"passive_effects": [],
                                   "effects": [{"kind": "buff", "stat": "attack", "delta": 2, "duration": 3}]}},
}


def _enemy(**over):
    e = {"id": "e1", "name": "Ogro", "hp": 40, "max_hp": 40, "defense": 12,
         "status": "ativo", "attributes": {"con": 4}, "active_conditions": []}
    e.update(over)
    return e


def test_bomba_atordoa_inimigo(monkeypatch):
    import inventory as inv
    monkeypatch.setattr(inv, "ARTIFACTS_DB", _ITEM_DB)
    p = _player(inventory=[{"id": "bomba_atordoante", "qty": 1}], equipment=None)
    target = _enemy()
    p2, logs = inv.use_item_in_combat(p, "bomba_atordoante", target=target)
    assert any(c.get("control") == "stun" for c in target["active_conditions"])
    assert not p2.get("inventory")            # consumiu a única unidade


def test_item_ofensivo_com_save_resiste(monkeypatch):
    import inventory as inv
    monkeypatch.setattr(inv, "ARTIFACTS_DB", _ITEM_DB)
    p = _player(inventory=[{"id": "po_do_sono", "qty": 1}], equipment=None)
    target = _enemy(attributes={"con": 20})   # save_dc 30 mas com=+5... ainda falha? força resistência:
    # DC 30 é altíssimo → sem seed, o alvo quase sempre FALHA. Para testar RESISTE,
    # usamos DC baixo:
    _ITEM_DB["po_do_sono"]["mechanics"]["save_dc"] = 1  # DC trivial → sempre passa (resiste)
    p2, logs = inv.use_item_in_combat(p, "po_do_sono", target=target)
    assert not any(c.get("control") == "stun" for c in target["active_conditions"])
    _ITEM_DB["po_do_sono"]["mechanics"]["save_dc"] = 30  # restaura


def test_item_buff_segue_no_self(monkeypatch):
    import inventory as inv
    monkeypatch.setattr(inv, "ARTIFACTS_DB", _ITEM_DB)
    p = _player(inventory=[{"id": "elixir_forca", "qty": 1}], equipment=None)
    target = _enemy()
    p2, logs = inv.use_item_in_combat(p, "elixir_forca", target=target)
    assert any(c.get("stat") == "attack" for c in p2.get("active_conditions", []))
    assert target["active_conditions"] == []  # alvo intacto (buff é self)


def test_consumivel_gasta_qty(monkeypatch):
    import inventory as inv
    monkeypatch.setattr(inv, "ARTIFACTS_DB", _ITEM_DB)
    p = _player(inventory=[{"id": "bomba_atordoante", "qty": 2}], equipment=None)
    p2, _ = inv.use_item_in_combat(p, "bomba_atordoante", target=_enemy())
    assert p2["inventory"][0]["qty"] == 1


# --- Etapa 4/5: dados reais (anti-órfão + variedade) ------------------------

def _real_db():
    from gamedata import ARTIFACTS_DB
    return ARTIFACTS_DB


def test_lanterna_e_fonte_de_luz():
    lan = _real_db().get("art_lanterna_suspiros") or {}
    passives = (lan.get("mechanics") or {}).get("passive_effects") or []
    assert any(pe.get("trigger") == "light" for pe in passives)


def test_todo_effect_kind_e_trigger_de_item_tem_handler():
    """Anti-órfão de DADO: kind/trigger declarado em item ∈ vocabulário do motor."""
    hk = cm.HANDLED_KINDS
    for iid, it in _real_db().items():
        mech = it.get("mechanics") or {}
        for eff in mech.get("effects") or []:
            if isinstance(eff, dict):
                assert eff.get("kind") in hk["effect"], f"{iid}: effect {eff.get('kind')} órfão"
        for pe in mech.get("passive_effects") or []:
            if isinstance(pe, dict):   # legado tem strings de flavor
                assert pe.get("trigger") in hk["passive_trigger"], \
                    f"{iid}: passive trigger {pe.get('trigger')} órfão"


def test_fontes_de_luz_minimas():
    db = _real_db()
    fontes = [iid for iid, it in db.items()
              if any(isinstance(pe, dict) and pe.get("trigger") == "light"
                     for pe in (it.get("mechanics") or {}).get("passive_effects") or [])
              or "luz" in (it.get("economy_tags") or [])]
    assert len(fontes) >= 3


def test_variedade_de_ativos():
    kinds = set()
    for it in _real_db().values():
        for eff in (it.get("mechanics") or {}).get("effects") or []:
            if isinstance(eff, dict):
                kinds.add(eff.get("kind"))
    assert {"control", "dot", "buff"} <= kinds   # ao menos 1 de cada


def test_catalogo_cresceu():
    assert len(_real_db()) >= 60          # 44 legados + ~22 novos


def test_api_world_block_expoe_luz():
    import api
    w = {"current_location_id": "x", "time_of_day": "Noite", "world_clock": {"day": 1, "period": "Noite"}}
    block = api._world_block(w, {}, [], {"inventory": [], "equipment": None})
    assert "light" in block and set(block["light"]) == {"dark", "lit", "label"}
    assert block["light"]["dark"] is True   # noite sem luz
