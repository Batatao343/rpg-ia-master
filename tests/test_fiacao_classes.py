"""Suíte da spec fiacao-regras-orfas-classes — taunt · Transformação · Purga + R4.

Fecha os 3 bugs de "mecânica declarada nos dados sem fiação no motor" achados
na auditoria de 2026-07-19. Offline/determinístico (MockLLM via conftest).
Ver specs/fiacao-regras-orfas-classes.md.
"""
import random

from langchain_core.messages import HumanMessage

import combat_mechanics as cm


DEVOTO = "Devoto do Abismo"


def _p(cls, **over):
    p = {
        "name": "Ava", "class_name": cls,
        "hp": 30, "max_hp": 30, "entropy": 0, "max_entropy": 16, "abyss_charge": 0,
        "attributes": {"str": 12, "dex": 14, "con": 12, "int": 14, "wis": 14, "cha": 10},
        "known_abilities": ["ataque_basico"], "active_conditions": [],
        "ability_cooldowns": {}, "equipment": {"weapon": None},
    }
    p.update(over)
    return p


def _enemy(**over):
    e = {"id": "e1", "name": "Goblin", "hp": 20, "max_hp": 20, "defense": 11,
         "status": "ativo", "attributes": {"dex": 12, "con": 10},
         "behavior": {"profile": "tatico"}, "active_conditions": [],
         "attacks": [{"name": "Adaga", "bonus": 3, "damage": "1d4+1"}]}
    e.update(over)
    return e


def _ally(**over):
    a = {"id": "a1", "name": "Bru", "hp": 5, "max_hp": 20, "defense": 10,
         "status": "ativo", "active": True, "attributes": {"dex": 10, "con": 10},
         "active_conditions": []}
    a.update(over)
    return a


def _taunted(enemy):
    enemy["active_conditions"].append(
        {"name": "Provocado", "control": "taunt", "duration": 2})
    return enemy


# --- Etapa 1 (R4): todo kind declarado nos dados tem handler no motor --------

def test_todo_kind_declarado_tem_handler():
    """Anti-órfão estrutural: kind novo nos JSONs gerados sem handler = vermelho.
    (Teria pego taunt/transformacao/reduce_ally_abyss dormentes.)"""
    from gamedata import ABILITIES, CLASSES
    hk = cm.HANDLED_KINDS
    for cname, cd in CLASSES.items():
        trig = (cd.get("entropy_trigger") or {}).get("kind")
        if trig:
            assert trig in hk["entropy_trigger"], f"{cname}: entropy_trigger {trig} órfão"
        sr = (cd.get("special_rule") or {}).get("kind")
        if sr:
            assert sr in hk["special_rule"], f"{cname}: special_rule {sr} órfão"
        cons = (cd.get("abyss") or {}).get("consequence")
        if cons:
            assert cons in hk["consequence"], f"{cname}: consequence {cons} órfã"
        for bn, bd in (cd.get("branches") or {}).items():
            ov_trig = ((bd.get("overrides") or {}).get("entropy_trigger") or {}).get("kind")
            if ov_trig:
                assert ov_trig in hk["entropy_trigger"], f"{cname}/{bn}: {ov_trig} órfão"
    for aid, ab in ABILITIES.items():
        for eff in ab.get("effects") or []:
            if isinstance(eff, dict):
                assert eff.get("kind") in hk["effect"], f"{aid}: effect {eff.get('kind')} órfão"
        for pe in ab.get("passive_effects") or []:
            assert pe.get("trigger") in hk["passive_trigger"], \
                f"{aid}: passive trigger {pe.get('trigger')} órfão"


# --- Etapa 2 (R1): taunt segura alvo ----------------------------------------

def test_taunt_forca_alvo():
    """Inimigo tatico SEM taunt sempre pega o aliado ferido; taunted, o player
    (provocador) vira alvo numa fração alta dos rolls."""
    player = _p(DEVOTO, entropy=10)
    ally = _ally(hp=2)                       # menor HP% — alvo natural do tatico
    random.seed(42)
    livre = sum(cm.pick_target(_enemy(), [player, ally], player=player) is player
                for _ in range(100))
    assert livre == 0                        # sem taunt, tatico NUNCA pega o player

    random.seed(42)
    taunted = sum(cm.pick_target(_taunted(_enemy()), [player, ally], player=player) is player
                  for _ in range(200))
    assert taunted >= 120                    # chance ≈ 0.75 com Entropia 10


def test_taunt_expira_volta_ao_perfil():
    player = _p(DEVOTO, entropy=10)
    ally = _ally(hp=2)
    e = _taunted(_enemy())
    e["active_conditions"] = []              # condição expirou
    random.seed(7)
    assert all(cm.pick_target(e, [player, ally], player=player) is ally
               for _ in range(50))


def test_taunt_escala_com_entropia():
    """Regra especial do Devoto viva: mais Entropia = mais aggro (mesma seed)."""
    ally = _ally(hp=2)

    def hits(entropy):
        p = _p(DEVOTO, entropy=entropy)
        random.seed(99)
        return sum(cm.pick_target(_taunted(_enemy()), [p, ally], player=p) is p
                   for _ in range(400))

    assert hits(12) > hits(0)                # 0.8 vs 0.5 de chance


def test_pick_target_sem_player_retrocompativel():
    ally = _ally(hp=2)
    p = _p(DEVOTO)
    assert cm.pick_target(_enemy(), [p, ally]) is ally   # assinatura antiga OK


# --- Etapa 3 (R2): Transformação roda no round ------------------------------

def test_transformacao_aplicada_no_combat_node():
    """Integração: Corruptor com Carga moderada entra no round → debuff ativo."""
    import agents.combat as combat
    random.seed(5)
    state = {
        "game_id": "transf", "messages": [HumanMessage(content="Ataco o goblin")],
        "player": _p("Corruptor", abyss_charge=4, hp=40, max_hp=40, entropy=8,
                     known_abilities=["ataque_basico", "corroer_vontade"]),
        "enemies": [_enemy(hp=30)], "combat": {"active": True},
        "world": {"current_location": "Pântano da Melancolia",
                  "current_location_id": "pantano_melancolia",
                  "turn_count": 3, "danger_level": 2, "visited": ["pantano_melancolia"]},
        "party": [],
    }
    out = combat.combat_node(state)
    conds = out["player"].get("active_conditions") or []
    assert any(str(c.get("name", "")).startswith("Transformação") for c in conds)


def test_transformacao_renova_sem_stack():
    p = _p("Corruptor", abyss_charge=4,
           known_abilities=["ataque_basico", "corroer_vontade"])
    cm.apply_transformacao(p)
    cm.apply_transformacao(p)
    transf = [c for c in p["active_conditions"]
              if str(c.get("name", "")).startswith("Transformação")]
    assert len(transf) == 1                  # renova, não empilha


def test_transformacao_tier_nenhum_e_outras_classes():
    limpo = _p("Corruptor", abyss_charge=0)
    cm.apply_transformacao(limpo)
    assert limpo["active_conditions"] == []
    devoto = _p(DEVOTO, abyss_charge=6)
    cm.apply_transformacao(devoto)
    assert devoto["active_conditions"] == [] # consequência é só do Corruptor


# --- Etapa 4 (R3): Purga da Carga despachada --------------------------------

def test_purga_reduz_carga_do_aliado_mais_carregado():
    from gamedata import ABILITIES
    medic = _p("Médico de Campo", entropy=10,
               known_abilities=["ataque_basico", "purga_da_carga"])
    a1 = _ally(name="Bru", abyss_charge=5, hp=10)
    a2 = _ally(id="a2", name="Cal", abyss_charge=2, hp=10)
    logs = cm.resolve_player_action(
        medic, [_enemy()],
        {"ability_id": "purga_da_carga", "target": "", "is_allowed": True},
        ABILITIES, allies=[a1, a2])
    assert a1["abyss_charge"] == 3           # amount=2 no MAIS carregado
    assert a2["abyss_charge"] == 2           # o outro intacto
    assert medic["entropy"] == 10 - 5        # só o custo da habilidade (5)
    assert any("purga" in l.lower() for l in logs)


def test_purga_sem_alvo_nao_gasta():
    from gamedata import ABILITIES
    medic = _p("Médico de Campo", entropy=10,
               known_abilities=["ataque_basico", "purga_da_carga"])
    logs = cm.resolve_player_action(
        medic, [_enemy()],
        {"ability_id": "purga_da_carga", "target": "", "is_allowed": True},
        ABILITIES, allies=[_ally(abyss_charge=0, hp=10)])
    assert medic["entropy"] == 10            # falha ANTES de pagar
    assert medic.get("ability_cooldowns", {}) == {}
    assert any("purgar" in l.lower() for l in logs)


def test_purga_nao_medico_bloqueada():
    from gamedata import ABILITIES
    intruso = _p("Sangromante", entropy=10,
                 known_abilities=["ataque_basico", "purga_da_carga"])
    ally = _ally(abyss_charge=5, hp=10)
    cm.resolve_player_action(
        intruso, [_enemy()],
        {"ability_id": "purga_da_carga", "target": "", "is_allowed": True},
        ABILITIES, allies=[ally])
    assert ally["abyss_charge"] == 5         # guard de classe segue valendo
    assert intruso["entropy"] == 10
