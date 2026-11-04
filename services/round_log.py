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

from services import card_effects as fx

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
        r": condição .+ renovada$",
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
        # SPEC-387 R18: toda recusa de jogador (cards.use_card / plan_plays / conflict_turn) é legível
        r"não pôde ser jogada\.$|não está no seu baralho\.$|não existe mais\.$",
        r"já foi usada \(|^Entropia insuficiente|só pode ser jogada 1× por rodada\.$",
        r"é um Fardo e não pode ser jogada\.$|^Falta Fôlego para descartar |não pode ser descartada\.$",
        r"não é uma Carta ativa\.$|está silenciado — sem Cartas\.$",
        r" resiste à (?:sua )?provocação(?: de )?",  # SPEC-387: a Provocação que não desvia também se explica
        r", provocado por .+, muda de alvo\.$",  # SPEC-389 R12: o desvio efetivo do Voto
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


_CAT_PT = {"leve": "leve", "grave": "grave", "critico": "crítico", "crítico": "crítico"}
_REGION_PREP = {
    "cabeca": "na cabeça",
    "torso": "no torso",
    "braco_esquerdo": "no braço esquerdo",
    "braco_direito": "no braço direito",
    "perna_esquerda": "na perna esquerda",
    "perna_direita": "na perna direita",
    "braco": "no braço",
    "perna": "na perna",
}


def _cond_name(raw: Any, default: str) -> str:
    """SPEC-363 P2-1: nome legível da condição (glossário), nunca o id nem artigo de gênero fixo."""
    return fx.condition_label(str(raw)) if raw else default


def _cat_pt(value: Any) -> str:
    """SPEC-353 R34: categoria de Ferimento em pt-BR (com acento)."""
    return _CAT_PT.get(str(value or "").strip(), str(value or "").strip())


def _region_phrase(value: Any) -> str:
    """SPEC-353 R34: "no torso / na cabeça / no braço esquerdo" — nunca "na região X"."""
    text = str(value or "").strip()
    return _REGION_PREP.get(text) or f"no {text.replace('_', ' ')}"


def _owned_region(region: Any, target_id: str | None, target_name: str | None) -> str:
    """SPEC-363 R10: a região diz de quem é ("no seu braço" / "no braço do Mímico")."""
    phrase = _region_phrase(region)
    name = (target_name or "").strip()
    if str(target_id) == "player" or name == "Você":
        head, _, rest = phrase.partition(" ")
        return f"{head} {'sua' if head == 'na' else 'seu'} {rest}".strip()
    return f"{phrase} do {name}" if name and name != "Alguém" else phrase


def _result_phrase(atk: dict, target_name: str | None = None) -> str:
    """Resultado em linguagem, sem aritmética: erra / acerta — N de dano, ferimento X na Y."""
    resultado = str(atk.get("resultado") or "")
    if resultado == "erro" or not atk.get("acerto"):
        return "erra"
    head = {"critico": "acerto crítico", "supercritico": "acerto supercrítico"}.get(
        resultado, "acerta"
    )
    try:  # SPEC-353 R29: crítico por dupla com total abaixo da Esquiva diz por quê
        if resultado in ("critico", "supercritico") and int(atk.get("total")) < int(
            atk.get("esquiva_alvo")
        ):
            head += " (dupla nos dados)"
    except (TypeError, ValueError):
        pass  # silent-ok: sem total/Esquiva no registro, o rótulo simples basta
    dano = atk.get("dano_final")
    if dano is None:
        return head
    parts = [f"{head} — {int(dano)} de dano"]
    fer = atk.get("ferimento") or {}
    if fer.get("categoria"):
        where = _owned_region(fer.get("regiao"), atk.get("target_id"), target_name)
        parts.append(f"ferimento {_cat_pt(fer['categoria'])} {where}")
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


def _attack_line(
    atk: dict,
    names: dict[str, str],
    actors_by_id: dict[str, dict],
    reactions: frozenset[str] = frozenset(),
) -> str:
    actor_id = str(atk.get("actor_id"))
    who = names.get(actor_id, "Alguém")
    target = names.get(str(atk.get("target_id")), "Alguém")
    card = _card(atk.get("card_id"))
    result = _result_phrase(atk, target)
    if not atk.get("card_id") and atk.get("fora_de_turno") in reactions:  # SPEC-389 R14
        return f"{who} reage com {atk['fora_de_turno']} em {target}: {result}."
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
        weapon = weapon.get("name") or weapon.get("id")
    text = str(weapon or "").strip()
    if not text:
        return ""
    # SPEC-363 R23: id cru vira o nome do catálogo; id desconhecido vira "a arma".
    from gamedata import ARTIFACTS_DB

    item = ARTIFACTS_DB.get(text)
    if item:
        return str(item.get("name") or text)
    if re.fullmatch(r"[a-z0-9]+(?:_[a-z0-9]+)+", text):
        return "a arma"
    return text


def _cap_cond(name: str) -> str:
    """Nome da condição com a inicial maiúscula; id com "_" vira o rótulo do glossário (SPEC-387 §6.8)."""
    if "_" in name:
        return fx.condition_label(name)
    return name[:1].upper() + name[1:]


def _voce(line: str, hero_name: str) -> str:
    """SPEC-353 R36: linhas do motor falam de "Você", com condição em maiúscula e concordância."""
    hero = (hero_name or "").strip()
    text = line.strip()
    if hero and text.startswith(hero):
        m = re.match(rf"^{re.escape(hero)}: ganha condição (.+?)\.?$", text)
        if m:
            return f"Você ganha a condição {_cap_cond(m.group(1))}."
        m = re.match(rf"^{re.escape(hero)}: condição (.+?) renovada\.?$", text)
        if m:
            return f"Sua condição {_cap_cond(m.group(1))} foi renovada."
        m = re.match(rf"^{re.escape(hero)}: (.+?) terminou\.?$", text)
        if m:
            return f"Sua condição {_cap_cond(m.group(1))} terminou."
        text = "Você" + text[len(hero) :]
    if hero:  # SPEC-390 R1: o desvio do Voto/Provocação fala "você", nunca o nome do herói
        m = re.match(rf"^(.+?), provocado por {re.escape(hero)}, muda de alvo\.$", text)
        if m:
            return f"{m.group(1)}, provocado por você, muda de alvo."
        m = re.match(rf"^(.+?) resiste à provocação de {re.escape(hero)}\.$", text)
        if m:
            return f"{m.group(1)} resiste à sua provocação."
    m = re.match(r"^(.+?): ganha condição (.+?)\.?$", text)
    if m:
        return f"{m.group(1)} ganha a condição {_cap_cond(m.group(2))}."
    m = re.match(r"^(.+?): condição (.+?) renovada\.?$", text)
    if m:
        return f"A condição {_cap_cond(m.group(2))} de {m.group(1)} foi renovada."
    m = re.match(r"^(.+?): (.+?) terminou\.?$", text)  # SPEC-367 R13
    if m:
        return f"A condição {_cap_cond(m.group(2))} de {m.group(1)} terminou."
    return text


def _sem_vitalidade_line(actor: dict, name: str) -> str:
    """SPEC-353 R27/R28: o Padrão/Elite a 0 de Vitalidade segue de pé — explica o porquê."""
    line = f"{name} está sem Vitalidade — cada golpe agora abre Ferimentos."
    try:
        from services import bestiary_knowledge as bk
        from services import death_flow

        corpo = ((bk.public_panel(actor).get("virtudes")) or {}).get("corpo")
        if corpo is not None:
            espacos = int(death_flow._wound_spaces(actor).get("critico", 0) or 0)
            have = len((actor.get("ferimentos") or {}).get("critico", []) or [])
            falta = max(0, espacos - have)
            if falta:
                s = "" if falta == 1 else "s"
                line = line[:-1] + f"; faltam {falta} Ferimento{s} Crítico{s}."
    except Exception:  # silent-ok: o número só aparece se for público; sem ele, a frase base basta
        pass
    return line


_INSTANCE_ID_RE = re.compile(r"\b(?:[a-z]+_)+\d+\b")


def humanize_ids(text: str, actors_by_id: dict[str, dict] | None = None) -> str:
    """SPEC-363 R27: id de instância ("fallback_goblin_1") nunca chega ao jogador; vira o nome."""
    names = _names(actors_by_id or {})

    def sub(match: re.Match) -> str:
        raw = match.group(0)
        if raw in names and names[raw] != raw:
            return names[raw]
        words = [w for w in raw.split("_") if w not in {"fallback", "enemy", "enemigo"}]
        return " ".join(words).capitalize()

    return _INSTANCE_ID_RE.sub(sub, text)


_USA_RE = re.compile(r"^Usa (.+?)(?: \(| —|$)")


def _card_name(card_id: Any) -> str:
    return str((_card(card_id) or {}).get("name") or "") if card_id else ""


def _conditions_after_cards(out: dict, hero_name: str) -> dict[str, list[str]]:
    """SPEC-387 R28: "X ganha a condição Y" entra logo DEPOIS da jogada que a aplicou (e antes do
    ataque seguinte do inimigo). Lido da ordem do próprio `logs` do motor: "Usa <Carta>" abre a
    janela; a linha "ganha condição" seguinte pertence a essa Carta."""
    by_card: dict[str, list[str]] = {}
    current = ""
    for raw in out.get("logs") or []:
        line = str(raw)
        m = _USA_RE.match(line)
        if m:
            current = m.group(1)
        elif current and ": ganha condição " in line and _is_human_line(line):
            by_card.setdefault(current, []).append(_voce(line, hero_name))
    return by_card


def _reaction_names(out: dict) -> frozenset[str]:
    return frozenset(
        n for n in (_card_name(r.get("card_id")) for r in out.get("reactions") or []) if n
    )


def _taunt_lines(out: dict, names: dict[str, str]) -> list[str]:
    """SPEC-353 R39a: a Provocação diz o que faz. SPEC-389 R12: quem já foi desviado/resistiu na
    rodada não ganha a promessa ("próxima intenção"): só o desfecho aparece."""
    settled = {str(d.get("actor_id")) for d in out.get("pressagios_desviados") or []} | {
        str(m.get("actor_id"))
        for m in out.get("class_mechanics") or []
        if m.get("kind") == "special:taunt_resisted"
    }
    lines = []
    for novo in out.get("condicoes_novas") or []:
        if novo.get("control") == "taunt" and str(novo.get("victim_id")) not in settled:
            src = names.get(str(novo.get("source_id")), "alguém")
            alvo = "você" if src == "Você" else src
            victim = names.get(str(novo.get("victim_id")), "Alguém")
            if victim == "Você":  # SPEC-390 R3: sem "a próxima intenção dele" para o herói
                lines.append(f"Você está provocado por {src}.")
                continue
            lines.append(
                f"{victim} está provocado: a próxima intenção dele mira {alvo} (com chance)."
            )
    return lines


def round_registry(
    out: dict,
    actors_by_id: dict[str, dict],
    status_logs: Iterable[str] | None = None,
    extra_lines: Iterable[str] | None = None,
) -> list[str]:
    """R4/R5 + SPEC-353 R12: frases curtas por evento na ordem CRONOLÓGICA da rodada (a mesma do
    ``mech_log`` e do ``round_board``), depois condições do motor, quedas e Última Ação, Cartas de
    Cena e de status."""
    from services.combat_preview import chrono_events

    names = _names(actors_by_id)
    reaction_names = _reaction_names(out)
    hero_name = next(
        (str(a.get("name") or "") for a in actors_by_id.values() if a.get("is_player")), ""
    )
    attacked = {
        (str(a.get("actor_id")), str(a.get("card_id")))
        for a in (out.get("attacks") or [])
        if a.get("card_id") and a.get("label") != "Última Ação"
    }
    event_lines: list[str] = []
    after_card = _conditions_after_cards(out, hero_name)  # SPEC-387 R28
    for kind, payload in chrono_events(out):
        if kind == "attack":
            atk = payload[0]
            if atk.get("label") != "Última Ação":
                event_lines.append(_attack_line(atk, names, actors_by_id, reaction_names))
                event_lines += after_card.pop(_card_name(atk.get("card_id")), [])
        elif kind == "tick":
            victim = names.get(
                str(payload.get("actor_id")), str(payload.get("actor_id") or "Alguém")
            )
            event_lines.append(
                f"{fx.condition_label(str(payload.get('condition')))} corrói {victim}: "
                f"{int(payload.get('dano_final', 0))} de dano contínuo."
            )
        elif kind == "custo":
            card = _card(payload.get("card_id")) or {}
            who = names.get(str(payload.get("actor_id")), "Alguém")
            verbo = "paga" if who == "Você" else "paga"
            line = f"{who} {verbo} {int(payload.get('amount', 0))} de Vitalidade por {card.get('name', 'uma Carta')}"
            note = payload.get("ferimento") or {}
            if note.get("categoria"):
                line += (
                    f", ferimento {_cat_pt(note['categoria'])} "
                    f"{_owned_region(note.get('regiao'), payload.get('actor_id'), who)}"
                )
            event_lines.append(line + ".")
        else:  # "card": Carta de apoio sem ataque (cura, proteção...) — uma frase com o sabor
            used = payload
            key = (str(used.get("actor_id")), str(used.get("card_id")))
            if key in attacked:
                continue
            card = used.get("card") or _card(used.get("card_id"))
            if not card:
                continue
            who = names.get(str(used.get("actor_id")), "Alguém")
            sabor = _sabor(card)
            event_lines.append(f"{who} joga {card.get('name')}" + (f": {sabor}." if sabor else "."))
            event_lines += after_card.pop(str(card.get("name") or ""), [])

    dot_lines: list[str] = []
    dot_lines += _taunt_lines(out, names)
    for fase in (
        out.get("fases") or []
    ):  # SPEC-387 R29: a troca de fase do chefe é visível, 1× por fase
        if fase.get("texto"):
            dot_lines.append(str(fase["texto"]))
    for m in out.get("class_mechanics") or []:
        if m.get("kind") == "special:taunt_resisted":
            dot_lines.append(f"{names.get(str(m.get('actor_id')), 'Alguém')} resiste à Provocação.")
    for line in out.get("logs") or []:
        if _is_human_line(str(line)):
            human = _voce(str(line), hero_name)
            if human not in dot_lines:
                dot_lines.append(human)

    for fr in out.get("pressagios_frustrados") or []:  # SPEC-387: sem Carta (ainda oculta) nem id
        who = names.get(str(fr.get("actor_id")), "Alguém")
        dot_lines.append(f"Presságio frustrado: {who}")
    for line in extra_lines or []:  # fuga, ordens a companheiros, clima: já humanas
        line = str(line or "").strip()
        if line and not _is_arith(line) and line not in dot_lines:
            dot_lines.append(line)

    fall_lines: list[str] = []
    # SPEC-363 R15: a causa fora de turno (Última Ação) vem ANTES da queda que ela provoca.
    for atk in out.get("attacks") or []:
        if atk.get("label") == "Última Ação":
            fall_lines.append(_attack_line(atk, names, actors_by_id, reaction_names))
    for aid in out.get("deaths") or []:
        if aid != "player" and not (actors_by_id.get(aid) or {}).get("is_player"):
            fall_lines.append(f"{names.get(str(aid), 'Alguém')} morre.")
    for aid in out.get("terminal") or []:
        if aid != "player" and aid not in (out.get("deaths") or []):
            fall_lines.append(f"{names.get(str(aid), 'Alguém')} cai, à beira da morte.")
    for item in out.get("sem_vitalidade") or []:
        aid = str(item.get("actor_id"))
        actor = actors_by_id.get(aid) or {}
        if actor and not actor.get("dead") and aid not in (out.get("deaths") or []):
            fall_lines.append(_sem_vitalidade_line(actor, names.get(aid, "Alguém")))

    # SPEC-364 R14/R15: Cartas de Cena e status passam pela mesma voz do jogador antes do dedupe
    scene_lines = [
        _voce(str(x), hero_name) for x in out.get("scene_logs") or [] if x and not _is_arith(str(x))
    ]
    status = [_voce(str(x), hero_name) for x in (status_logs or []) if x and not _is_arith(str(x))]

    seen: set[str] = set()
    result: list[str] = []
    for line in [*event_lines, *dot_lines, *fall_lines, *scene_lines, *status]:
        line = line.strip()
        if line and line not in seen:
            seen.add(line)
            result.append(line)
    return [humanize_ids(line, actors_by_id) for line in _falls_after_cause(result)]


_FALL_LINE_RE = re.compile(r"^(?P<who>.+?) (?:morre|cai, à beira da morte)[.]$")


def _falls_after_cause(lines: list[str]) -> list[str]:
    """SPEC-363 R15: "<X> morre." nunca antes da linha que causou a queda de X."""
    result = list(lines)
    for line in [ln for ln in result if _FALL_LINE_RE.match(ln)]:
        who = _FALL_LINE_RE.match(line).group("who")  # type: ignore[union-attr]
        idx = result.index(line)
        causes = [
            j
            for j, other in enumerate(result)
            if j > idx
            and not _FALL_LINE_RE.match(other)
            and (f" em {who}:" in other or f"corrói {who}" in other)
        ]
        if causes:
            result.insert(max(causes) + 1, result.pop(idx))
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
            out.append(f"ferimento {_cat_pt(cat)} {_region_phrase(w.get('regiao'))}")
    return out


_OUTCOME_PT = {
    "victory": "vitória",
    "fled": "fuga",
    "death": "o herói tombou",
    "defeat": "derrota",
    "surrendered_enemy": "o inimigo se rendeu",
    "expired": "os inimigos perderam o rastro",
    "incapacitated": "o herói perdeu os sentidos",
    "objective_failed": "o objetivo falhou",  # SPEC-387 R20 (o `outcome` salvo segue `defeat`)
}


def objective_reason(last_out: dict | None) -> str:
    """SPEC-387 R20: motivo do motor para o objetivo falho ("" sem objetivo), sem ponto final."""
    return str(((last_out or {}).get("objetivo") or {}).get("motivo") or "").strip().rstrip(".")


def _fact_names(
    player: dict, enemies: list[dict], extra: dict[str, str] | None = None
) -> dict[str, str]:
    names = {"player": "Você"}
    for e in enemies or []:
        for key in (e.get("id"), e.get("name")):
            if key:
                names[str(key)] = str(e.get("name") or key)
    for key, value in (extra or {}).items():
        names.setdefault(str(key), str(value))
    return names


def _event_result(atk: dict, target_name: str | None = None) -> str:
    """Resultado em linguagem, SEM número (R5)."""
    if not atk.get("acerto") or atk.get("resultado") == "erro":
        return "errou"
    head = {"critico": "acerto crítico", "supercritico": "acerto supercrítico"}.get(
        str(atk.get("resultado")), "acertou"
    )
    fer = atk.get("ferimento") or {}
    if fer.get("categoria"):
        where = _owned_region(fer.get("regiao"), atk.get("target_id"), target_name)
        head += f", ferimento {_cat_pt(fer['categoria'])} {where}"
    return head


def authorship(
    last_out: dict | None,
    names: dict[str, str],
    player: dict | None = None,
    conflict_summary: dict | None = None,
) -> dict:
    """SPEC-353 R5-R8: quem fez o quê na rodada final, estruturado.

    ``hero_cards``: nome da Carta/arma do herói → "hit"|"miss"; ``final_by_hero``: o golpe final
    foi do herói?; ``lines``: as linhas de fatos; ``final_lines``: as de golpe final."""
    last_out = last_out or {}
    from services.combat_preview import chrono_events

    lines: list[str] = []
    hero_cards: dict[str, str] = {}
    last_hero_hit: bool | None = None
    for kind, payload in chrono_events(last_out):
        if kind == "attack":
            atk = payload[0]
            actor = str(atk.get("actor_id"))
            who = names.get(actor, "Alguém")
            target = names.get(str(atk.get("target_id")), "Alguém")
            card = _card(atk.get("card_id"))
            hero = actor == "player"
            if atk.get("label") == "Última Ação":
                verb = "executou a Última Ação"
            elif card is not None and hero:
                verb = "jogou"
            else:
                verb = "atacou"
            what = f" {card['name']}" if card and verb != "executou a Última Ação" else ""
            if verb == "executou a Última Ação" and card:
                what = f" com {card['name']}"
            lines.append(f"{who} {verb}{what} em {target}: {_event_result(atk, target)}.")
            if hero:
                last_hero_hit = bool(atk.get("acerto"))
                if card:
                    key = card["name"]
                    hit = bool(atk.get("acerto"))
                    hero_cards[key] = "hit" if (hit or hero_cards.get(key) == "hit") else "miss"
        elif kind == "tick":
            victim = names.get(str(payload.get("actor_id")), "Alguém")
            lines.append(f"{fx.condition_label(str(payload.get('condition')))} corroeu {victim}.")
        elif kind == "custo":
            card = _card(payload.get("card_id")) or {}
            who = names.get(str(payload.get("actor_id")), "Alguém")
            lines.append(f"{who} pagou Vitalidade pelo custo de {card.get('name', 'uma Carta')}.")
    final_lines: list[str] = []
    final_by_hero = False
    final_on_enemy = False
    for blow in last_out.get("final_blows") or []:
        target = names.get(str(blow.get("target_id")), "Alguém")
        by = str(blow.get("by_actor_id") or "")
        card = _card(blow.get("card_id"))
        kind = blow.get("kind")
        if str(blow.get("target_id")) == "player":
            if kind == "dano_continuo":
                final_lines.append(
                    f"Quem derrubou o herói: o dano contínuo de {_cond_name(blow.get('condition'), 'uma condição')}."
                )
            elif kind == "auto_dano":
                final_lines.append("Quem derrubou o herói: o custo em Vitalidade da própria Carta.")
            else:
                final_lines.append(f"Quem derrubou o herói: {names.get(by, 'um inimigo')}.")
            continue
        final_on_enemy = True
        if kind == "dano_continuo":
            final_lines.append(
                f"Golpe final: o {_cond_name(blow.get('condition'), 'dano contínuo')} (dano contínuo) em {target}."
            )
        elif by == "player":
            final_by_hero = True
            final_lines.append(
                f"Golpe final: {card['name'] if card else 'seu ataque'} de Você em {target}."
            )
            if kind == "reacao":  # SPEC-355 R4 / SPEC-363 R38(i): a frase que o resumo deve usar
                final_lines.append(f"Sua reação termina o serviço: {target} tomba.")
        else:
            final_lines.append(
                f"Golpe final: {card['name'] if card else 'o ataque'} de {names.get(by, 'um aliado')} em {target}."
            )
    if final_on_enemy and not final_by_hero and last_hero_hit is False:
        final_lines.append("Seu último golpe errou.")
    hero_info: dict = {}
    if player is not None:  # SPEC-363 R11 (V4): o que o herói de fato sofreu
        regions = [
            str(w.get("regiao") or "")
            for cat in ("critico", "grave", "leve")
            for w in (player.get("ferimentos") or {}).get(cat, []) or []
        ]
        hero_info = {"hero_state": qualitative_state(player), "hero_wound_regions": regions}
    earlier = (
        fall_partition(conflict_summary, last_out, names, str((player or {}).get("name") or ""))[1]
        if conflict_summary
        else []
    )
    return {
        **hero_info,
        "earlier_fallen": earlier,  # SPEC-364 R12 (V6)
        "participant_names": sorted(
            {str(v) for v in names.values() if str(v) and str(v) != "Você"}
        ),
        "lines": lines,
        "final_lines": final_lines,
        "hero_cards": hero_cards,
        "final_by_hero": final_by_hero,
        "final_on_enemy": final_on_enemy,
        "hero_last_missed": last_hero_hit is False,
    }


def fall_partition(
    summary: dict | None, last: dict | None, nm: dict[str, str], hero: str = ""
) -> tuple[set[str], list[str]]:
    """SPEC-364 R10: (nomes que caíram na rodada final, nomes de quedas anteriores).
    Sem dado da rodada final (save antigo) tudo é "agora", como antes."""
    last = last or {}
    now_ids = {str(b.get("target_id")) for b in last.get("final_blows") or []}
    now_ids |= {str(i) for i in last.get("deaths") or []} | {
        str(i) for i in last.get("terminal") or []
    }
    now_ids |= {str(x.get("actor_id")) for x in last.get("sem_vitalidade") or []}
    now_names = {nm.get(i, i) for i in now_ids if i != "player"}
    fallen = [
        n
        for key in ("mortos", "caidos", "inconscientes")
        for n in ((summary or {}).get(key) or [])
        if str(n).strip() and str(n).strip() != hero
    ]
    earlier = [n for n in dict.fromkeys(fallen) if n not in now_names] if now_ids else []
    return now_names, earlier


def outcome_facts(
    outcome: str,
    conflict_summary: dict,
    player: dict,
    enemies: list[dict],
    last_out: dict | None = None,
    decisive_cards: list[str] | None = None,
    names: dict[str, str] | None = None,
) -> list[str]:
    """R12/R14 + SPEC-353 R5/R6: fatos em linguagem, SEM nenhum dígito, para o resumo final.
    As linhas de autoria (quem fez o quê, em quem, com que resultado) substituem as "Cartas
    decisivas" soltas; o golpe final vem explícito."""
    last_out = last_out or {}
    facts = [f"Desfecho: {_OUTCOME_PT.get(outcome, outcome)}."]
    if outcome == "objective_failed" and objective_reason(last_out):
        facts.append(f"Objetivo: {objective_reason(last_out)}.")
    summ = conflict_summary or {}
    nm_all = _fact_names(player, enemies, names)
    now_names, earlier_all = fall_partition(summ, last_out, nm_all, str(player.get("name") or ""))
    for key, verb, past in (
        ("mortos", "morreu", "morrido"),
        ("caidos", "caiu", "caído"),
        ("inconscientes", "perdeu os sentidos", "perdido os sentidos"),
        ("rendidos", "se rendeu", ""),
        ("fugitivos", "fugiu", ""),
        ("capturados", "foi capturado", ""),
    ):
        pnames = [str(n) for n in summ.get(key) or [] if str(n) and str(n) != player.get("name")]
        if not pnames:
            continue
        if past and last_out:  # SPEC-364 R10: a queda anterior fica no passado
            old = [n for n in pnames if n in earlier_all]
            pnames = [n for n in pnames if n not in old]
            if old:
                aux = "já tinha" if len(old) == 1 else "já tinham"
                facts.append(f"Antes do fim, {', '.join(old)} {aux} {past}.")
            if pnames:
                facts.append(f"Na rodada final, {', '.join(pnames)} {verb}.")
        elif pnames:
            facts.append(f"{', '.join(pnames)} {verb}.")
    auth = authorship(last_out, _fact_names(player, enemies, names))
    facts += auth["lines"]
    facts += auth["final_lines"]
    weapon = _weapon_name(player)
    if weapon and weapon != "a arma":
        facts.append(f"Arma do herói: {weapon}.")
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
    protect = _protected_names(player, enemies, names, summ)
    return [_no_digits(f, protect) for f in facts] if re.search(r"\d", text) else facts


def _protected_names(
    player: dict | None,
    enemies: list[dict] | None,
    names: dict[str, str] | None,
    summary: dict | None,
) -> list[str]:
    """SPEC-363 R6: nomes de participantes que podem ter dígito ("Bandido 2", "Smoke3A")."""
    found: list[str] = [str((player or {}).get("name") or "")]
    found += [str(e.get("name") or "") for e in enemies or []]
    found += [str(v) for v in (names or {}).values()]
    for key in (
        "participantes",
        "mortos",
        "caidos",
        "inconscientes",
        "rendidos",
        "fugitivos",
        "capturados",
    ):
        found += [str(v) for v in (summary or {}).get(key) or []]
    return sorted({n.strip() for n in found if re.search(r"\d", n)}, key=len, reverse=True)


def _no_digits(text: str, protect: list[str] | None = None) -> str:
    """Tira números; `protect` (SPEC-363 R6) = nomes com dígito que sobrevivem intactos."""
    held: list[str] = []
    for name in protect or []:
        if name and name in text:
            text = text.replace(name, chr(0xE000 + len(held)))
            held.append(name)
    value = _strip_digits(text)
    for i, name in enumerate(held):
        value = value.replace(chr(0xE000 + i), name)
    return value


def _strip_digits(text: str) -> str:
    """Tira números junto com o espaço que os precede; sem espaço duplo nem vírgula órfã."""
    value = re.sub(r"\s*\d+", "", text)
    value = re.sub(r"[ 	]{2,}", " ", value)
    value = re.sub(r"\s+([,.;!?])", r"\1", value)
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


def final_blow_sentence(last_out: dict | None, names: dict[str, str]) -> str:
    """SPEC-353 R10: a frase do golpe final, sem dígitos, com a autoria certa."""
    for blow in (last_out or {}).get("final_blows") or []:
        tid = str(blow.get("target_id"))
        if tid == "player":
            continue
        target = names.get(tid, "O inimigo")
        by = str(blow.get("by_actor_id") or "")
        if blow.get("kind") == "dano_continuo":
            cond = _cond_name(blow.get("condition"), "dano contínuo")
            return f"{cond[:1].upper()}{cond[1:]} termina o serviço: {target} tomba."
        if by == "player" and blow.get("kind") == "reacao":  # SPEC-355 R4
            return f"Sua reação termina o serviço: {target} tomba."
        if by == "player":
            return f"Seu golpe termina o serviço: {target} tomba."
        who = names.get(by)
        if who:
            return f"{who} termina o serviço: {target} tomba."
    return ""


def deterministic_outcome_text(
    outcome: str,
    conflict_summary: dict,
    player: dict,
    last_out: dict | None = None,
    names: dict[str, str] | None = None,
) -> str:
    """R15: parágrafo legível montado em Python (nunca bullets, ⚔️, ids nem números)."""
    from services.conflict_summary import player_clauses

    nm = {"player": "Você", **(names or {})}
    hero = str((player or {}).get("name") or "").strip()
    summary = conflict_summary or {}
    last = last_out or {}
    # R9: quedas da rodada final (de last_out) vs. quedas anteriores do conflito.
    blow = final_blow_sentence(last, nm)
    blow_targets = {
        nm.get(str(b.get("target_id")), "")
        for b in last.get("final_blows") or []
        if str(b.get("target_id")) != "player"
    }
    _now, earlier = fall_partition(summary, last, nm, hero)
    skip = {hero, *earlier, *(blow_targets if blow else set())}

    lead = {
        "victory": "O campo silencia. A luta acabou, e você segue em pé.",
        "fled": "Você rompe o cerco e some na distância; os inimigos perdem o seu rastro.",
        "death": "Você tomba.",
        "defeat": "A luta termina contra você.",
        "surrendered_enemy": "Os inimigos largam as armas; a luta termina.",
        "expired": "Os inimigos perdem o seu rastro e o confronto se desfaz.",
        "incapacitated": "A escuridão fecha sobre você: os sentidos se apagam.",
    }.get(outcome, "A luta termina.")
    if outcome == "objective_failed":  # SPEC-387 R20: o herói segue de pé
        why = objective_reason(last)
        lead = f"O objetivo se perdeu: {why}. Você segue de pé." if why else "O objetivo se perdeu."
    if outcome == "death":  # R14: quem derrubou o herói (golpe final), não o 1º inimigo
        for b in last.get("final_blows") or []:
            if str(b.get("target_id")) != "player":
                continue
            kind, by = b.get("kind"), str(b.get("by_actor_id") or "")
            if kind == "dano_continuo":
                cond = _cond_name(b.get("condition"), "dano contínuo")
                lead = f"Você tomba, consumido por {cond}."
            elif kind == "auto_dano":
                lead = "Você tomba, vencido pelo preço da própria Carta."
            elif nm.get(by):
                lead = f"Você tomba diante de {nm[by]}."
            break
    parts = [lead]
    body = " ".join(player_clauses(summary, exclude=skip))
    if body:
        parts.append(body)
    if blow:
        parts.append(blow)
    if earlier:
        past = "já tinha tombado" if len(earlier) == 1 else "já tinham tombado"
        old = f"Antes, {_join(earlier)} {past}."
        if len(parts) + 1 <= 4:
            parts.insert(1, old)
    wounds = _wound_phrases(player)
    if wounds and outcome != "fled":
        parts.append("Você carrega " + ", ".join(wounds[:3]) + ".")
    text = " ".join(parts)
    return _no_digits(text, _protected_names(player, None, names, summary))


def _join(names: list[str]) -> str:
    return names[0] if len(names) == 1 else f"{', '.join(names[:-1])} e {names[-1]}"


WHEEL_TEXT = (
    "A escuridão te engole — mas a Roda do Abismo ainda não decidiu. "
    "Voltar ao último respiro seguro, ou aceitar o fim aqui?"
)


_RAW_ID_RE = re.compile(r"\b[a-z]+(?:_[a-z0-9]+)+\b")


def names_hero(text: str, hero_name: str) -> bool:
    """SPEC-387 R33 [D-387-6]: a prosa usou o nome próprio do herói (a voz é "você")."""
    hero = (hero_name or "").strip()
    return bool(hero) and bool(re.search(rf"(?<!\w){re.escape(hero)}(?!\w)", text or ""))
