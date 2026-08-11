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
from services.conflict_resolution import resolve_attack, virtude_para_tipo, virtude_value

_MANEUVERS = {"engajar", "desengajar", "guardar", "esconder", "procurar", "mover"}


# ==========================================================================
# Declaração estruturada de turno (R4)
# ==========================================================================
class TurnStep(BaseModel):
    kind: str = "pass"                 # attack | card | item | maneuver | object | move | pass
    card_id: Optional[str] = None
    item_id: Optional[str] = None
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
    # conflito-16: escolha antecipada da Carta que deve responder caso o
    # protagonista vire alvo nesta rodada. A janela ainda é validada pelo motor.
    reaction_card_id: Optional[str] = None


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
    out = {"ok": True, "logs": [], "attacks": [], "deaths": [], "terminal": [],
           "cards_used": []}
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
        if r.get("ok") and isinstance(r.get("effect"), dict):
            # Import local evita o ciclo de módulos: o orquestrador de rodada
            # importa este resolvedor. A função chamada materializa novamente o
            # EffectSpec e valida catálogo/potência/alvo antes de tocar a ficha.
            from services import conflict_orchestrator as orchestrator
            orchestrator.apply_effect_spec(
                scene, actors_by_id, r["effect"], out, rng=rng)
        return
    if kind == "item":
        _resolve_inventory_item(actor, actors_by_id, step, out)
        return
    if kind in ("attack", "card"):
        _resolve_attack_step(scene, actor, actor_id, actors_by_id, step, out,
                             state=state, rng=rng)


def _resolve_inventory_item(actor, actors_by_id, step, out):
    """Usa consumível do inventário como Ação. O inventário continua sendo um
    sistema reaproveitado no conflito v2; cura passa a operar sobre Vitalidade
    quando a ficha já está no schema v4."""
    import inventory
    target = actors_by_id.get(step.target_id) if step.target_id else None
    updated, logs = inventory.use_item_in_combat(
        actor, step.item_id or step.object_id or "", target=target)
    actor.clear()
    actor.update(updated)
    out["logs"] += logs


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


_DANO_BASE_ARMA = {"leve": 3, "marcial": 4, "versatil": 6, "pesada": 8}
_DANO_BASICO_DEFAULT = 3
_DIRECT_DAMAGE_EFFECTS = {"dano", "contra_ataque"}
_ATTACK_EFFECTS = _DIRECT_DAMAGE_EFFECTS | {
    "dot", "aplicar_condicao", "empurrao", "taunt", "marca",
}
_SUPPORT_EFFECTS = {
    "cura", "estabilizar", "protecao", "reposicionar", "esconder",
    "purga_condicao", "vantagem", "buff_defesa", "buff_acerto", "buff_dano",
    "reduzir_carga_aliado",
}


def _damage_from(card: Optional[dict], actor: dict, step) -> tuple:
    """Dano-base do ataque na escala NOVA (conflito-05/14): dano FLAT, não dados.
    Precedência: `efeito.dano_base` da Carta → categoria de arma da Carta →
    fórmula legada (Carta/step/`attack_formula`, mantida p/ inimigo legado e testes)
    → `dano_base_arma` do ator → básico default. Reusa `roll_dice_numeric` só na
    via legada de fórmula."""
    dtype = "cortante"
    if card:
        ef = card.get("efeito") or {}
        dtype = ef.get("damage_type") or ef.get("tipo_dano") or dtype
        if ef.get("dano_base") is not None:
            return max(0, int(ef["dano_base"])), dtype
        cat = ef.get("categoria_arma")
        if cat in _DANO_BASE_ARMA:
            return _DANO_BASE_ARMA[cat], dtype
        if ef.get("formula"):
            total, _ = cm.roll_dice_numeric(str(ef["formula"]))
            return max(0, total), dtype
    if step.params.get("dano_base") is not None:
        return max(0, int(step.params.get("dano_base") or 0)), dtype
    formula = step.params.get("formula") or actor.get("attack_formula")
    if formula:
        total, _ = cm.roll_dice_numeric(str(formula))
        return max(0, total), dtype
    base = actor.get("dano_base_arma")
    if base is not None:
        return max(0, int(base)), dtype
    return _DANO_BASICO_DEFAULT, dtype


def _resolve_attack_step(scene, actor, actor_id, actors_by_id, step, out, *, state, rng):
    card = None
    if step.card_id:
        from services import cards
        ruptura = bool(step.params.get("ruptura"))
        card = cards.effective_card(actor, step.card_id, ruptura=ruptura)
        if not card:
            out["logs"].append(f"Carta '{step.card_id}' desconhecida.")
            return
        if card.get("tipo") != "ativa":
            out["logs"].append(
                f"{card.get('name', step.card_id)} não é uma Carta ativa.")
            return
        effect_kind = str((card.get("efeito") or {}).get("kind") or "")
        if effect_kind not in _ATTACK_EFFECTS | _SUPPORT_EFFECTS:
            out["logs"].append(
                f"Efeito de Carta sem resolução de Ação: {effect_kind!r}.")
            return
        is_player_actor = bool(
            actor.get("is_player") or actor.get("player")
            or (state is not None and actor is state.get("player"))
        )
        if is_player_actor:
            res = None if state is None else (
                cards.use_ruptura(state, step.card_id) if ruptura
                else cards.use_card(state, step.card_id)
            )
        else:
            res = cards.use_enemy_card(actor, step.card_id)
        if res is not None:
            if not res["ok"]:
                out["logs"].append(res["error"])
                if is_player_actor:
                    return
                card = None
                step.card_id = None
                effect_kind = "dano"
            else:
                out["logs"].append(res["log"])
                out["cards_used"].append({
                    "actor_id": actor_id,
                    "card_id": step.card_id,
                    "card": card,
                    "economy": {
                        "cost": int(res.get("cost", 0) or 0),
                        "base_cost": int(res.get("base_cost", res.get("cost", 0)) or 0),
                        "dependencia_applied": bool(res.get("dependencia_applied")),
                    },
                })
        if effect_kind in _SUPPORT_EFFECTS:
            _resolve_support_card(scene, actor, actor_id, actors_by_id, step,
                                  card, out)
            return

    target = actors_by_id.get(step.target_id)
    if not target:
        out["logs"].append("Ataque sem alvo válido.")
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
    advantage += cs.consume_tactical_attack_modifier(
        scene, actor_id, step.target_id)
    directed_region = step.params.get("regiao")
    if directed_region is not None and cd.is_valid_hit_region(target, directed_region):
        # Mirar uma parte específica troca precisão por controle da consequência.
        advantage -= 1

    ruptura = bool(step.params.get("ruptura"))
    virtue_key = _virtude_key(card, step, actor)
    effective_virtue = (
        virtude_value(actor, virtue_key)
        + int(actor.get("_env_attack_mod", 0) or 0)
    )
    atk = resolve_attack(actor, target, virtude_key=virtue_key,
                         virtude_value_override=effective_virtue,
                         advantage=advantage, ruptura=ruptura, rng=rng)
    atk["actor_id"] = actor_id
    atk["target_id"] = step.target_id
    out["attacks"].append(atk)
    out["logs"].append(
        f"{actor.get('name', actor_id)} → {target.get('name', step.target_id)}: "
        f"{atk['resultado']} (total {atk['total']} vs Esquiva {atk['esquiva_alvo']}).")

    if atk["acerto"]:
        effect = (card or {}).get("efeito") or {}
        effect_kind = str(effect.get("kind") or "dano")
        if card is None or effect_kind in _DIRECT_DAMAGE_EFFECTS:
            dmg_base, dtype = _damage_from(card, actor, step)
            if actor_id == "player" or actor.get("is_player"):
                dmg_base += cm.early_game_damage_bonus(
                    int(actor.get("level", 1) or 1))
            dres = cd.resolve_damage_and_wounds(
                target, damage_base=dmg_base, damage_type=dtype,
                crit_mult=atk["efeito_principal_multiplicador"],
                directed_region=directed_region, rng=rng)
            atk["regiao"] = dres["regiao"]
            atk["dano_final"] = int(dres.get("dano_final", 0) or 0)
            out["logs"].append("; ".join(dres["log"]))
            _check_death(target, step.target_id, out)
        else:
            _apply_attack_card_effect(scene, actor, actor_id, target,
                                      step.target_id, card, out)

    # atacar oculto: revela DEPOIS da resolução (R11)
    if scene.get("positions", {}).get(actor_id):
        cs.reveal_after_attack(scene, actor_id)


def _resolve_support_card(scene, actor, actor_id, actors_by_id, step, card, out):
    """Resolve Cartas ativas que não exigem rolagem de ataque. O efeito nunca
    atravessa acidentalmente o pipeline de dano básico."""
    effect = card.get("efeito") or {}
    kind = str(effect.get("kind") or "")
    target = actors_by_id.get(step.target_id) or actor
    amount = _effect_amount(effect)
    duration = max(1, int(effect.get("duracao", effect.get("duration", 1)) or 1))
    name = card.get("name", step.card_id)

    if kind == "cura":
        before = int(target.get("vitalidade", 0) or 0)
        max_v = int(target.get("max_vitalidade", before) or before)
        target["vitalidade"] = min(max_v, before + amount)
        import gamedata
        gamedata.sync_legacy_hp_aliases(target)
        out["logs"].append(
            f"{target.get('name', step.target_id or actor_id)} recupera "
            f"{target['vitalidade'] - before} Vitalidade com {name}.")
    elif kind == "estabilizar":
        if target.get("estado_terminal"):
            target["estado_terminal"] = False
            target["dead"] = False
            target["vitalidade"] = max(1, int(target.get("vitalidade", 0) or 0))
            target["scar_pending"] = True
            out["logs"].append(f"{name} estabiliza {target.get('name', 'o alvo')}.")
        else:
            out["logs"].append(f"{name}: o alvo não está em Estado Terminal.")
    elif kind == "purga_condicao":
        conditions = target.setdefault("active_conditions", [])
        removed = conditions.pop(0) if conditions else None
        out["logs"].append(
            f"{name} remove {removed.get('name', 'uma condição')}."
            if removed else f"{name}: nenhuma condição para remover.")
    elif kind == "reduzir_carga_aliado":
        _ok, log = cm.reduce_ally_abyss(actor, target, amount)
        out["logs"].append(log)
    elif kind == "esconder":
        result = cs.hide(scene, actor_id, source=name)
        out["logs"].append(result.get("log") or result.get("error", ""))
    elif kind == "reposicionar":
        target_id = step.target_id or actor_id
        result = cs.move_distance(scene, target_id, step.direction or "afastar")
        out["logs"].append(result.get("log") or result.get("error", ""))
    else:
        stat = {
            "protecao": "protection", "vantagem": "advantage",
            "buff_defesa": "ac", "buff_acerto": "attack", "buff_dano": "damage",
        }.get(kind, kind)
        condition = {
            "name": name, "dot": 0, "duration": duration,
            "source": step.card_id, "stat": stat, "delta": amount,
        }
        out["logs"].append(cm.apply_condition(target, condition))


def _effect_amount(effect: dict) -> int:
    if effect.get("valor") is not None:
        return max(0, int(effect.get("valor") or 0))
    if effect.get("dano_base") is not None:
        return max(0, int(effect.get("dano_base") or 0))
    if effect.get("formula"):
        total, _ = cm.roll_dice_numeric(str(effect["formula"]))
        return max(0, total)
    return 1


def _apply_attack_card_effect(scene, actor, actor_id, target, target_id, card, out):
    effect = card.get("efeito") or {}
    kind = str(effect.get("kind") or "")
    amount = _effect_amount(effect)
    duration = max(1, int(effect.get("duracao", effect.get("duration", 1)) or 1))
    name = card.get("name", card.get("id", "Carta"))
    if kind == "dot":
        out["logs"].append(cm.apply_condition(target, {
            "name": name, "dot": amount, "duration": duration,
            "source": card.get("id", name),
        }))
    elif kind == "aplicar_condicao":
        raw = str(effect.get("condicao") or name)
        cond = cm.parse_condition(raw, source=card.get("id", name))
        cond["duration"] = duration
        out["logs"].append(cm.apply_condition(target, cond))
    elif kind == "empurrao":
        result = cs.move_distance(scene, target_id, "afastar")
        out["logs"].append(result.get("log") or result.get("error", ""))
    elif kind in ("taunt", "marca"):
        out["logs"].append(cm.apply_condition(target, {
            "name": name, "dot": 0, "duration": duration,
            "source": card.get("id", name), "control": kind,
            "source_actor_id": actor_id, "delta": amount,
        }))


def _check_death(target, target_id, out):
    """Fluxo de morte (conflito-07, decisão R6=A): último Crítico → Última Ação →
    Estado Terminal. A estabilização/`death_pending` é decidida FORA do turno pelo
    nó de combate (aqui só marca o gatilho)."""
    if death_flow.should_trigger_last_stand(target):
        death_flow.trigger_last_stand(target)
        if target_id not in out["terminal"]:
            out["terminal"].append(target_id)
        out["logs"].append(
            f"{target.get('name', target_id)} prepara sua Última Ação.")
