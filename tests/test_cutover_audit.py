"""Auditoria final do cutover conflito-13: o motor d20/AC não existe mais."""

import os
import re

import combat_mechanics

# Motor d20+AC antigo — substituído pelos services novos (conflito-04/07/08).
DYING_FUNCTIONS = [
    "resolve_player_action", "resolve_enemy_turn", "resolve_ally_turn",
    "roll_initiative", "get_behavior", "choose_enemy_attack", "pick_target",
    "check_morale", "usable_enemy_abilities", "apply_boss_phase",
    "combat_suggestions",
]

# Helpers genéricos + sistema de classes Entropia/Carga (v4) + condições/passivas.
SURVIVING_FUNCTIONS = [
    "actor_mods", "normalize_attr", "roll_dice_numeric", "resolve_damage_formula",
    "parse_condition", "tick_conditions", "player_passives",
    "entropy_config", "abyss_tier", "apply_entropy_trigger", "apply_scar",
    "apply_transformacao", "reduce_ally_abyss", "check_recidiva",
    "compute_player_combat_stats",
]

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_SERVICES = os.path.join(_ROOT, "services")


def _strip_comments(src: str) -> str:
    """Remove comentários de linha e docstrings triplas — só sobra código real."""
    src = re.sub(r'"""(?:.|\n)*?"""', "", src)
    src = re.sub(r"'''(?:.|\n)*?'''", "", src)
    return "\n".join(line.split("#", 1)[0] for line in src.splitlines())


def test_funcoes_d20_foram_removidas():
    for fn in DYING_FUNCTIONS:
        assert not hasattr(combat_mechanics, fn), f"{fn} ainda existe após o cutover"


def test_funcoes_que_sobrevivem_continuam_no_modulo():
    for fn in SURVIVING_FUNCTIONS:
        assert hasattr(combat_mechanics, fn), f"{fn} deveria sobreviver ao cutover"


def test_nenhum_service_novo_depende_do_motor_antigo():
    """O motor novo (`services/*`) NÃO pode chamar nenhuma função d20+AC morredoura
    — se chamar, a remoção da Etapa 3 quebraria o motor novo."""
    offenders = []
    for name in os.listdir(_SERVICES):
        if not name.endswith(".py"):
            continue
        with open(os.path.join(_SERVICES, name), encoding="utf-8") as f:
            code = _strip_comments(f.read())
        for fn in DYING_FUNCTIONS:
            if re.search(rf"\b{fn}\s*\(", code):
                offenders.append(f"{name}:{fn}")
    assert not offenders, f"service novo depende de função morredoura: {offenders}"


def test_catalogo_antigo_foi_removido():
    assert not os.path.exists(os.path.join(_ROOT, "data", "player_abilities.json"))
