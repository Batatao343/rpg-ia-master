"""services/conflict_turn.py — orquestrador de TURNO do conflito v2 (spec conflito-13, Etapa 2).

A peça de COMPOSIÇÃO que as specs 01-12 deixaram de fora de propósito: compõe os
motores puros (`conflict_scene`, `conflict_resolution`, `conflict_damage`, `cards`,
`reactions`, `death_flow`) num turno inteiro `Pré-Ação → Ação → Pós-Ação`
(conflito-04), 100% determinístico, ZERO LLM. É o que o `combat_node` novo chama.

`TurnDeclaration` é a decisão estruturada de um turno (R4 do cutover): cada slot é
uma manobra, um ataque/Carta, uso de objeto ou movimento. O jogador e a IA
(perfil tático, conflito-08) emitem essa estrutura — não texto livre.
"""
import random
from typing import Dict, List, Optional

from pydantic import BaseModel, Field

import combat_mechanics as cm  # helpers que SOBREVIVEM (dados, condições, Entropia)
from services import conflict_scene as cs
from services import conflict_damage as cd
from services import death_flow
from services.conflict_resolution import resolve_attack, virtude_para_tipo

_MANEUVERS = {"engajar", "desengajar", "guardar", "esconder", "procurar", "mover"}


# ==========================================================================
# Declaração estruturada de turno (R4)
# ==========================================================================
class TurnStep(BaseModel):
    kind: str = "pass"                 # attack | card | maneuver | object | move | pass
    card_id: Optional[str] = None
    target_id: Optional[str] = None
    maneuver: Optional[str] = None     # engajar|desengajar|guardar|esconder|procurar|mover
    direction: Optional[str] = None    # p/ mover: aproximar|afastar
    virtude: Optional[str] = None
    source: Optional[str] = None       # p/ esconder: fonte plausível
    object_id: Optional[str] = None
    interaction: Optional[str] = None
    params: Dict = Field(default_factory=dict)


class TurnDeclaration(BaseModel):
    actor_id: str
    pre_acao: Optional[TurnStep] = None
    acao: Optional[TurnStep] = None
    pos_acao: Optional[TurnStep] = None


# ==========================================================================
# Resolução de um turno
# ==========================================================================
def resolve_turn(scene: dict, actors_by_id: Dict[str, dict], declaration, *,
                 state: Optional[dict] = None, rng=None) -> dict:
    """Resolve um turno inteiro. `actors_by_id` mapeia participant_id → ficha
    (player/inimigo/aliado). `state` (opcional) leva o jogador p/ a economia de
    Cartas. Retorna {logs, attacks, deaths, terminal}."""
    rng = rng or random.Random()
    decl = declaration if isinstance(declaration, TurnDeclaration) else TurnDeclaration(**declaration)
    actor = actors_by_id.get(decl.actor_id)
    if not actor:
        return {"ok": False, "logs": [f"Ator '{decl.actor_id}' fora da cena."],
                "attacks": [], "deaths": [], "terminal": []}

    cs.reset_turn_budget(scene, decl.actor_id)
    out = {"ok": True, "logs": [], "attacks": [], "deaths": [], "terminal": []}
    for slot in (decl.pre_acao, decl.acao, decl.pos_acao):
        if slot is None:
            continue
        _resolve_step(scene, actor, decl.actor_id, actors_by_id, slot, out,
                      state=state, rng=rng)
    return out


def _resolve_step(scene, actor, actor_id, actors_by_id, step, out, *, state, rng):
    kind = str(step.kind or "pass").lower()
    if kind == "pass":
        return
    if kind == "move" or (kind == "maneuver" and step.maneuver == "mover"):
        r = cs.move_distance(scene, actor_id, step.direction or "aproximar")
        out["logs"].append(r.get("log") or r.get("error", ""))
        return
    if kind == "maneuver":
        _resolve_maneuver(scene, actor_id, step, out)
        return
    if kind == "object":
        r = cs.apply_object_interaction(scene, step.object_id, step.interaction, actor_id)
        out["logs"].append(r.get("log") or r.get("error", ""))
        return
    if kind in ("attack", "card"):
        _resolve_attack_step(scene, actor, actor_id, actors_by_id, step, out,
                             state=state, rng=rng)


def _resolve_maneuver(scene, actor_id, step, out):
    m = str(step.maneuver or "").lower()
    if m == "engajar":
        r = cs.engage(scene, actor_id, step.target_id)
    elif m == "desengajar":
        r = cs.disengage(scene, actor_id, step.target_id)
    elif m == "guardar":
        r = cs.guard(scene, actor_id)
    elif m == "esconder":
        r = cs.hide(scene, actor_id, source=step.source)
    elif m == "procurar":
        r = cs.search(scene, actor_id, step.target_id)
    else:
        r = {"ok": False, "error": f"Manobra desconhecida: {m}.", "log": ""}
    out["logs"].append(r.get("log") or r.get("error", ""))


def _virtude_key(card: Optional[dict], step, actor: dict) -> str:
    if step.virtude:
        return step.virtude
    if card:
        permitidas = card.get("virtude_permitida") or []
        if permitidas:
            return permitidas[0]
        return virtude_para_tipo(card.get("tipo"))
    return "forca"


def _damage_from(card: Optional[dict], actor: dict, step) -> tuple:
    """Dano-base do ataque: fórmula da Carta (efeito dano) ou ataque básico.
    Reusa `combat_mechanics.roll_dice_numeric` (helper que SOBREVIVE)."""
    formula = None
    dtype = "cortante"
    if card:
        ef = card.get("efeito") or {}
        formula = ef.get("formula")
        dtype = ef.get("damage_type") or ef.get("tipo_dano") or dtype
    if not formula:
        formula = str(step.params.get("formula") or actor.get("attack_formula") or "1d6")
    total, _ = cm.roll_dice_numeric(formula)
    return max(0, total), dtype


def _resolve_attack_step(scene, actor, actor_id, actors_by_id, step, out, *, state, rng):
    target = actors_by_id.get(step.target_id)
    if not target:
        out["logs"].append("Ataque sem alvo válido.")
        return

    card = None
    if step.card_id:
        from services import cards
        card = cards.get_card(step.card_id)
        if state is not None:
            res = cards.use_card(state, step.card_id)
            if not res["ok"]:
                out["logs"].append(res["error"])
                return

    # Vantagem/Desvantagem por ocultação (R10/R11) + Guarda (R8, conflito-06)
    occ = cs.occlusion_attack_modifier(scene, actor_id, step.target_id) \
        if scene.get("positions", {}).get(actor_id) else {"can_target": True, "advantage": 0}
    if not occ["can_target"]:
        out["logs"].append(f"{step.target_id} sem posição conhecida — não pode mirar direto.")
        return
    advantage = occ["advantage"]
    advantage += cs.guard_offense_modifier(scene, actor_id)
    advantage += cs.guard_defense_modifier(scene, step.target_id)

    ruptura = bool(step.params.get("ruptura"))
    atk = resolve_attack(actor, target, virtude_key=_virtude_key(card, step, actor),
                         advantage=advantage, ruptura=ruptura, rng=rng)
    out["attacks"].append(atk)
    out["logs"].append(
        f"{actor.get('name', actor_id)} → {target.get('name', step.target_id)}: "
        f"{atk['resultado']} (total {atk['total']} vs Esquiva {atk['esquiva_alvo']}).")

    if atk["acerto"]:
        dmg_base, dtype = _damage_from(card, actor, step)
        dres = cd.resolve_damage_and_wounds(
            target, damage_base=dmg_base, damage_type=dtype,
            crit_mult=atk["efeito_principal_multiplicador"],
            directed_region=step.params.get("regiao", "torso"))
        out["logs"].append("; ".join(dres["log"]))
        _check_death(target, step.target_id, out)

    # atacar oculto: revela DEPOIS da resolução (R11)
    if scene.get("positions", {}).get(actor_id):
        cs.reveal_after_attack(scene, actor_id)


def _check_death(target, target_id, out):
    """Fluxo de morte (conflito-07, decisão R6=A): último Crítico → Última Ação →
    Estado Terminal. A estabilização/`death_pending` é decidida FORA do turno pelo
    nó de combate (aqui só marca o gatilho)."""
    if death_flow.should_trigger_last_stand(target):
        death_flow.trigger_last_stand(target)
        death_flow.enter_terminal_state(target)
        out["terminal"].append(target_id)
        out["logs"].append(f"{target.get('name', target_id)} entra em Estado Terminal!")
