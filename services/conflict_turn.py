"""services/conflict_turn.py — orquestrador de TURNO do conflito v2 (spec conflito-13, Etapa 2).

A peça de COMPOSIÇÃO que as specs 01-12 deixaram de fora de propósito: compõe os
motores puros (`conflict_scene`, `conflict_resolution`, `conflict_damage`, `cards`,
`reactions`, `death_flow`) num turno inteiro `Pré-Ação → Ação → Pós-Ação`
(conflito-04), 100% determinístico, ZERO LLM. É o que o `combat_node` novo chama.

`TurnDeclaration` é a decisão estruturada de um turno (R4 do cutover): cada slot é
uma manobra, um ataque/Carta, uso de objeto ou movimento. O jogador e a IA
(perfil tático, conflito-08) emitem essa estrutura — não texto livre.
"""

import logging
import random
from typing import Dict, List, Optional

from pydantic import BaseModel, Field

import combat_mechanics as cm  # helpers que SOBREVIVEM (dados, condições, Entropia)
from services import combat_flags, death_flow
from services import conflict_damage as cd
from services import conflict_scene as cs
from services.conflict_resolution import resolve_attack, virtude_para_tipo, virtude_value

_MANEUVERS = {"engajar", "desengajar", "guardar", "esconder", "procurar", "mover"}

logger = logging.getLogger("rpg.conflict")


# ==========================================================================
# Declaração estruturada de turno (R4)
# ==========================================================================
class TurnStep(BaseModel):
    kind: str = "pass"  # attack | card | item | maneuver | object | move | pass
    card_id: str | None = None
    item_id: str | None = None
    target_id: str | None = None
    maneuver: str | None = None  # engajar|desengajar|guardar|esconder|procurar|mover
    direction: str | None = None  # p/ mover: aproximar|afastar
    virtude: str | None = None
    source: str | None = None  # p/ esconder: fonte plausível
    object_id: str | None = None
    interaction: str | None = None
    params: dict = Field(default_factory=dict)


class TurnDeclaration(BaseModel):
    actor_id: str
    pre_acao: TurnStep | None = None
    acao: TurnStep | None = None
    pos_acao: TurnStep | None = None
    # conflito-16: escolha antecipada da Carta que deve responder caso o
    # protagonista vire alvo nesta rodada. A janela ainda é validada pelo motor.
    reaction_card_id: str | None = None


# ==========================================================================
# Resolução de um turno
# ==========================================================================
def resolve_turn(
    scene: dict,
    actors_by_id: dict[str, dict],
    declaration,
    *,
    state: dict | None = None,
    rng=None,
    sides: dict[str, list[str]] | None = None,
) -> dict:
    """Resolve um turno inteiro. `actors_by_id` mapeia participant_id → ficha
    (player/inimigo/aliado). `state` (opcional) leva o jogador p/ a economia de
    Cartas. `sides` (opcional) define hostilidade para validar alvo (SPEC-232
    R5); sem ele, o lado é inferido da ficha. Retorna {logs, attacks, deaths, terminal}."""
    rng = rng or random.Random()
    decl = (
        declaration if isinstance(declaration, TurnDeclaration) else TurnDeclaration(**declaration)
    )
    actor = actors_by_id.get(decl.actor_id)
    if not actor:
        return {
            "ok": False,
            "logs": [f"Ator '{decl.actor_id}' fora da cena."],
            "attacks": [],
            "deaths": [],
            "terminal": [],
        }

    cs.reset_turn_budget(scene, decl.actor_id)
    out = {"ok": True, "logs": [], "attacks": [], "deaths": [], "terminal": [], "cards_used": []}
    for slot in (decl.pre_acao, decl.acao, decl.pos_acao):
        if slot is None:
            continue
        _resolve_step(
            scene, actor, decl.actor_id, actors_by_id, slot, out, state=state, rng=rng, sides=sides
        )
    return out


def _resolve_step(scene, actor, actor_id, actors_by_id, step, out, *, state, rng, sides=None):
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

            orchestrator.apply_effect_spec(scene, actors_by_id, r["effect"], out, rng=rng)
        return
    if kind == "item":
        _resolve_inventory_item(actor, actors_by_id, step, out)
        return
    if kind in ("attack", "card"):
        _resolve_attack_step(
            scene, actor, actor_id, actors_by_id, step, out, state=state, rng=rng, sides=sides
        )


def _resolve_inventory_item(actor, actors_by_id, step, out):
    """Usa consumível do inventário como Ação. O inventário continua sendo um
    sistema reaproveitado no conflito v2; cura passa a operar sobre Vitalidade
    quando a ficha já está no schema v4."""
    import inventory

    target = actors_by_id.get(step.target_id) if step.target_id else None
    updated, logs = inventory.use_item_in_combat(
        actor, step.item_id or step.object_id or "", target=target
    )
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
        # SPEC-325 R14: o estado "alguém escondido de mim" vale ANTES da busca (que o limpa).
        someone_hidden = _someone_hidden_from(scene, actor_id)
        r = cs.search(scene, actor_id, step.target_id)
        out["logs"].append(r.get("log") or r.get("error", ""))
        if not someone_hidden:
            _search_discovers_object(scene, actor_id, out)
        return
    else:
        r = {"ok": False, "error": f"Manobra desconhecida: {m}.", "log": ""}
    out["logs"].append(r.get("log") or r.get("error", ""))


def _someone_hidden_from(scene: dict, actor_id: str) -> bool:
    return any(
        actor_id in (p.get("hidden_from") or []) or actor_id in (p.get("approx_from") or [])
        for p in (scene.get("positions") or {}).values()
        if isinstance(p, dict)
    )


def _search_discovers_object(scene: dict, actor_id: str, out: dict) -> None:
    """SPEC-325 R14: `procurar` sem participante escondido do ator revela o 1o objeto
    secreto da zona dele. `shadow` so registra; `off` nao faz nada."""
    mode = combat_flags.mode("objects")
    if mode == "off":
        return
    positions = scene.get("positions") or {}
    zone = (positions.get(actor_id) or {}).get("zone_id")
    secret = next(
        (
            o
            for o in scene.get("objects") or []
            if o.get("secret")
            and not o.get("discovered")
            and not o.get("destroyed")
            and o.get("zone_id") in (None, zone)
        ),
        None,
    )
    if secret is None:
        return
    if mode == "shadow":
        from observability.telemetry import log_event

        log_event("combat", "objects_shadow", action="discover")
        return
    found = cs.discover_object(scene, str(secret.get("id")))
    out["logs"].append(found.get("log") or found.get("error", ""))


def _virtude_key(card: dict | None, step, actor: dict) -> str:
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
    "dot",
    "aplicar_condicao",
    "empurrao",
    "taunt",
    "marca",
}
_SUPPORT_EFFECTS = {
    "cura",
    "estabilizar",
    "protecao",
    "reposicionar",
    "esconder",
    "purga_condicao",
    "vantagem",
    "buff_defesa",
    "buff_acerto",
    "buff_dano",
    "reduzir_carga_aliado",
}


def _damage_from(card: dict | None, actor: dict, step) -> tuple:
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


def _side_of(actor_id: str, sides) -> str | None:
    """Lado declarado pelo orquestrador; None quando o chamador não informou
    `sides` (motor puro/testes) — aí a hostilidade não é inferida."""
    if not sides:
        return None
    if actor_id in set(sides.get("hero", [])) | set(sides.get("ally", [])):
        return "hero"
    if actor_id in set(sides.get("enemy", [])):
        return "enemy"
    return None


def _same_side(a_id: str, b_id: str, sides) -> bool | None:
    a, b = _side_of(a_id, sides), _side_of(b_id, sides)
    if a is None or b is None:
        return None
    return a == b


def _targetable(target: dict | None) -> bool:
    if not target:
        return False
    if target.get("dead") or target.get("fled") or target.get("surrendered"):
        return False
    return str(target.get("status", "ativo")) not in (
        "morto",
        "fugiu",
        "rendido",
        "incapacitado",  # SPEC-325 R9
    )


def _invalid_target_reason(
    scene, actor, actor_id, actors_by_id, step, *, support, sides
) -> str | None:
    """SPEC-232 R5: valida o alvo ANTES de qualquer custo. Ofensiva: vivo,
    hostil, não o próprio ator, mirável. Suporte: vivo e do mesmo lado (ou o
    próprio ator quando sem alvo)."""
    if support:
        if not step.target_id or step.target_id == actor_id:
            return None
        target = actors_by_id.get(step.target_id)
        if target is None:
            return "Alvo de suporte fora da cena."
        if target.get("dead") or str(target.get("status", "")) == "morto":
            return "Alvo de suporte já caiu."
        if _same_side(step.target_id, actor_id, sides) is False:
            return f"{target.get('name', step.target_id)} é hostil — Carta de suporte recusada."
        return None
    target = actors_by_id.get(step.target_id)
    if not target or step.target_id == actor_id:
        return "Ataque sem alvo válido."
    if not _targetable(target):
        return f"{target.get('name', step.target_id)} já está fora do conflito."
    if _same_side(step.target_id, actor_id, sides) is True:
        return f"{target.get('name', step.target_id)} é aliado — ataque recusado."
    if scene.get("positions", {}).get(actor_id):
        occ = cs.occlusion_attack_modifier(scene, actor_id, step.target_id)
        if not occ["can_target"]:
            return f"{step.target_id} sem posição conhecida — não pode mirar direto."
    return None


def _is_melee(card: dict | None, step) -> bool:
    """Ataque corpo a corpo: básico (sem Carta) ou Carta ancorada em arma."""
    if step.params.get("ranged"):
        return False
    if card is None:
        return True
    return (card.get("efeito") or {}).get("categoria_arma") in _DANO_BASE_ARMA


def _fire_triggered_passive(actor, trigger: str, out) -> list[dict]:
    """Dispara passivas de gatilho (tier 7/8) do JOGADOR: cobra custo/frequência
    da Carta via `cards.use_passive`; só devolve as que pagaram."""
    if not actor.get("is_player"):
        return []
    from services import cards

    fired = []
    for pe in cm.triggered_passives(actor, trigger):
        res = cards.use_passive(actor, pe["source_card"])
        if res.get("ok"):
            out["logs"].append(res["log"])
            out.setdefault("passives_fired", []).append(pe["source_card"])
            fired.append(pe)
    return fired


def _resolve_attack_step(
    scene, actor, actor_id, actors_by_id, step, out, *, state, rng, sides=None
):
    card = None
    effect_kind = "dano"
    ruptura = bool(step.params.get("ruptura"))
    if step.card_id:
        from services import cards

        card = cards.effective_card(actor, step.card_id, ruptura=ruptura)
        if not card:
            out["logs"].append(f"Carta '{step.card_id}' desconhecida.")
            return
        if card.get("tipo") != "ativa":
            out["logs"].append(f"{card.get('name', step.card_id)} não é uma Carta ativa.")
            return
        effect_kind = str((card.get("efeito") or {}).get("kind") or "")
        if effect_kind not in _ATTACK_EFFECTS | _SUPPORT_EFFECTS:
            out["logs"].append(f"Efeito de Carta sem resolução de Ação: {effect_kind!r}.")
            return
        is_player_actor = bool(
            actor.get("is_player")
            or actor.get("player")
            or (state is not None and actor is state.get("player"))
        )
        if cm.has_control(actor, "silence"):
            out["logs"].append(f"{actor.get('name', actor_id)} está silenciado — sem Cartas.")
            if is_player_actor:
                return
            card, step.card_id, effect_kind = None, None, "dano"
    if card is not None:
        support = effect_kind in _SUPPORT_EFFECTS
        reason = _invalid_target_reason(
            scene, actor, actor_id, actors_by_id, step, support=support, sides=sides
        )
        if reason and not is_player_actor:
            # SPEC-275 R3: declaração recusada de INIMIGO não é no-op — cai UMA
            # vez em ataque básico no mesmo alvo (nada cobrado); se também for
            # recusado, o bloco abaixo registra a recusa e o turno passa.
            # Telemetria estruturada; a prosa não recebe o motivo técnico.
            out.setdefault("enemy_fallbacks", []).append(
                {
                    "event": "enemy_declaration_fallback",
                    "actor_id": actor_id,
                    "card_id": step.card_id,
                    "reason": reason,
                }
            )
            logger.info("enemy_declaration_fallback actor=%s", actor_id)
            card, step.card_id, effect_kind = None, None, "dano"
        elif reason:
            # SPEC-232 R5: nada foi cobrado — Entropia e frequência intactas.
            out["logs"].append(reason)
            return
        if card is None:
            res = None  # SPEC-275 R3: caiu em ataque básico
        elif is_player_actor:
            res = (
                None
                if state is None
                else (
                    cards.use_ruptura(state, step.card_id)
                    if ruptura
                    else cards.use_card(state, step.card_id)
                )
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
                log = res["log"]
                if not is_player_actor and effect_kind in _SUPPORT_EFFECTS:
                    # SPEC-283 R7: frase narrável em pt-BR (nomes, nunca ids) +
                    # telemetria estruturada fora da prosa.
                    log = _support_use_phrase(actor, actor_id, actors_by_id, step, card)
                    out.setdefault("enemy_support_cards", []).append(
                        {
                            "event": "enemy_support_card",
                            "actor_id": actor_id,
                            "card_id": step.card_id,
                            "target_id": step.target_id or actor_id,
                            "kind": effect_kind,
                        }
                    )
                out["logs"].append(log)
                out["cards_used"].append(
                    {
                        "actor_id": actor_id,
                        "card_id": step.card_id,
                        "card": card,
                        "economy": {
                            "cost": int(res.get("cost", 0) or 0),
                            "base_cost": int(res.get("base_cost", res.get("cost", 0)) or 0),
                            "dependencia_applied": bool(res.get("dependencia_applied")),
                        },
                    }
                )
        if card is not None and effect_kind in _SUPPORT_EFFECTS:
            _resolve_support_card(scene, actor, actor_id, actors_by_id, step, card, out)
            return

    reason = _invalid_target_reason(
        scene, actor, actor_id, actors_by_id, step, support=False, sides=sides
    )
    if reason:
        out["logs"].append(reason)
        return
    target = actors_by_id[step.target_id]

    # Vantagem/Desvantagem por ocultação (R10/R11) + Guarda (R8, conflito-06)
    if scene.get("positions", {}).get(actor_id):
        occ = cs.occlusion_attack_modifier(scene, actor_id, step.target_id)
    else:
        occ = {"can_target": True, "advantage": 0}
    advantage = occ["advantage"]
    advantage += cs.guard_offense_modifier(scene, actor_id)
    advantage += cs.guard_defense_modifier(scene, step.target_id)
    advantage += cs.consume_tactical_attack_modifier(scene, actor_id, step.target_id)
    if cm.has_control(target, "marca"):
        advantage += 1  # SPEC-232: alvo Marcado é atacado com Vantagem
    if _fire_triggered_passive(actor, "on_attack", out):
        advantage += 1  # passiva `vantagem` (1×frequência, custo próprio)
    directed_region = step.params.get("regiao")
    if directed_region is not None and cd.is_valid_hit_region(target, directed_region):
        # Mirar uma parte específica troca precisão por controle da consequência.
        advantage -= 1

    virtue_key = _virtude_key(card, step, actor)
    effective_virtue = virtude_value(actor, virtue_key) + int(actor.get("_env_attack_mod", 0) or 0)
    atk = resolve_attack(
        actor,
        target,
        virtude_key=virtue_key,
        virtude_value_override=effective_virtue,
        advantage=advantage,
        ruptura=ruptura,
        rng=rng,
    )
    atk["actor_id"] = actor_id
    atk["target_id"] = step.target_id
    out["attacks"].append(atk)
    out["logs"].append(
        f"{actor.get('name', actor_id)} → {target.get('name', step.target_id)}: "
        f"{atk['resultado']} (total {atk['total']} vs Esquiva {atk['esquiva_alvo']})."
    )

    if atk["acerto"]:
        positions = scene.get("positions", {})
        if _is_melee(card, step) and positions.get(actor_id) and positions.get(step.target_id):
            # SPEC-232 R8: golpe corpo a corpo que conecta engaja os dois.
            cs.engage(scene, actor_id, step.target_id, spend=False)
        effect = (card or {}).get("efeito") or {}
        effect_kind = str(effect.get("kind") or "dano")
        on_hit = _fire_triggered_passive(actor, "on_hit", out)
        if card is None or effect_kind in _DIRECT_DAMAGE_EFFECTS:
            dmg_base, dtype = _damage_from(card, actor, step)
            if actor_id == "player" or actor.get("is_player"):
                dmg_base += cm.early_game_damage_bonus(int(actor.get("level", 1) or 1))
            # SPEC-232 R1/R2: `damage` de condições e passivas estáticas.
            dmg_base = max(
                0,
                dmg_base
                + int(cm.combat_modifiers(actor).get("damage", 0))
                + cm.damage_type_bonus(actor, dtype),
            )
            dmg_base += sum(
                int(pe.get("value", 0) or 0) for pe in on_hit if pe.get("kind") == "dano"
            )
            dres = cd.resolve_damage_and_wounds(
                target,
                damage_base=dmg_base,
                damage_type=dtype,
                crit_mult=atk["efeito_principal_multiplicador"],
                directed_region=directed_region,
                rng=rng,
            )
            atk["regiao"] = dres["regiao"]
            atk["dano_final"] = int(dres.get("dano_final", 0) or 0)
            if dres.get("resistance_hit") and combat_flags.mode("reveal_resist") != "off":
                atk["resistance_hit"] = dres["resistance_hit"]  # SPEC-325 R8
            out["logs"].append("; ".join(dres["log"]))
            _check_death(target, step.target_id, out)
        else:
            _apply_attack_card_effect(scene, actor, actor_id, target, step.target_id, card, out)
        for pe in on_hit:
            if pe.get("kind") == "aplicar_condicao":
                cond = cm.parse_condition(
                    str(pe.get("condicao") or "exposto"), source=pe.get("source_card", "")
                )
                cond["duration"] = max(1, int(pe.get("duration", 1) or 1))
                out["logs"].append(cm.apply_condition(target, cond))

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
        # SPEC-232 R2: `heal` (buff_cura, bonus_cura_por_estagio) do curandeiro.
        amount = max(0, amount + int(cm.combat_modifiers(actor).get("heal", 0) or 0))
        before = int(target.get("vitalidade", 0) or 0)
        max_v = int(target.get("max_vitalidade", before) or before)
        target["vitalidade"] = min(max_v, before + amount)
        import gamedata

        gamedata.sync_legacy_hp_aliases(target)
        out["logs"].append(
            f"{target.get('name', step.target_id or actor_id)} recupera "
            f"{target['vitalidade'] - before} Vitalidade com {name}."
        )
    elif kind == "estabilizar":
        if target.get("estado_terminal"):
            target["estado_terminal"] = False
            target["dead"] = False
            target["vitalidade"] = max(1, int(target.get("vitalidade", 0) or 0))
            target["scar_pending"] = True
            target["last_stand_pending"] = False
            target["stabilization_attempts"] = 0
            tid = step.target_id if step.target_id in actors_by_id else actor_id
            scars = out.setdefault("scars_pending", [])
            if tid not in scars:
                scars.append(tid)
            out["logs"].append(f"{name} estabiliza {target.get('name', 'o alvo')}.")
        else:
            out["logs"].append(f"{name}: o alvo não está em Estado Terminal.")
    elif kind == "purga_condicao":
        conditions = target.setdefault("active_conditions", [])
        # SPEC-232: purga remove a primeira condição NOCIVA (DoT, controle ou
        # delta negativo) — antes tirava a primeira da lista, inclusive um buff.
        harmful = [
            c
            for c in conditions
            if int(c.get("dot", 0) or 0) > 0 or c.get("control") or int(c.get("delta", 0) or 0) < 0
        ]
        removed = harmful[0] if harmful else None
        if removed is not None:
            conditions.remove(removed)
        out["logs"].append(
            f"{name} remove {removed.get('name', 'uma condição')}."
            if removed
            else f"{name}: nenhuma condição para remover."
        )
    elif kind == "reduzir_carga_aliado":
        _ok, log = cm.reduce_ally_abyss(actor, target, amount)
        out["logs"].append(log)
    elif kind == "esconder":
        result = cs.hide(scene, actor_id, source=name)
        out["logs"].append(result.get("log") or result.get("error", ""))
    elif kind == "reposicionar":
        target_id = step.target_id or actor_id
        direction = step.direction or "afastar"
        result = cs.move_distance(scene, target_id, direction)
        if result.get("ok"):
            # SPEC-283 R7: sem o token técnico `id -> estágio (via)` na prosa.
            closer = direction in ("aproximar", "approach", "closer", "-")
            verb = "se aproxima" if closer else "se afasta"
            where = _DISTANCE_PHRASE.get(str(result.get("distance_state")), "")
            out["logs"].append(f"{target.get('name', target_id)} {verb}{where}.")
        else:
            out["logs"].append(result.get("error", ""))
    else:
        stat = {
            "protecao": "protection",
            "vantagem": "advantage",
            "buff_defesa": "ac",
            "buff_acerto": "attack",
            "buff_dano": "damage",
        }.get(kind, kind)
        condition = {
            "name": name,
            "dot": 0,
            "duration": duration,
            "source": step.card_id,
            "stat": stat,
            "delta": amount,
        }
        out["logs"].append(cm.apply_condition(target, condition))


_DISTANCE_PHRASE = {
    "proximo": " e fica ao alcance",
    "distante": " e fica à distância",
    "separado": " e sai do alcance",
}


def _support_use_phrase(actor, actor_id, actors_by_id, step, card) -> str:
    who = actor.get("name", actor_id)
    name = card.get("name", step.card_id)
    target_id = step.target_id
    if not target_id or target_id == actor_id:
        return f"{who} usa {name}."
    target = actors_by_id.get(target_id) or {}
    return f"{who} usa {name} em {target.get('name', target_id)}."


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
        # SPEC-232 R2: `dot` (buff_dot) do aplicador soma à potência do DoT.
        dot = max(0, amount + int(cm.combat_modifiers(actor).get("dot", 0) or 0))
        out["logs"].append(
            cm.apply_condition(
                target,
                {
                    "name": name,
                    "dot": dot,
                    "duration": duration,
                    "source": card.get("id", name),
                },
            )
        )
    elif kind == "aplicar_condicao":
        raw = str(effect.get("condicao") or name)
        cond = cm.parse_condition(raw, source=card.get("id", name))
        cond["duration"] = duration
        out["logs"].append(cm.apply_condition(target, cond))
    elif kind == "empurrao":
        result = cs.move_distance(scene, target_id, "afastar")
        out["logs"].append(result.get("log") or result.get("error", ""))
    elif kind in ("taunt", "marca"):
        out["logs"].append(
            cm.apply_condition(
                target,
                {
                    "name": name,
                    "dot": 0,
                    "duration": duration,
                    "source": card.get("id", name),
                    "control": kind,
                    "source_actor_id": actor_id,
                    "delta": amount,
                },
            )
        )


def _check_death(target, target_id, out):
    """Fluxo de morte (conflito-07, decisão R6=A): último Crítico → Última Ação →
    Estado Terminal. A estabilização/`death_pending` é decidida FORA do turno pelo
    nó de combate (aqui só marca o gatilho)."""
    if death_flow.should_trigger_last_stand(target):
        death_flow.trigger_last_stand(target)
        if target_id not in out["terminal"]:
            out["terminal"].append(target_id)
        out["logs"].append(f"{target.get('name', target_id)} prepara sua Última Ação.")
