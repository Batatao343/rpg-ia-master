"""SPEC-346 — registro determinístico da rodada e fatos do desfecho (sem LLM).

Com o Baralho `on` a rodada se resolve só por Cartas: a mensagem do turno é o REGISTRO
(quem jogou o quê, em quem, com que resultado), em frases curtas montadas a partir do
resultado estruturado do motor (`out`). A aritmética (dados, Esquiva, resistência) fica
no ``last_mech_log`` e no ``mechanics_trace`` — nunca na frase.

Este módulo é puro: não chama LLM, não muda estado.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from typing import Any

# Linhas internas do motor que NUNCA entram no registro (aritmética, ids, setas).
_ARITH_RE = re.compile(
    r"\d+\s*[×x*]\s*\d+|->|→\s*\d|resist/vuln|Proteção\s*-|Proteção \(|Integridade|Rachadura/Torpor"
    r"|Vitalidade\s+\d|\(Vit\b|\bVit\s+\d|excedente|\btotal\s+\d|vs\s+Esquiva"
)

# Frases já humanas emitidas pelo motor (prefixos/sufixos fechados).
_HUMAN_LINE_RES = tuple(
    re.compile(p)
    for p in (
        r": ganha condição ",
        r" terminou\.$",
        r"cumpre o que o presságio anunciava\.$",
        r" age de novo\.$",
        r" está atordoado e perde o turno\.$",
        r"^O Abismo se aproxima\.$",
        r"desaba sobre a cena\.$",
        # recusas e avisos do motor (já em português claro)
        r"Carta de suporte recusada\.$",
        r"^Alvo de suporte ",
        r"^Ataque sem alvo válido\.$",
        r"já está fora do conflito\.$",
        r"ataque recusado\.$",
        r"não pode mirar direto\.$",
        r"^Pacto do Abismo:",
        r"não está na sua mão|não está preparada|Fôlego insuficiente",
    )
)

_FOLEGO_RE = re.compile(r"^(?:O ferimento abre|Membro Falho|Dor Surda|Cego)", re.IGNORECASE)

_REGION_PT = {
    "cabeca": "cabeça",
    "torso": "torso",
    "braco_esquerdo": "braço esquerdo",
    "braco_direito": "braço direito",
    "perna_esquerda": "perna esquerda",
    "perna_direita": "perna direita",
    "braco": "braço",
    "perna": "perna",
}


def _is_arith(line: str) -> bool:
    return bool(_ARITH_RE.search(line))


def _is_human_line(line: str) -> bool:
    return not _is_arith(line) and any(rx.search(line) for rx in _HUMAN_LINE_RES)


def _names(actors_by_id: dict[str, dict]) -> dict[str, str]:
    names = {
        str(aid): str(a.get("name") or aid)
        for aid, a in actors_by_id.items()
        if isinstance(a, dict)
    }
    names["player"] = "Você"
    for aid, a in actors_by_id.items():
        if isinstance(a, dict) and a.get("is_player"):
            names[str(aid)] = "Você"
    return names


def _region(value: Any) -> str:
    text = str(value or "").strip()
    return _REGION_PT.get(text, text.replace("_", " "))


def _result_phrase(atk: dict) -> str:
    """Resultado em linguagem, sem aritmética: erra / acerta — N de dano, ferimento X na Y."""
    resultado = str(atk.get("resultado") or "")
    if resultado == "erro" or not atk.get("acerto"):
        return "erra"
    head = {"critico": "acerto crítico", "supercritico": "acerto supercrítico"}.get(
        resultado, "acerta"
    )
    dano = atk.get("dano_final")
    if dano is None:
        return head
    parts = [f"{head} — {int(dano)} de dano"]
    fer = atk.get("ferimento") or {}
    if fer.get("categoria"):
        parts.append(f"ferimento {fer['categoria']} na região {_region(fer.get('regiao'))}")
    return ", ".join(parts)


def _card(card_id: str | None) -> dict | None:
    if not card_id:
        return None
    try:
        from services import cards

        return cards.get_card(str(card_id))
    except Exception:  # silent-ok: nome da Carta é cosmético; sem ele cai no ataque simples
        return None


def _sabor(card: dict | None) -> str:
    text = str((card or {}).get("descricao") or "").strip()
    return text.rstrip(".!? ")


def _is_hero_side(actor_id: str, actors_by_id: dict[str, dict]) -> bool:
    actor = actors_by_id.get(actor_id) or {}
    return bool(actor.get("is_player") or actor.get("is_ally") or actor_id == "player")


def _attack_line(atk: dict, names: dict[str, str], actors_by_id: dict[str, dict]) -> str:
    actor_id = str(atk.get("actor_id"))
    who = names.get(actor_id, "Alguém")
    target = names.get(str(atk.get("target_id")), "Alguém")
    card = _card(atk.get("card_id"))
    result = _result_phrase(atk)
    if atk.get("label") == "Última Ação":
        return f"{who} executa a Última Ação em {target}: {result}."
    if card is not None and _is_hero_side(actor_id, actors_by_id):
        sabor = _sabor(card)
        sabor_txt = f": {sabor}." if sabor else "."
        return f"{who} joga {card['name']} em {target}{sabor_txt} {result[0].upper()}{result[1:]}."
    if card is not None:
        return f"{who} ataca {target} com {card['name']}: {result}."
    weapon = _weapon_name(actors_by_id.get(actor_id) or {})
    com = f" com {weapon}" if weapon else ""
    return f"{who} ataca {target}{com}: {result}."


def _weapon_name(actor: dict) -> str:
    eq = actor.get("equipment") or {}
    weapon = eq.get("weapon") if isinstance(eq, dict) else None
    if isinstance(weapon, dict):
        weapon = weapon.get("name")
    return str(weapon or "").strip()


def round_registry(
    out: dict,
    actors_by_id: dict[str, dict],
    status_logs: Iterable[str] | None = None,
    extra_lines: Iterable[str] | None = None,
) -> list[str]:
    """R4/R5: frases curtas por evento, na ordem jogadas do herói/aliados, inimigos, DoT e
    condições, quedas e Última Ação, Cartas de Cena e de status."""
    names = _names(actors_by_id)
    attacks = [a for a in (out.get("attacks") or []) if a.get("label") != "Última Ação"]
    hero_lines: list[str] = []
    enemy_lines: list[str] = []
    attacked: set[tuple[str, str]] = set()
    for atk in attacks:
        line = _attack_line(atk, names, actors_by_id)
        (
            hero_lines if _is_hero_side(str(atk.get("actor_id")), actors_by_id) else enemy_lines
        ).append(line)
        if atk.get("card_id"):
            attacked.add((str(atk.get("actor_id")), str(atk.get("card_id"))))
    # Cartas de apoio (cura, proteção...) não geram ataque: uma frase com o sabor.
    for used in out.get("cards_used") or []:
        key = (str(used.get("actor_id")), str(used.get("card_id")))
        if key in attacked:
            continue
        card = used.get("card") or _card(used.get("card_id"))
        if not card:
            continue
        who = names.get(str(used.get("actor_id")), "Alguém")
        sabor = _sabor(card)
        line = f"{who} joga {card.get('name')}" + (f": {sabor}." if sabor else ".")
        (
            hero_lines if _is_hero_side(str(used.get("actor_id")), actors_by_id) else enemy_lines
        ).append(line)

    dot_lines: list[str] = []
    for tick in out.get("ticks") or []:
        victim = names.get(str(tick.get("actor_id")), str(tick.get("actor_id") or "Alguém"))
        dot_lines.append(
            f"{tick.get('condition')} corrói {victim}: {int(tick.get('dano_final', 0))} de dano contínuo."
        )
    for line in out.get("logs") or []:
        if _is_human_line(str(line)) and str(line) not in dot_lines:
            dot_lines.append(str(line))

    for line in extra_lines or []:  # fuga, ordens a companheiros, clima: já humanas
        line = str(line or "").strip()
        if line and not _is_arith(line) and line not in dot_lines:
            dot_lines.append(line)

    fall_lines: list[str] = []
    for aid in out.get("deaths") or []:
        if aid != "player" and not (actors_by_id.get(aid) or {}).get("is_player"):
            fall_lines.append(f"{names.get(str(aid), 'Alguém')} morre.")
    for aid in out.get("terminal") or []:
        if aid != "player" and aid not in (out.get("deaths") or []):
            fall_lines.append(f"{names.get(str(aid), 'Alguém')} cai, à beira da morte.")
    for atk in out.get("attacks") or []:
        if atk.get("label") == "Última Ação":
            fall_lines.append(_attack_line(atk, names, actors_by_id))

    scene_lines = [str(x) for x in out.get("scene_logs") or [] if x and not _is_arith(str(x))]
    status = [str(x) for x in (status_logs or []) if x and not _is_arith(str(x))]

    seen: set[str] = set()
    result: list[str] = []
    for line in [*hero_lines, *enemy_lines, *dot_lines, *fall_lines, *scene_lines, *status]:
        line = line.strip()
        if line and line not in seen:
            seen.add(line)
            result.append(line)
    return result


# ---------------------------------------------------------------------------
# Desfecho (R11-R15)
# ---------------------------------------------------------------------------
_STATE_LABEL = (
    (lambda a: bool(a.get("dead")) or a.get("status") == "morto", "morto"),
    (lambda a: a.get("post_combat_state") == "inconsciente", "inconsciente"),
    (lambda a: bool(a.get("incapacitated")) or not a.get("conscious", True), "caído"),
)


def qualitative_state(actor: dict) -> str:
    """Estado sem números: ileso / ferido / à beira do colapso / caído / inconsciente / morto."""
    for test, label in _STATE_LABEL:
        if test(actor):
            return label
    vit = int(actor.get("vitalidade", actor.get("hp", 0)) or 0)
    mx = int(actor.get("max_vitalidade", actor.get("max_hp", 0)) or 0)
    if mx <= 0 or vit >= mx:
        return "ileso"
    if vit * 4 <= mx:
        return "à beira do colapso"
    return "ferido"


def _wound_phrases(player: dict) -> list[str]:
    fer = player.get("ferimentos") or {}
    out = []
    for cat in ("critico", "grave", "leve"):
        for w in fer.get(cat, []) or []:
            out.append(f"ferimento {cat} na região {_region(w.get('regiao'))}")
    return out


_OUTCOME_PT = {
    "victory": "vitória",
    "fled": "fuga",
    "death": "o herói tombou",
    "defeat": "derrota",
    "surrendered_enemy": "o inimigo se rendeu",
    "expired": "os inimigos perderam o rastro",
    "incapacitated": "o herói perdeu os sentidos",
}


def outcome_facts(
    outcome: str,
    conflict_summary: dict,
    player: dict,
    enemies: list[dict],
    last_out: dict | None = None,
    decisive_cards: list[str] | None = None,
) -> list[str]:
    """R12/R14: fatos em linguagem, SEM nenhum dígito, para o resumo final."""
    last_out = last_out or {}
    facts = [f"Desfecho: {_OUTCOME_PT.get(outcome, outcome)}."]
    summ = conflict_summary or {}
    for key, verb in (
        ("mortos", "morreu"),
        ("caidos", "caiu"),
        ("inconscientes", "perdeu os sentidos"),
        ("rendidos", "se rendeu"),
        ("fugitivos", "fugiu"),
        ("capturados", "foi capturado"),
    ):
        names = [str(n) for n in summ.get(key) or [] if str(n) and str(n) != player.get("name")]
        if names:
            facts.append(f"{', '.join(names)} {verb}.")
    weapon = _weapon_name(player)
    if weapon:
        facts.append(f"Arma do herói: {weapon}.")
    cards = [c for c in (decisive_cards or []) if c]
    if cards:
        facts.append(f"Cartas decisivas: {', '.join(cards)}.")
    wounds = _wound_phrases(player)
    facts.append(
        f"Herói: {qualitative_state(player)}" + (f" ({'; '.join(wounds)})." if wounds else ".")
    )
    for e in enemies:
        if e.get("status") == "ativo" and not e.get("dead"):
            facts.append(f"{e.get('name')}: {qualitative_state(e)}.")
    # R14: o que NÃO aconteceu e o jogador poderia confundir.
    dots = {str(t.get("actor_id")): t for t in last_out.get("ticks") or []}
    for atk in last_out.get("attacks") or []:
        if str(atk.get("target_id")) == "player" and not atk.get("acerto") and dots.get("player"):
            actor = next((e for e in enemies if str(e.get("id")) == str(atk.get("actor_id"))), None)
            if actor:
                facts.append(
                    f"O último golpe de {actor.get('name')} errou; o dano veio de "
                    f"{dots['player'].get('condition')}."
                )
                break
    text = "\n".join(facts)
    return [_no_digits(f) for f in facts] if re.search(r"\d", text) else facts


def _no_digits(text: str) -> str:
    """Tira números junto com o espaço que os precede; sem espaço duplo nem vírgula órfã."""
    value = re.sub(r"\s*\d+", "", text)
    value = re.sub(r"[ 	]{2,}", " ", value)
    value = re.sub(r"\s+([,.;!?])", r"", value)
    value = re.sub(r",\s*,", ",", value)
    return value.strip()


def decisive_cards(last_out: dict, limit: int = 2) -> list[str]:
    """Nomes das Cartas do golpe final e as que mais causaram dano do herói na rodada."""
    totals: dict[str, int] = {}
    for atk in last_out.get("attacks") or []:
        if str(atk.get("actor_id")) == "player" and atk.get("card_id"):
            totals[str(atk["card_id"])] = totals.get(str(atk["card_id"]), 0) + int(
                atk.get("dano_final") or 0
            )
    ranked = sorted(totals, key=lambda c: (-totals[c], c))[:limit]
    return [str((_card(c) or {}).get("name") or c) for c in ranked]


def deterministic_outcome_text(outcome: str, conflict_summary: dict, player: dict) -> str:
    """R15: parágrafo legível montado em Python (nunca bullets, ⚔️, ids nem números)."""
    from services.conflict_summary import player_summary_text

    lead = {
        "victory": "O campo silencia. A luta acabou, e você segue em pé.",
        "fled": "Você rompe o cerco e some na distância; os inimigos perdem o seu rastro.",
        "death": "Você tomba.",
        "defeat": "A luta termina contra você.",
        "surrendered_enemy": "Os inimigos largam as armas; a luta termina.",
        "expired": "Os inimigos perdem o seu rastro e o confronto se desfaz.",
        "incapacitated": "A escuridão fecha sobre você: os sentidos se apagam.",
    }.get(outcome, "A luta termina.")
    parts = [lead]
    body = player_summary_text(conflict_summary or {})
    if body:
        parts.append(body)
    wounds = _wound_phrases(player)
    if wounds and outcome != "fled":
        parts.append("Você carrega " + ", ".join(wounds[:3]) + ".")
    text = " ".join(parts)
    return _no_digits(text)


WHEEL_TEXT = (
    "A escuridão te engole — mas a Roda do Abismo ainda não decidiu. "
    "Voltar ao último respiro seguro, ou aceitar o fim aqui?"
)
