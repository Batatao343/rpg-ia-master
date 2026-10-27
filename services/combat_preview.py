"""SPEC-334 R4: preview determinístico de uma jogada (sem LLM, sem efeito colateral).

A chance de acerto vem da distribuição EXATA do 2d10 (3d10 mantendo 2 com Vantagem/
Desvantagem): enumera todas as combinações de dados passando-as à MESMA
``resolve_attack`` do motor por um ``rng`` roteirizado. Nenhuma ficha é alterada
(tudo roda em cópias). Mostra só o lado do jogador: dano bruto, sem Proteção,
resistência ou imunidade do alvo (regra de ouro — ``public_panel``).
"""

from __future__ import annotations

import copy
import itertools
import re
from typing import Any

import combat_mechanics as cm
import gamedata
from services import card_effects as fx
from services import cards
from services import conflict_scene as cs
from services import conflict_turn as ct
from services.conflict_resolution import resolve_attack, virtude_value

_DICE_RE = re.compile(r"(\d*)d(\d+)([+-]\d+)?")


class _Scripted:
    """RNG que devolve uma sequência fixa de d10 (substitui o ``random`` do motor)."""

    def __init__(self, dice: tuple[int, ...]):
        self._dice = list(dice)

    def randint(self, lo: int, hi: int) -> int:  # noqa: ARG002 - mesma assinatura do random
        return self._dice.pop(0)


def exact_attack_distribution(attacker: dict, target: dict, **kw: Any) -> dict[str, float]:
    """P(erro/acerto/critico/supercritico) exata, via ``resolve_attack`` real."""
    advantage = int(kw.get("advantage", 0) or 0)
    n = 3 if advantage else 2
    counts = {"erro": 0, "acerto": 0, "critico": 0, "supercritico": 0}
    total = 0
    for dice in itertools.product(range(1, 11), repeat=n):
        res = resolve_attack(attacker, target, rng=_Scripted(dice), **kw)
        counts[res["resultado"]] += 1
        total += 1
    return {k: v / total for k, v in counts.items()}


def _base_damage(card: dict | None, actor: dict) -> int:
    """Dano-base FLAT; fórmula legada usa a média arredondada (preview não rola)."""
    ef = (card or {}).get("efeito") or {}
    if ef.get("dano_base") is not None:
        return max(0, int(ef["dano_base"]))
    if ef.get("categoria_arma") in ct._DANO_BASE_ARMA:
        return ct._DANO_BASE_ARMA[ef["categoria_arma"]]
    formula = ef.get("formula") or ((card is None) and actor.get("attack_formula"))
    if formula:
        m = _DICE_RE.fullmatch(str(formula).replace(" ", ""))
        if not m:
            return ct._DANO_BASICO_DEFAULT
        n, faces, bonus = int(m.group(1) or 1), int(m.group(2)), int(m.group(3) or 0)
        return max(0, (n * (faces + 1)) // 2 + bonus)
    base = actor.get("dano_base_arma")
    return max(0, int(base)) if base is not None else ct._DANO_BASICO_DEFAULT


def preview(state: dict, card_id: str | None, target_id: str | None) -> dict:
    """Preview de ``card_id`` (ou ataque básico se ``None``) contra ``target_id``.

    Levanta ``ValueError`` com código estável: ``card_unknown``, ``target_unknown``,
    ``not_offensive``."""
    player = copy.deepcopy(state.get("player") or {})
    player.setdefault("is_player", True)
    card = None
    if card_id:
        card = cards.effective_card(player, card_id)
        if not card:
            raise ValueError("card_unknown")
        kind = str((card.get("efeito") or {}).get("kind") or "")
        if kind not in ct._ATTACK_EFFECTS:
            raise ValueError("not_offensive")
    enemy = next(
        (e for e in state.get("enemies") or [] if str(e.get("id")) == str(target_id)), None
    )
    if enemy is None or not ct._targetable(enemy):
        raise ValueError("target_unknown")
    target = copy.deepcopy(enemy)

    meta = state.get("combat") or {}
    scene = copy.deepcopy(meta.get("scene") or {})
    advantage = 0
    if (scene.get("positions") or {}).get("player"):
        advantage += cs.occlusion_attack_modifier(scene, "player", str(target_id))["advantage"]
    advantage += cs.guard_offense_modifier(scene, "player")
    advantage += cs.guard_defense_modifier(scene, str(target_id))
    if cm.has_control(target, "marca"):
        advantage += 1

    step = ct.TurnStep(kind="card" if card else "attack", card_id=card_id)
    virtude_key = ct._virtude_key(card, step, player)
    vval = virtude_value(player, virtude_key) + int(player.get("_env_attack_mod", 0) or 0)
    dist = exact_attack_distribution(
        player, target, virtude_key=virtude_key, virtude_value_override=vval, advantage=advantage
    )
    p_hit = dist["acerto"] + dist["critico"] + dist["supercritico"]

    dtype = "cortante"
    if card:
        ef = card.get("efeito") or {}
        dtype = ef.get("damage_type") or ef.get("tipo_dano") or dtype
    base = _base_damage(card, player)
    base += cm.early_game_damage_bonus(int(player.get("level", 1) or 1))
    base = max(
        0,
        base
        + int(cm.combat_modifiers(player).get("damage", 0))
        + cm.damage_type_bonus(player, dtype),
    )
    direct = card is None or str((card.get("efeito") or {}).get("kind") or "dano") in (
        ct._DIRECT_DAMAGE_EFFECTS
    )
    dano_min, dano_max = (base, base * 2) if direct else (0, 0)  # acerto .. crítico

    vit = int(target.get("vitalidade", target.get("hp", 0)) or 0)
    ferimento = None
    if direct and dano_min > vit:
        corpo = (target.get("virtudes") or {}).get("corpo", 0)
        ferimento = gamedata.categoria_ferimento(corpo, dano_min - vit)
    efeitos: list[str] = []
    if ferimento and dtype == "cortante":
        efeitos.append("Sangramento")
    if card:
        for kw in fx.keywords(card):
            efeitos.append(kw)

    pressagios = [
        p for p in (meta.get("pressagios_publicos") or []) if p.get("actor_id") == str(target_id)
    ]
    kws = fx.keywords(card) if card else {}
    frustra = bool(pressagios) and bool(kws.get("interromper") or (direct and dano_max >= vit))
    return {
        "chance_acerto_pct": round(p_hit * 100, 1),
        "chance_critico_pct": round((dist["critico"] + dist["supercritico"]) * 100, 1),
        "dano_min": dano_min,
        "dano_max": dano_max,
        "ferimento_provavel": ferimento,
        "efeitos_extra": efeitos,
        "pressagio_frustrado": frustra,
    }


_RESULT_LABEL = {
    "erro": "erro",
    "acerto": "acerto",
    "critico": "crítico",
    "supercritico": "supercrítico",
}


def mech_log(attacks: list[dict], actors: list[dict]) -> list[str]:
    """R6: uma linha por ataque da rodada, só com números que o motor já resolveu.
    Ex.: ``Você · Corte Raso → Lobo · 2d10 13 + 2 = 15 vs 12 · acerto · 5 dano``."""
    names = {
        str(a.get("id") or ("player" if a.get("is_player") else "")): a.get("name") or "?"
        for a in actors
    }
    names["player"] = "Você"
    lines: list[str] = []
    for atk in attacks:
        kept = atk.get("dice_kept") or []
        dice = "3d10" if len(atk.get("dice_rolled") or []) == 3 else "2d10"
        mod = int(atk.get("virtude", 0) or 0) + int(atk.get("modificador", 0) or 0)
        card = cards.get_card(str(atk.get("card_id") or "")) if atk.get("card_id") else None
        who = names.get(str(atk.get("actor_id")), "?")
        what = f" · {card['name']}" if card else ""
        tail = _RESULT_LABEL.get(str(atk.get("resultado")), str(atk.get("resultado")))
        if atk.get("acerto") and atk.get("dano_final") is not None:
            tail += f" · {int(atk['dano_final'])} dano"
        lines.append(
            f"{who}{what} → {names.get(str(atk.get('target_id')), '?')} · {dice} "
            f"{' + '.join(str(k) for k in kept)} {mod:+d} = {atk.get('total')} "
            f"vs {atk.get('esquiva_alvo')} · {tail}"
        )
    return lines
