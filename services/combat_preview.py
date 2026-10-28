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
import random
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


def effective_damage_base(
    player: dict, card: dict | None, target: dict | None = None
) -> tuple[int, str, list[str]]:
    """SPEC-353 R18: o dano-base EFETIVO de uma jogada (Carta + herói iniciante + modificadores),
    a MESMA conta da prévia e do motor. Devolve ``(base, tipo, partes)``; ``partes`` explica a
    origem em linguagem ("3 da Carta", "+2 de herói iniciante", "+2 de bônus"). Sem defesa do alvo."""
    step = ct.TurnStep(kind="card" if card else "attack", card_id=(card or {}).get("id"))
    if _uses_formula(card, player):
        base, dtype = ct._damage_from(
            card and {**card, "efeito": {**(card.get("efeito") or {}), "formula": None}},
            {k: v for k, v in player.items() if k != "attack_formula"},
            step,
        )
    else:
        base, dtype = ct._damage_from(card, player, step)  # MESMO caminho do motor
    carta = base
    early = cm.early_game_damage_bonus(int(player.get("level", 1) or 1))
    mods = int(cm.combat_modifiers(player).get("damage", 0)) + cm.damage_type_bonus(player, dtype)
    total = max(0, base + early + mods)
    partes = [f"{carta} da Carta"]
    if early:
        partes.append(f"{early:+d} de herói iniciante")
    if mods:
        partes.append(f"{mods:+d} de bônus")
    return total, dtype, partes


def _after_public_defense(target: dict, dtype: str, raw: int) -> int | None:
    """Dano que sobra depois da defesa PÚBLICA do alvo (armadura visível + condições visíveis),
    rodando o próprio ``resolve_damage_and_wounds`` numa cópia sem nada oculto (resistências,
    imunidades, ``resist_tipos``, escudo). ``None`` = sem defesa pública conhecida."""
    from services import conflict_damage as cd

    armor = target.get("armor") or {}
    cond_prot = int(cm.combat_modifiers(target).get("protection", 0) or 0)
    if not armor and not cond_prot:
        return None
    if dtype not in gamedata.DANO_FISICO and not cond_prot:
        return None  # `resist_tipos` da armadura é oculto: não dá para saber se absorve
    public_armor = {
        k: armor[k]
        for k in ("protecao", "integridade_atual", "integridade_max", "reducoes_max")
        if k in armor
    }
    if public_armor and int(armor.get("integridade_atual", 1) or 0) <= 0:
        public_armor["comprometida"] = True
    ghost = {
        "id": "preview",
        "vitalidade": 10**6,
        "max_vitalidade": 10**6,
        "virtudes": {"corpo": 5},
        "ferimentos": {"leve": [], "grave": [], "critico": []},
        "active_conditions": copy.deepcopy(target.get("active_conditions") or []),
        "armor": public_armor,
    }
    res = cd.resolve_damage_and_wounds(
        ghost, damage_base=raw, damage_type=dtype, crit_mult=1, rng=random.Random(0)
    )
    return int(res.get("dano_final", raw) or 0)


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
        base, dtype, _partes = effective_damage_base(player, card)  # SPEC-353 R18: uma conta só
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
    # SPEC-353 R19: a Proteção PÚBLICA, calculada pelo MESMO pipeline de dano do motor.
    after_min = after_max = defesa = None
    if direct:
        after_min = _after_public_defense(target, dtype, dano_min)
        after_max = _after_public_defense(target, dtype, dano_max)
        if after_min is not None:
            defesa = max(0, dano_min - after_min)
    result = {
        "chance_acerto_pct": round(p_hit * 100, 1),
        "chance_critico_pct": round((dist["critico"] + dist["supercritico"]) * 100, 1),
        "dano_min": dano_min,
        "dano_max": dano_max,
        "ferimento_provavel": ferimento,
        "efeitos_extra": efeitos,
        "pressagio_frustrado": frustra,
        "aproximado": aproximado,
        "defesa_conhecida": defesa,
    }
    if defesa is not None and after_min is not None and after_max is not None:
        result["dano_min_apos_defesa"] = after_min
        result["dano_max_apos_defesa"] = after_max
    return result


_RESULT_LABEL = {
    "erro": "erro",
    "acerto": "acerto",
    "critico": "crítico",
    "supercritico": "supercrítico",
}


def chrono_events(out: dict) -> list[tuple[str, Any]]:
    """SPEC-353 R12: UMA ordem cronológica para registro, ``mech_log`` e ``round_board``.

    ``turn_spans`` manda: tick de DoT no início do turno de quem sofre, reações/oportunidades na
    posição em que ocorreram, custo (auto-dano) junto da Carta que o causou. Eventos fora de turno
    (Última Ação), DoT sem turno e custos soltos vêm por último. Sem ``turn_spans`` (save antigo):
    a ordem de antes (ataques, depois ticks)."""
    attacks = list(out.get("attacks") or [])
    used = list(out.get("cards_used") or [])
    ticks = list(out.get("ticks") or [])
    custos = [
        m
        for m in (out.get("class_mechanics") or [])
        if m.get("kind") == "self_harm" and m.get("actor_id")
    ]
    events: list[tuple[str, Any]] = []
    spans = out.get("turn_spans")
    if not spans:
        events += [("attack", (a, bool(a.get("fora_de_turno")))) for a in attacks]
        events += [("tick", t) for t in ticks]
        events += [("custo", m) for m in custos]
        return events
    covered: set[int] = set()

    def take_custo(actor_id: str, card_id: Any) -> list[tuple[str, Any]]:
        got = [
            ("custo", m)
            for m in custos
            if str(m.get("actor_id")) == actor_id and str(m.get("card_id")) == str(card_id)
        ]
        for _, m in got:
            custos.remove(m)
        return got

    for span in spans:
        if span.get("negado"):
            continue
        actor_id = str(span.get("actor_id"))
        for tick in [t for t in ticks if str(t.get("actor_id")) == actor_id]:
            ticks.remove(tick)
            events.append(("tick", tick))
        a0, a1 = span["attacks"]
        c0, c1 = span["cards"]
        span_attacks = [(i, attacks[i]) for i in range(a0, min(a1, len(attacks)))]
        covered.update(i for i, _ in span_attacks)
        span_cards = list(range(c0, min(c1, len(used))))
        matched: dict[int, int] = {}
        for j in span_cards:
            m = next(
                (
                    i
                    for i, atk in span_attacks
                    if i not in matched
                    and not atk.get("fora_de_turno")
                    and str(atk.get("card_id")) == str(used[j].get("card_id"))
                ),
                None,
            )
            if m is not None:
                matched[m] = j
        done_cards = set(matched.values())
        emitted: set[int] = set()
        for i, atk in span_attacks:
            if i in matched:
                for j in span_cards:
                    if j < matched[i] and j not in done_cards and j not in emitted:
                        emitted.add(j)
                        events.append(("card", used[j]))
                events += take_custo(actor_id, atk.get("card_id"))
                events.append(("attack", (atk, False)))
            else:
                events.append(("attack", (atk, bool(atk.get("fora_de_turno")))))
        for j in span_cards:
            if j not in done_cards and j not in emitted:
                events += take_custo(actor_id, used[j].get("card_id"))
                events.append(("card", used[j]))
    for i, atk in enumerate(attacks):
        if i not in covered:
            events.append(("attack", (atk, bool(atk.get("fora_de_turno")))))
    events += [("tick", t) for t in ticks]
    events += [("custo", m) for m in custos]
    return events


def _flee_line(out: dict) -> str | None:
    roll = out.get("fuga")
    if not isinstance(roll, dict) or roll.get("total") is None:
        return None
    verdict = "escapou" if roll.get("sucesso") else "falhou"
    return f"Fuga · total {roll['total']} vs {roll.get('dificuldade')} · {verdict}"


def mech_log(
    attacks: list[dict],
    actors: list[dict],
    ticks: list[dict] | None = None,
    heals: list[dict] | None = None,
    out: dict | None = None,
) -> list[str]:
    """R6: uma linha por ataque da rodada, só com números que o motor já resolveu.
    Ex.: ``Você · Corte Raso → Lobo · 2d10 6 + 7 +2 = 15 vs 12 · acerto · 5 dano``.

    SPEC-346: crítico diz a dupla que o causou (R8), a Última Ação diz o alvo (R9) e cada tick
    de DoT tem linha própria (R7). SPEC-353: com ``out`` a ordem é a cronológica (R12), o custo
    em Vitalidade tem linha (R13), a Proteção que absorveu aparece (R20) e a fuga mostra o dado."""
    names: dict[str, str] = {}
    for a in actors:  # SPEC-345 R6: indexa por id OU nome (aliado de cena pode não ter id)
        key = str(a.get("id") or a.get("name") or ("player" if a.get("is_player") else ""))
        if key and a.get("name"):
            names[key] = str(a["name"])
        if a.get("is_player"):
            names[key] = "Você"
    names["player"] = "Você"

    def attack_line(atk: dict) -> str:
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
            if int(atk.get("absorvido", 0) or 0) > 0:  # SPEC-353 R20
                tail += f" · Proteção −{int(atk['absorvido'])}"
            tail += f" · {int(atk['dano_final'])} dano"
        if atk.get("label") == "Última Ação":
            head = f"Última Ação: {who} → {target}"
            if atk.get("alvo_declarado"):
                head += " (alvo declarado)"
        else:
            what = f" · {card['name']}" if card else ""
            if atk.get(
                "fora_de_turno"
            ):  # SPEC-347 R5.2: reação/oportunidade/contra-ataque ganham rótulo
                what = f" · {atk['fora_de_turno']}"
            head = f"{who}{what} → {target}"
        return (
            f"{head} · {dice} "
            f"{' + '.join(str(k) for k in kept)} {mod:+d} = {atk.get('total')} "
            f"vs {atk.get('esquiva_alvo')} · {tail}"
        )

    def tick_line(tick: dict) -> str:
        victim = names.get(str(tick.get("actor_id")), str(tick.get("actor_id") or "Alguém"))
        dano = int(tick.get("dano_final", 0))
        return f"{tick.get('condition')} → {victim} · dano contínuo · {dano} dano"

    lines: list[str] = []
    base = out or {}
    merged = {
        **base,
        "attacks": attacks,
        "ticks": ticks if ticks is not None else base.get("ticks"),
    }
    for kind, payload in chrono_events(merged):
        if kind == "attack":
            lines.append(attack_line(payload[0]))
        elif kind == "tick":
            lines.append(tick_line(payload))
        elif kind == "custo":
            card = cards.get_card(str(payload.get("card_id") or "")) or {}
            who = names.get(str(payload.get("actor_id")), "Alguém")
            lines.append(
                f"{who} · {card.get('name', 'Carta')} · custo · "
                f"{int(payload.get('amount', 0))} Vitalidade"
            )
        # "card" (apoio sem ataque) não tinha linha de mecânica; a cura vem de ``heals``
    for heal in heals or []:  # R10: cura/ganho de Vitalidade tem linha própria
        who = names.get(str(heal.get("actor_id")), str(heal.get("actor_id") or "Alguém"))
        lines.append(f"{heal.get('card')} → {who} · cura · {int(heal.get('amount', 0))} Vitalidade")
    flee = _flee_line(base)
    if flee:
        lines.append(flee)
    return lines


def store_mech_log(
    meta: dict, out: dict, actors: list[dict], enemy_ids: set[str] | None = None
) -> None:
    """R6: grava o log mecânico da rodada. Só com o Baralho `on` (save `off` fica idêntico)."""
    from services import card_piles

    if card_piles.mode() != "on" or out.get("action_refused"):
        return
    meta["last_mech_log"] = mech_log(
        out.get("attacks") or [], actors, out.get("ticks") or [], out.get("heals") or [], out=out
    )
    meta["last_round_board"] = round_board(
        out, actors, enemy_ids, fontes=meta.get("fontes_condicao")
    )  # SPEC-347 R14.2


# --- SPEC-347 R14: registro estruturado da rodada (só view; nenhum número muda) ---

_EFFECT_TEXT = {
    "cura": "Cura",
    "estabilizar": "Estabiliza",
    "protecao": "Proteção",
    "reposicionar": "Reposiciona",
    "esconder": "Esconde",
    "purga_condicao": "Purga condição",
    "vantagem": "Vantagem",
    "buff_defesa": "Defesa",
    "buff_acerto": "Acerto",
    "buff_dano": "Dano",
}
_RESULT_KEY = {
    "erro": "erro",
    "acerto": "acerto",
    "critico": "critico",
    "supercritico": "supercritico",
}


def _effect_text(card: dict) -> str:
    effect = card.get("efeito") or {}
    kind = str(effect.get("kind") or "")
    if kind == "taunt":  # SPEC-353 R52
        return "Provocado"
    if kind == "aplicar_condicao":
        label = str(effect.get("condicao") or "Condição").replace("_", " ").capitalize()
        dur = int(effect.get("duracao", effect.get("duration", 0)) or 0)
        return f"{label} {dur} rodadas" if dur > 1 else label
    label = _EFFECT_TEXT.get(kind, str(card.get("name") or "Efeito"))
    if kind in ("protecao", "cura", "buff_defesa"):
        return f"+{ct._effect_amount(effect)} {label}"
    return label


def round_board(
    out: dict,
    actors: list[dict],
    enemy_ids: set[str] | None = None,
    fontes: dict | None = None,
) -> list[dict[str, Any]]:
    """Uma entrada por evento da rodada, na ordem cronológica (``chrono_events``, SPEC-353 R12).

    Contrato (SPEC-353 R50-R53): ``tipo`` ∈ jogada | dano_continuo | queda | pressagio | custo.
    Reações/oportunidades (``fora_de_turno``) saem como ``origem="reacao"``; turno negado não gera
    entrada. ``fontes`` = ``combat_meta["fontes_condicao"]`` (vítima → condição → quem aplicou)."""
    names: dict[str, str] = {}
    for a in actors:
        key = str(a.get("id") or a.get("name") or ("player" if a.get("is_player") else ""))
        if key and a.get("name"):
            names[key] = str(a["name"])
    names["player"] = "Você" if "player" not in names else names["player"]
    enemy_ids = enemy_ids or set()
    fontes = fontes or {}
    heals = list(out.get("heals") or [])

    def side(actor_id: str) -> str:
        if actor_id == "player":
            return "heroi"
        return "inimigo" if actor_id in enemy_ids else "aliado"

    def attack_entry(atk: dict, *, reaction: bool) -> dict[str, Any]:
        actor_id, target_id = str(atk.get("actor_id")), str(atk.get("target_id"))
        card = cards.get_card(str(atk.get("card_id") or "")) if atk.get("card_id") else None
        hit = bool(atk.get("acerto"))
        return {
            "tipo": "jogada",
            "ator_id": actor_id,
            "ator_nome": names.get(actor_id, "Alguém"),
            "lado": side(actor_id),
            "carta_id": card["id"] if card else None,
            "carta_nome": card["name"] if card else None,
            "alvo_id": target_id,
            "alvo_nome": names.get(target_id, "Alguém"),
            "origem": "reacao" if reaction else "turno",
            "rotulo": atk.get("fora_de_turno") if reaction else None,
            "resultado": _RESULT_KEY.get(
                str(atk.get("resultado")), "erro" if not hit else "acerto"
            ),
            "dano": int(atk["dano_final"]) if hit and atk.get("dano_final") is not None else None,
            "efeito": None,
        }

    def heal_note(use: dict) -> str | None:
        for h in heals:
            if str(h.get("actor_id")) == str(use.get("actor_id")) and h.get("card") == (
                use.get("card") or {}
            ).get("name"):
                return f"+{int(h.get('amount', 0) or 0)} Vitalidade"
        return None

    def card_entry(use: dict) -> dict[str, Any]:
        actor_id = str(use.get("actor_id"))
        card = use.get("card") or cards.get_card(str(use.get("card_id") or "")) or {}
        return {
            "tipo": "jogada",
            "ator_id": actor_id,
            "ator_nome": names.get(actor_id, "Alguém"),
            "lado": side(actor_id),
            "carta_id": use.get("card_id"),
            "carta_nome": card.get("name"),
            "alvo_id": None,
            "alvo_nome": None,
            "origem": "turno",
            "rotulo": None,
            "resultado": "efeito",
            "dano": None,
            "efeito": heal_note(use) or _effect_text(card),
        }

    def tick_entry(tick: dict) -> dict[str, Any]:
        victim = str(tick.get("actor_id"))
        cond = str(tick.get("condition") or "Condição")
        src = (fontes.get(victim) or {}).get(cond)
        dano = int(tick.get("dano_final", 0) or 0)
        known = bool(src) and str(src) in names
        return {
            "tipo": "dano_continuo",
            "ator_id": str(src) if known else None,
            "ator_nome": names[str(src)] if known else cond,
            "lado": side(str(src)) if known else "efeito",
            "carta_id": None,
            "carta_nome": cond,
            "alvo_id": victim,
            "alvo_nome": names.get(victim, "Alguém"),
            "origem": "turno",
            "rotulo": "Dano contínuo",
            "resultado": "efeito",
            "dano": dano,
            "efeito": f"−{dano} Vitalidade",
        }

    def custo_entry(m: dict) -> dict[str, Any]:
        actor_id = str(m.get("actor_id"))
        card = cards.get_card(str(m.get("card_id") or "")) or {}
        amount = int(m.get("amount", 0) or 0)
        note = m.get("ferimento") or {}
        efeito = f"−{amount} Vitalidade"
        if note.get("categoria"):
            efeito += f", ferimento {note['categoria']}"
        return {
            "tipo": "custo",
            "ator_id": actor_id,
            "ator_nome": names.get(actor_id, "Alguém"),
            "lado": side(actor_id),
            "carta_id": card.get("id"),
            "carta_nome": card.get("name"),
            "alvo_id": actor_id,
            "alvo_nome": names.get(actor_id, "Alguém"),
            "origem": "turno",
            "rotulo": "Custo",
            "resultado": "efeito",
            "dano": amount,
            "efeito": efeito,
        }

    def queda_entry(actor_id: str, frase: str) -> dict[str, Any]:
        return {
            "tipo": "queda",
            "ator_id": actor_id,
            "ator_nome": names.get(actor_id, "Alguém"),
            "lado": side(actor_id),
            "carta_id": None,
            "carta_nome": None,
            "alvo_id": None,
            "alvo_nome": None,
            "origem": "turno",
            "rotulo": None,
            "resultado": "efeito",
            "dano": None,
            "efeito": frase,
        }

    def pressagio_entry(p: dict) -> dict[str, Any]:
        entry = queda_entry(str(p.get("actor_id")), "cumpre o presságio")
        entry["tipo"] = "pressagio"
        return entry

    entries: list[dict[str, Any]] = []
    pressagios = {str(p.get("actor_id")): p for p in (out.get("pressagios_cumpridos") or [])}
    seen_pressagio: set[str] = set()
    for kind, payload in chrono_events(out):
        if kind == "tick":
            entries.append(tick_entry(payload))
        elif kind == "card":
            entries.append(card_entry(payload))
        elif kind == "custo":
            entries.append(custo_entry(payload))
        else:
            atk, reaction = payload
            actor_id = str(atk.get("actor_id"))
            if actor_id in pressagios and actor_id not in seen_pressagio and not reaction:
                seen_pressagio.add(actor_id)
                entries.append(pressagio_entry(pressagios[actor_id]))
            entries.append(attack_entry(atk, reaction=reaction))
    for aid in out.get("deaths") or []:
        entries.append(queda_entry(str(aid), "morre"))
    for aid in out.get("terminal") or []:
        if aid not in (out.get("deaths") or []):
            entries.append(queda_entry(str(aid), "cai, à beira da morte"))
    for item in out.get("sem_vitalidade") or []:
        entries.append(queda_entry(str(item.get("actor_id")), "sem Vitalidade"))
    return entries
