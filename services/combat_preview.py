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
from typing import Any

import combat_mechanics as cm
import gamedata
from services import bestiary_knowledge as bk
from services import card_effects as fx
from services import cards
from services import conflict_scene as cs
from services import conflict_turn as ct
from services.conflict_resolution import resolve_attack, virtude_value


class _Scripted:
    """RNG que devolve uma sequência fixa de d10 (substitui o ``random`` do motor)."""

    def __init__(self, dice: tuple[int, ...]):
        self._dice = list(dice)

    def randint(self, lo: int, hi: int) -> int:  # noqa: ARG002 - mesma assinatura do random
        return self._dice.pop(0)


def exact_attack_distribution(attacker: dict, target: dict, **kw: Any) -> dict[str, float]:
    """P(erro/acerto/critico/supercritico) exata, via ``resolve_attack`` real.

    Sempre enumera 3 dados: o motor pode trocar o saldo de Vantagem por dentro (condições do
    atacante, ex.: ``cego``) e o rng roteirizado só consome os dados que o caminho real pede —
    cada desfecho do caminho de 2 dados é contado 10× igual, então a razão segue exata."""
    counts = {"erro": 0, "acerto": 0, "critico": 0, "supercritico": 0}
    total = 0
    for dice in itertools.product(range(1, 11), repeat=3):
        res = resolve_attack(attacker, target, rng=_Scripted(dice), **kw)
        counts[res["resultado"]] += 1
        total += 1
    return {k: v / total for k, v in counts.items()}


def _uses_formula(card: dict | None, actor: dict) -> bool:
    """O dano do motor (``_damage_from``) cairia na via legada que ROLA dados."""
    ef = (card or {}).get("efeito") or {}
    if ef.get("dano_base") is not None or ef.get("categoria_arma") in ct._DANO_BASE_ARMA:
        return False
    return bool(ef.get("formula") or actor.get("attack_formula"))


def preview(state: dict, card_id: str | None, target_id: str | None) -> dict:
    """Preview de ``card_id`` (ou ataque básico se ``None``) contra ``target_id``.

    Levanta ``ValueError`` com código estável: ``card_unknown``, ``card_not_in_hand``,
    ``card_not_active``, ``target_unknown``, ``not_offensive``. ``aproximado`` = há
    modificador que a prévia não resolve (passiva de gatilho, fórmula de dano rolada)."""
    player = copy.deepcopy(state.get("player") or {})
    player.setdefault("is_player", True)
    meta = state.get("combat") or {}
    card = None
    if card_id:
        piles = meta.get("pilhas")
        if isinstance(piles, dict) and card_id not in (piles.get("mao") or []):
            raise ValueError("card_not_in_hand")
        card = cards.effective_card(player, card_id)
        if not card:
            raise ValueError("card_unknown")
        if card.get("tipo") != "ativa":
            raise ValueError("card_not_active")
        kind = str((card.get("efeito") or {}).get("kind") or "")
        if kind not in ct._ATTACK_EFFECTS:
            raise ValueError("not_offensive")
    enemy = next(
        (e for e in state.get("enemies") or [] if str(e.get("id")) == str(target_id)), None
    )
    if enemy is None or not ct._targetable(enemy):
        raise ValueError("target_unknown")
    target = copy.deepcopy(enemy)

    scene = copy.deepcopy(meta.get("scene") or {})  # cópia: o consumo tático não vaza
    advantage = 0
    if (scene.get("positions") or {}).get("player"):
        advantage += cs.occlusion_attack_modifier(scene, "player", str(target_id))["advantage"]
    advantage += cs.guard_offense_modifier(scene, "player")
    advantage += cs.guard_defense_modifier(scene, str(target_id))
    advantage += cs.consume_tactical_attack_modifier(scene, "player", str(target_id))
    if cm.has_control(target, "marca"):
        advantage += 1
    aproximado = bool(cm.triggered_passives(player, "on_attack")) or bool(
        cm.triggered_passives(player, "on_hit")
    )

    step = ct.TurnStep(kind="card" if card else "attack", card_id=card_id)
    virtude_key = ct._virtude_key(card, step, player)
    vval = virtude_value(player, virtude_key) + int(player.get("_env_attack_mod", 0) or 0)
    dist = exact_attack_distribution(
        player, target, virtude_key=virtude_key, virtude_value_override=vval, advantage=advantage
    )
    p_hit = dist["acerto"] + dist["critico"] + dist["supercritico"]

    direct = card is None or str((card.get("efeito") or {}).get("kind") or "dano") in (
        ct._DIRECT_DAMAGE_EFFECTS
    )
    dano_min = dano_max = 0
    dtype = "cortante"
    if direct:
        if _uses_formula(card, player):
            aproximado = True  # `_damage_from` rolaria dados; o preview usa o dano-base padrão
            base, dtype = ct._damage_from(
                card and {**card, "efeito": {**(card.get("efeito") or {}), "formula": None}},
                {k: v for k, v in player.items() if k != "attack_formula"},
                step,
            )
        else:
            base, dtype = ct._damage_from(card, player, step)  # MESMO caminho do motor
        base += cm.early_game_damage_bonus(int(player.get("level", 1) or 1))
        base = max(
            0,
            base
            + int(cm.combat_modifiers(player).get("damage", 0))
            + cm.damage_type_bonus(player, dtype),
        )
        base += fx.consume_marca_abismo(player, target, None)  # cópias; a Marca é pública
        pct = fx.damage_pct(player, "dealt") + fx.damage_pct(target, "taken")

        def _final(mult: int) -> int:
            raw = base * mult
            return fx.apply_pct(raw, pct) if pct and raw > 0 else raw

        dano_min, dano_max = _final(1), _final(2)  # acerto .. crítico, brutos (sem defesa do alvo)

    # Ferimento só com a Virtude `corpo` que o painel público revela; senão, omitido.
    ferimento = None
    corpo = ((bk.public_panel(target).get("virtudes")) or {}).get("corpo")
    vit = int(target.get("vitalidade", target.get("hp", 0)) or 0)
    if direct and corpo is not None and dano_min > vit:
        ferimento = gamedata.categoria_ferimento(corpo, dano_min - vit)
    efeitos: list[str] = []
    if ferimento and dtype == "cortante":
        efeitos.append("Sangramento")
    if card:
        efeitos.extend(fx.keywords(card))

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
        "aproximado": aproximado,
    }


_RESULT_LABEL = {
    "erro": "erro",
    "acerto": "acerto",
    "critico": "crítico",
    "supercritico": "supercrítico",
}


def mech_log(attacks: list[dict], actors: list[dict], ticks: list[dict] | None = None) -> list[str]:
    """R6: uma linha por ataque da rodada, só com números que o motor já resolveu.
    Ex.: ``Você · Corte Raso → Lobo · 2d10 6 + 7 +2 = 15 vs 12 · acerto · 5 dano``.

    SPEC-346: crítico diz a dupla que o causou (R8), a Última Ação diz o alvo (R9) e cada tick
    de DoT tem linha própria (R7)."""
    names: dict[str, str] = {}
    for a in actors:  # SPEC-345 R6: indexa por id OU nome (aliado de cena pode não ter id)
        key = str(a.get("id") or a.get("name") or ("player" if a.get("is_player") else ""))
        if key and a.get("name"):
            names[key] = str(a["name"])
        if a.get("is_player"):
            names[key] = "Você"
    names["player"] = "Você"
    lines: list[str] = []
    for atk in attacks:
        kept = atk.get("dice_kept") or []
        dice = "3d10" if len(atk.get("dice_rolled") or []) == 3 else "2d10"
        mod = int(atk.get("virtude", 0) or 0) + int(atk.get("modificador", 0) or 0)
        card = cards.get_card(str(atk.get("card_id") or "")) if atk.get("card_id") else None
        who = names.get(str(atk.get("actor_id")), "Alguém")
        target = names.get(str(atk.get("target_id")), "Alguém")
        tail = _RESULT_LABEL.get(str(atk.get("resultado")), str(atk.get("resultado")))
        if atk.get("resultado") in ("critico", "supercritico") and len(kept) >= 2:
            if kept[0] == kept[1]:  # R8: a regra de dupla manda, mesmo abaixo da Esquiva
                tail += f" (dupla de {kept[0]})"
        if atk.get("acerto") and atk.get("dano_final") is not None:
            tail += f" · {int(atk['dano_final'])} dano"
        if atk.get("label") == "Última Ação":
            head = f"Última Ação: {who} → {target}"
            if atk.get("alvo_declarado"):
                head += " (alvo declarado)"
        else:
            what = f" · {card['name']}" if card else ""
            head = f"{who}{what} → {target}"
        lines.append(
            f"{head} · {dice} "
            f"{' + '.join(str(k) for k in kept)} {mod:+d} = {atk.get('total')} "
            f"vs {atk.get('esquiva_alvo')} · {tail}"
        )
    for tick in ticks or []:  # R7: o DoT também fecha a conta (inclusive com 0 de dano)
        victim = names.get(str(tick.get("actor_id")), str(tick.get("actor_id") or "Alguém"))
        lines.append(
            f"{tick.get('condition')} → {victim} · dano contínuo · {int(tick.get('dano_final', 0))} dano"
        )
    return lines


def store_mech_log(meta: dict, out: dict, actors: list[dict]) -> None:
    """R6: grava o log mecânico da rodada. Só com o Baralho `on` (save `off` fica idêntico)."""
    from services import card_piles

    if card_piles.mode() != "on" or out.get("action_refused"):
        return
    meta["last_mech_log"] = mech_log(out.get("attacks") or [], actors, out.get("ticks") or [])
