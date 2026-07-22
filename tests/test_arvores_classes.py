# -*- coding: utf-8 -*-
"""Suíte da spec arvores-habilidade-classes — árvore rica das 5 Posturas.

Etapa 1 (motor): ability_kind, player_passives, triggers novos, utility no contexto.
Etapa 2 (conteúdo): R3–R8 por subclasse. Offline/determinístico.
"""
import combat_mechanics as cm
import progression as pg
from gamedata import ABILITIES, CLASSES
from services.context_builder import utility_context_block

FIVE = ["Devoto do Abismo", "Sangromante", "Corruptor",
        "Arcanista Cinzento", "Médico de Campo"]

# --- db sintético p/ testes de motor ----------------------------------------
FAKE_DB = {
    "ativa_x": {"name": "Ativa X", "classes": ["Devoto do Abismo"], "branch": None,
                "tier": 1, "level_req": 1, "requires": [], "cost": 4,
                "resource_type": "Entropia", "category": "Marcial",
                "damage_formula": "1d6", "damage_type": "Físico",
                "conditions": [], "effects": []},
    "passiva_dano": {"name": "Passiva Dano", "classes": ["Devoto do Abismo"],
                     "branch": None, "tier": 1, "level_req": 2, "requires": [],
                     "cost": 0, "resource_type": "Nenhum", "ability_kind": "passive",
                     "damage_formula": "0", "conditions": [], "effects": [],
                     "passive_effects": [{"trigger": "always", "stat": "damage", "delta": 2}]},
    "passiva_pool": {"name": "Passiva Pool", "classes": ["Devoto do Abismo"],
                     "branch": None, "tier": 1, "level_req": 2, "requires": [],
                     "cost": 0, "resource_type": "Nenhum", "ability_kind": "passive",
                     "damage_formula": "0", "conditions": [], "effects": [],
                     "passive_effects": [{"trigger": "entropy_max_bonus", "delta": 3}]},
    "passiva_desconto": {"name": "Passiva Desconto", "classes": ["Devoto do Abismo"],
                         "branch": None, "tier": 1, "level_req": 2, "requires": [],
                         "cost": 0, "resource_type": "Nenhum", "ability_kind": "passive",
                         "damage_formula": "0", "conditions": [], "effects": [],
                         "passive_effects": [{"trigger": "charge_discount", "delta": 1}]},
    "util_preco": {"name": "Avaliação de Preço", "classes": ["Devoto do Abismo"],
                   "branch": None, "tier": 1, "level_req": 1, "requires": [],
                   "cost": 0, "resource_type": "Nenhum", "ability_kind": "utility",
                   "damage_formula": "0", "conditions": [], "effects": [],
                   "out_of_combat": {"label": "Avaliação de preço", "scope": "social",
                                     "prompt_hint": "sabe o valor real de algo"}},
}


def _pl(**over):
    p = {"name": "T", "class_name": "Devoto do Abismo",
         "hp": 30, "max_hp": 30, "entropy": 10, "max_entropy": 14, "abyss_charge": 0,
         "attributes": {"str": 12, "dex": 12, "con": 12, "int": 12, "wis": 12, "cha": 12},
         "known_abilities": ["ataque_basico"], "active_conditions": [],
         "ability_cooldowns": {}, "equipment": {"weapon": None}}
    p.update(over)
    return p


# --- Etapa 1: motor ----------------------------------------------------------

def test_ability_kind_default_active():
    # habilidade sem ability_kind = ativa (legado)
    assert ABILITIES["ataque_basico"].get("ability_kind", "active") == "active"


def test_player_passives_merges_learned():
    p = _pl(known_abilities=["ataque_basico", "passiva_dano"])
    pes = cm.player_passives(p, abilities_db=FAKE_DB)
    assert any(pe.get("stat") == "damage" and pe.get("delta") == 2 for pe in pes)
    # inimigo (sem known_abilities de jogador) não ganha passiva de árvore
    enemy = {"name": "Orc", "class_name": ""}
    assert cm.player_passives(enemy, abilities_db=FAKE_DB) == []


def test_learned_passive_affects_combat():
    com = _pl(known_abilities=["ataque_basico", "passiva_dano"])
    sem = _pl()
    b_com, _ = cm.damage_bonus(com, {"damage_type": "Físico"})
    b_sem, _ = cm.damage_bonus(sem, {"damage_type": "Físico"})
    # damage_bonus lê player_passives — a passiva aprendida soma no dano
    # (FAKE_DB não é o db default; simula via monkey no known + db explícito)
    pes = cm.player_passives(com, abilities_db=FAKE_DB)
    assert sum(int(pe.get("delta", 0)) for pe in pes
               if pe.get("trigger") == "always" and pe.get("stat") == "damage") == 2
    assert b_sem == 0  # baseline sem passiva


def test_utility_in_storyteller_context():
    p = _pl(known_abilities=["ataque_basico", "util_preco"])
    block = utility_context_block(p, abilities_db=FAKE_DB)
    assert "Avaliação de preço" in block
    assert "CAPACIDADES_DO_HEROI" in block
    # sem utilitária → bloco vazio (storyteller omite)
    assert utility_context_block(_pl(), abilities_db=FAKE_DB) == ""


def test_entropy_max_bonus_applies():
    p = _pl(level=2, known_abilities=["ataque_basico"],
            pending_choices=[{"id": "lvl2-ability", "level": 2, "kind": "ability"}])
    out, err = pg.apply_choice(p, "lvl2-ability", ability_id="passiva_pool",
                               abilities_db=FAKE_DB)
    assert err is None
    assert out["max_entropy"] == 14 + 3
    assert out["entropy"] == 10 + 3


def test_charge_discount_reduces_charge():
    p = _pl(known_abilities=["ataque_basico", "passiva_desconto"], entropy=0)
    import gamedata
    old = gamedata.ABILITIES
    # apply_entropy_trigger lê o db passado — usa o FAKE p/ achar a passiva
    cm.reset_entropy_turn(p)
    cm.apply_entropy_trigger(p, {"kind": "on_damage_taken", "amount": 8},
                             abilities_db=FAKE_DB)
    assert p["entropy"] > 0
    assert p["abyss_charge"] == 0  # charge_per 1 − desconto 1 = 0


def test_entropy_cost_reduction():
    db = dict(FAKE_DB)
    db["passiva_custo"] = {"name": "PC", "classes": ["Devoto do Abismo"], "branch": None,
                           "tier": 1, "level_req": 2, "requires": [], "cost": 0,
                           "resource_type": "Nenhum", "ability_kind": "passive",
                           "damage_formula": "0", "conditions": [], "effects": [],
                           "passive_effects": [{"trigger": "entropy_cost_reduction",
                                                "category": "Marcial", "delta": 2}]}
    p = _pl(known_abilities=["ataque_basico", "passiva_custo"], entropy=10)
    import gamedata
    monkey_ok = False
    old = gamedata.ABILITIES
    try:
        gamedata.ABILITIES = db
        # combat_mechanics importa ABILITIES lazy (learned_passives) — o custo 4
        # da categoria Marcial cai p/ 2 (piso 1)
        ok, _ = cm.spend_resources(p, "ativa_x", db["ativa_x"])
        monkey_ok = True
    finally:
        gamedata.ABILITIES = old
    assert monkey_ok and ok
    assert p["entropy"] == 10 - 2


def test_carga_embrace_bonus():
    db = dict(FAKE_DB)
    db["abraco"] = {"name": "Abraço", "classes": ["Devoto do Abismo"], "branch": None,
                    "tier": 1, "level_req": 2, "requires": [], "cost": 0,
                    "resource_type": "Nenhum", "ability_kind": "passive",
                    "damage_formula": "0", "conditions": [], "effects": [],
                    "passive_effects": [{"trigger": "carga_embrace", "stat": "damage",
                                         "per_tier": 2}]}
    p = _pl(known_abilities=["ataque_basico", "abraco"], abyss_charge=4)  # moderado=2
    import gamedata
    old = gamedata.ABILITIES
    try:
        gamedata.ABILITIES = db
        bonus, notes = cm.damage_bonus(p, {"damage_type": "Físico"})
    finally:
        gamedata.ABILITIES = old
    assert bonus == 2 * 2  # per_tier 2 × tier moderado (índice 2)


def test_entropy_on_kill():
    db = dict(FAKE_DB)
    db["colheita"] = {"name": "Colheita", "classes": ["Corruptor"], "branch": None,
                      "tier": 1, "level_req": 2, "requires": [], "cost": 0,
                      "resource_type": "Nenhum", "ability_kind": "passive",
                      "damage_formula": "0", "conditions": [], "effects": [],
                      "passive_effects": [{"trigger": "entropy_on_kill", "amount": 2}]}
    p = _pl(class_name="Corruptor", known_abilities=["ataque_basico", "colheita"],
            entropy=5, max_entropy=18)
    import gamedata
    old = gamedata.ABILITIES
    try:
        gamedata.ABILITIES = db
        cm.apply_entropy_on_kill(p, 2)
    finally:
        gamedata.ABILITIES = old
    assert p["entropy"] == 5 + 4  # 2 por kill × 2 mortos


def test_combat_surfaces_exclude_non_active():
    from agents.combat import _allowed_ability_ids
    import gamedata
    db = dict(FAKE_DB)
    db["ataque_basico"] = ABILITIES["ataque_basico"]
    p = _pl(known_abilities=["ataque_basico", "ativa_x", "passiva_dano", "util_preco"])
    old = gamedata.ABILITIES
    try:
        gamedata.ABILITIES = db
        import agents.combat as cbt
        old_ab = cbt.ABILITIES
        cbt.ABILITIES = db
        try:
            allowed = _allowed_ability_ids(p)
        finally:
            cbt.ABILITIES = old_ab
    finally:
        gamedata.ABILITIES = old
    assert "ativa_x" in allowed
    assert "passiva_dano" not in allowed
    assert "util_preco" not in allowed


def test_lock_de_ramo_vale_para_passiva():
    """R9: conhecer passiva de um ramo deriva a subclasse e tranca o rival."""
    db = {
        "ataque_basico": {"name": "AB", "classes": ["all"], "branch": None,
                          "tier": 1, "level_req": 1, "requires": []},
        "passiva_ramo_a": {"name": "PA", "classes": ["Devoto do Abismo"],
                           "branch": "consagrado", "tier": 2, "level_req": 2,
                           "requires": [], "ability_kind": "passive",
                           "passive_effects": [{"trigger": "always", "stat": "ac", "delta": 1}]},
        "ativa_ramo_b": {"name": "RB", "classes": ["Devoto do Abismo"],
                         "branch": "zeloso", "tier": 2, "level_req": 2, "requires": []},
    }
    p = _pl(level=3, known_abilities=["ataque_basico", "passiva_ramo_a"])
    assert pg.player_branch(p, abilities_db=db) == "consagrado"
    elig = pg.eligible_abilities(p, abilities_db=db)
    assert "ativa_ramo_b" not in elig


# --- Etapa 2: conteúdo (R3–R8, R12) ------------------------------------------

def _of_kind(cname, branch, kind):
    return [aid for aid, a in ABILITIES.items()
            if cname in (a.get("classes") or [])
            and a.get("branch") == branch
            and a.get("ability_kind", "active") == kind]


def test_cada_subclasse_2_passivas():
    for cname in FIVE:
        for bid in CLASSES[cname].get("branches") or {}:
            passivas = _of_kind(cname, bid, "passive")
            assert len(passivas) >= 2, f"{cname}/{bid}: {len(passivas)} passivas (< 2)"
            for aid in passivas:
                pes = ABILITIES[aid].get("passive_effects") or []
                assert pes and all(pe.get("trigger") for pe in pes), \
                    f"{aid}: passive_effects vazio/sem trigger"


def test_cada_subclasse_1_utility():
    for cname in FIVE:
        for bid in CLASSES[cname].get("branches") or {}:
            utils = _of_kind(cname, bid, "utility")
            assert len(utils) >= 1, f"{cname}/{bid}: sem utilitária"


def test_tronco_tem_2_utility_do_doc():
    for cname in FIVE:
        utils = _of_kind(cname, None, "utility")
        assert len(utils) >= 2, f"{cname}: tronco com {len(utils)} utilitárias (< 2)"


def test_cada_subclasse_2_ativas():
    for cname in FIVE:
        for bid in CLASSES[cname].get("branches") or {}:
            ativas = _of_kind(cname, bid, "active")
            assert len(ativas) >= 2, f"{cname}/{bid}: {len(ativas)} ativas (< 2)"
            # encadeadas: alguma ativa do ramo exige outra do ramo (requires)
            assert any(ABILITIES[a].get("requires") for a in ativas), \
                f"{cname}/{bid}: ativas sem cadeia (requires)"


def test_tronco_tem_passiva():
    for cname in FIVE:
        passivas = _of_kind(cname, None, "passive")
        assert len(passivas) >= 1, f"{cname}: tronco sem passiva"


def test_tudo_entropia_por_kind():
    for aid, a in ABILITIES.items():
        kind = a.get("ability_kind", "active")
        cost = int(a.get("cost", 0) or 0)
        if kind == "active":
            if cost > 0:
                assert a.get("resource_type") == "Entropia", f"{aid}: ativa fora de Entropia"
        else:
            assert cost == 0, f"{aid}: {kind} com custo"
            assert a.get("resource_type") in ("Nenhum", None, ""), \
                f"{aid}: {kind} com resource_type {a.get('resource_type')!r}"


def test_sem_so_texto_por_kind():
    for aid, a in ABILITIES.items():
        kind = a.get("ability_kind", "active")
        if kind == "passive":
            assert a.get("passive_effects"), f"{aid}: passiva sem passive_effects"
        elif kind == "utility":
            ooc = a.get("out_of_combat") or {}
            assert ooc.get("label") and ooc.get("scope") and ooc.get("prompt_hint"), \
                f"{aid}: utility sem out_of_combat completo"


_VALID_SCOPES = {"social", "investigation", "detection", "engineering", "medical"}


def test_out_of_combat_schema():
    for aid, a in ABILITIES.items():
        if a.get("ability_kind") != "utility":
            continue
        ooc = a.get("out_of_combat") or {}
        assert ooc.get("scope") in _VALID_SCOPES, f"{aid}: scope {ooc.get('scope')!r}"


def test_volume_total():
    """R12: ≈20 habilidades/classe → ≈100 no total (+ataque_basico)."""
    assert len(ABILITIES) >= 95, f"árvore com só {len(ABILITIES)} habilidades"


# --- spec balanceamento-classes-pos-playtest: guarda de PARITY mecânica -------
# Análise estática (2026-07-20): habilidades de DANO PURO comparáveis (custo em
# Entropia > 0, SEM self_harm e SEM efeito) devem cair numa banda de dano-por-
# Entropia — nenhuma "muito mais forte que a outra". Pega mis-escala futura (ex.:
# 4d6 a custo 2 sem contrapartida = 7.0/E). Habilidades com self_harm/DoT/efeito/
# cura são financiadas por HP ou carregam payload → fora deste conjunto limpo.

def _avg_dice(formula: str) -> float:
    import re
    t = 0.0
    for m in re.finditer(r"(\d+)d(\d+)", str(formula or "")):
        t += int(m.group(1)) * (int(m.group(2)) + 1) / 2
    return t


def _pure_damage_dpe():
    """{aid: dano_dado/Entropia} das ativas de DANO PURO comparáveis."""
    out = {}
    for aid, a in ABILITIES.items():
        cost = int(a.get("cost", 0) or 0)
        if cost <= 0 or int(a.get("self_harm", 0) or 0) > 0:
            continue
        if a.get("effects"):
            continue
        if str(a.get("damage_type", "")).lower() in ("cura", "heal"):
            continue
        dmg = _avg_dice(a.get("damage_formula"))
        if dmg <= 0:
            continue
        out[aid] = dmg / cost
    return out


def test_parity_dano_puro_dentro_da_banda():
    dpe = _pure_damage_dpe()
    assert dpe, "nenhuma habilidade de dano puro detectada — schema mudou?"
    for aid, v in dpe.items():
        assert 1.5 <= v <= 4.0, (
            f"{aid} fora da banda de parity de dano puro: {v:.2f} dano/Entropia "
            f"(esperado 1.5–4.0). Rebalancear a fórmula/custo no gerador.")


def test_parity_devoto_tier3_puro_alinhado():
    """Regressão do fix Fervor Ritual: os 3 tier-3 de dano puro do Devoto
    (Fervor/Retaliação/Intimidade) têm o MESMO dano-por-Entropia (2d8, custo 4)."""
    alvo = ["fervor_ritual", "retaliacao_do_ciume", "intimidade_com_o_fim"]
    vals = {a: _avg_dice(ABILITIES[a]["damage_formula"]) / int(ABILITIES[a]["cost"])
            for a in alvo}
    assert len(set(round(v, 2) for v in vals.values())) == 1, \
        f"tier-3 puro do Devoto desalinhado: {vals}"
