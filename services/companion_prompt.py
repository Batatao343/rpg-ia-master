"""SPEC-300 — bloco ``<COMPANHEIROS>`` do prompt (R9–R13). Puro; zero chamadas ao LLM.

O motor (``companion_soul``) decidiu o que aconteceu; este módulo só escolhe QUEM fala e
diz ao narrador/``npc_actor`` o que narrar. Nunca expõe número de aprovação nem nome de
traço oculto — só rótulos e frases de personagem.
"""

from __future__ import annotations

import random
from typing import Literal

from services import companion_soul as cs
from services import companion_tags as ctags

BLOCK_CAP_EACH = 600
BLOCK_CAP_TOTAL = 1200
MAX_CAMP_SPEAKERS = 2
STRONG_DELTA = 4

_QUIET_TAGS = {"aviso", "despedida", "estagio", "resolucao"}

_AXIS_PHRASE: dict[str, tuple[str, str]] = {
    "compaixao": ("cuida dos fracos", "tem pouca paciência com fraqueza"),
    "honra": ("palavra dada e ofício bem feito", "pensa em vantagem antes de honra"),
    "ordem": ("lei e disciplina", "desconfia de regras e autoridades"),
    "ganancia": ("riqueza e bom negócio", "pouco se importa com ouro"),
    "fe": ("fé e tradição", "desconfia de rezas e sermões"),
    "coragem": ("enfrentar o perigo de frente", "prefere evitar o confronto"),
    "abismo": ("curiosidade pelo Abismo", "horror ao que vem do Abismo"),
}

_ROMANCE_RULE = (
    "REGRA FIXA (romance): cena íntima termina em corte antes de qualquer contato físico "
    "explícito; nada sexual; foco em diálogo, gesto e consequência."
)


def _fold(text: str) -> str:
    return ctags._fold(text)


def values_phrase(values: dict[str, int]) -> str:
    ranked = sorted(
        ((a, v) for a, v in (values or {}).items() if v and a in cs.AXES),
        key=lambda av: (-abs(av[1]), cs.AXES.index(av[0])),
    )[:2]
    parts = [_AXIS_PHRASE[a][0 if v > 0 else 1] for a, v in ranked]
    return "; ".join(parts) if parts else "sem convicções fortes"


def _turn(state: dict) -> int:
    return cs._turn(state)


def _pending(soul: dict, turn: int) -> list[dict]:
    return [
        r
        for r in (soul.get("reactions") or [])
        if isinstance(r, dict)
        and not r.get("consumed")
        and _int(r.get("turn")) < turn
        and turn - _int(r.get("turn")) <= cs.REACTION_TTL
    ]


def _int(v) -> int:
    return cs._int(v)


def _present(state: dict) -> list[tuple[str, dict, dict]]:
    from party import active_allies

    souls = state.get("companion_souls") or {}
    out = []
    for comp in active_allies(state):
        if comp.get("transient"):
            continue
        cid = cs.comp_id(comp)
        soul = souls.get(cid)
        if isinstance(soul, dict) and not soul.get("departed"):
            out.append((cid, comp, soul))
    return sorted(out, key=lambda t: t[0])


def _prose(tag: str) -> str:
    meta = ctags.catalog().get(tag) or {}
    return str(meta.get("prose") or "tomou uma decisão marcante")


def _clip(text: str, cap: int) -> str:
    return text if len(text) <= cap else text[: cap - 1].rstrip() + "…"


def _header(comp: dict, soul: dict, row: dict) -> str:
    role = str(row.get("role") or comp.get("archetype") or "").strip()
    name = str(comp.get("name") or soul.get("companion_id"))
    label = cs.approval_label(soul.get("approval", 50))
    who = f"{name} ({role})" if role else name
    return f"{who} — {label}.\nO que importa: {values_phrase(soul.get('values') or {})}."


def _romance_line(soul: dict) -> str:
    stage = soul.get("romance")
    if not cs.romance_enabled() or stage in (None, "none"):
        return ""
    return {
        "interesse": "Entre vocês há um interesse discreto.",
        "vinculo": "Entre vocês há um vínculo declarado.",
        "compromisso": "Vocês estão comprometidos.",
        "rompido": "O que havia entre vocês esfriou.",
    }.get(str(stage), "")


def _speaker_block(
    kind: str, comp: dict, soul: dict, row: dict, reaction: dict | None, state: dict
) -> str:
    name = str(comp.get("name") or soul.get("companion_id"))
    lines = [_header(comp, soul, row)]
    if kind == "despedida":
        lines.append(
            f"{name} decidiu deixar o grupo. FAÇA: {name} se despede com uma fala curta e "
            "fria, sem rodeios. Não mude o que o motor registrou."
        )
    elif kind == "aviso":
        lines.append(
            f"{name} está perdendo a paciência. FAÇA: {name} avisa claramente que está "
            "descontente e que não vai aguentar muito mais. Fala curta, sem ameaça de morte."
        )
    elif kind == "reacao" and reaction:
        delta = _int(reaction.get("delta"))
        phrase = cs.change_phrase(name, delta) or ""
        lines.append(
            f"No turno anterior o herói {_prose(str(reaction.get('tag')))}. {phrase}\n"
            f"FAÇA: uma fala curta de {name} reagindo a isso, no tom dela. Não decida nada por "
            "ela além disso; não mude o que o motor registrou."
        )
    elif kind == "resolucao":
        lines.append(
            f"{name} chegou ao lugar do seu assunto pessoal. FAÇA: uma cena breve em que "
            f"{name} resolve esse assunto com a ajuda do herói."
        )
    elif kind == "acampamento":
        lines.append(f"Acampamento: {name} aproveita a calma para conversar com o herói.")
    return "\n".join(lines)


def _camp_topic(state: dict, comp: dict, soul: dict, row: dict, turn: int) -> tuple[str, str]:
    """Tópico da conversa de acampamento escolhido em Python: (id, instrução)."""
    name = str(comp.get("name") or soul.get("companion_id"))
    if cs.reveal_ready(soul):
        spec = cs.personal_quest_spec(state, comp)
        return (
            "quest",
            f"{name} confia o bastante para contar um assunto pessoal: {spec['description']} "
            f"FAÇA: {name} conta isso ao herói, sem inventar detalhes além do dito.",
        )
    stage_pending = any(r.get("tag") == "estagio" for r in _pending(soul, turn))
    if stage_pending and cs.romance_enabled():
        stage = str(soul.get("romance"))
        return (
            "romance",
            f"FAÇA: uma conversa íntima entre {name} e o herói sobre o vínculo ({stage}), "
            "em diálogo e gesto; a cena termina em corte.",
        )
    return (
        "values",
        f"FAÇA: {name} comenta algo pessoal coerente com o que importa para ela(e), "
        "em 1 ou 2 falas curtas.",
    )


def _story_block(state: dict) -> tuple[str, list[str]]:
    present = _present(state)
    if not present:
        return "", []
    turn = _turn(state)
    rows = {cid: cs.npc_row(state, comp)[1] for cid, comp, _ in present}
    ack: list[str] = []
    chosen: list[str] = []

    def reaction_id(cid: str, soul: dict, tag: str) -> str:
        for r in _pending(soul, turn):
            if r.get("tag") == tag:
                return f"r:{cid}:{r['id']}"
        return ""

    # 1. despedida/traição pendente
    for cid, comp, soul in present:
        if soul.get("departure_pending"):
            chosen.append(_speaker_block("despedida", comp, soul, rows[cid], None, state))
            rid = reaction_id(cid, soul, "despedida")
            ack.append(rid or f"r:{cid}:{soul.get('departure_turn')}:despedida")
            break
    # 2. aviso pendente
    if not chosen:
        for cid, comp, soul in present:
            rid = reaction_id(cid, soul, "aviso")
            if rid:
                chosen.append(_speaker_block("aviso", comp, soul, rows[cid], None, state))
                ack.append(rid)
                break
    # 2b. cena de resolução da missão pessoal
    if not chosen:
        for cid, comp, soul in present:
            if soul.get("personal_quest") == "ready" and turn > _int(soul.get("quest_ready_turn")):
                chosen.append(_speaker_block("resolucao", comp, soul, rows[cid], None, state))
                ack.append(f"topic:{cid}:resolve")
                break
    # 3. reação forte (um só; empate por RNG seeded)
    if not chosen:
        best: list[tuple[str, dict, dict, dict]] = []
        top = 0
        for cid, comp, soul in present:
            for r in _pending(soul, turn):
                if r.get("tag") in _QUIET_TAGS:
                    continue
                mag = abs(_int(r.get("delta")))
                if mag < STRONG_DELTA:
                    continue
                if mag > top:
                    top, best = mag, []
                if mag == top:
                    best.append((cid, comp, soul, r))
        if best:
            rng = random.Random(f"{state.get('game_id', '')}|{turn}|companion_voice")
            cid, comp, soul, r = best[rng.randrange(len(best))] if len(best) > 1 else best[0]
            chosen.append(_speaker_block("reacao", comp, soul, rows[cid], r, state))
            ack.append(f"r:{cid}:{r['id']}")
    # 4. acampamento (até 2)
    if not chosen and cs._rest_turn(state):
        for cid, comp, soul in present[:MAX_CAMP_SPEAKERS]:
            topic, instruction = _camp_topic(state, comp, soul, rows[cid], turn)
            chosen.append(
                _speaker_block("acampamento", comp, soul, rows[cid], None, state)
                + "\n"
                + instruction
            )
            ack.append(f"topic:{cid}:{topic}")
            for r in _pending(soul, turn):
                if r.get("tag") == "estagio":
                    ack.append(f"r:{cid}:{r['id']}")
    # 5. silêncio
    if not chosen:
        names = ", ".join(str(c.get("name")) for _, c, _ in present)
        chosen.append(
            f"Companheiros presentes: {names}. Ficam calados neste turno (só presença; "
            "não invente falas deles)."
        )
    body = "\n\n".join(_clip(b, BLOCK_CAP_EACH) for b in chosen)
    extra = ""
    if cs.romance_enabled() and any(s.get("romance") not in (None, "none") for _, _, s in present):
        extra = "\n" + _ROMANCE_RULE
    return _wrap(body, extra), ack


def _wrap(body: str, extra: str = "") -> str:
    """Teto total (R12); ``extra`` (regra fixa de romance) nunca é cortado."""
    body = _clip(body, BLOCK_CAP_TOTAL - 40 - len(extra))
    return f"<COMPANHEIROS>\n{body}{extra}\n</COMPANHEIROS>"


def _npc_block(state: dict, target: str) -> tuple[str, list[str]]:
    present = _present(state)
    key = _fold(target)
    match = None
    for cid, comp, soul in present:
        row = cs.npc_row(state, comp)[1]
        if key in {_fold(cid), _fold(comp.get("name", "")), _fold(row.get("id", ""))}:
            match = (cid, comp, soul, row)
            break
    if match is None:
        return "", []
    cid, comp, soul, row = match
    turn = _turn(state)
    name = str(comp.get("name") or cid)
    lines = [_header(comp, soul, row)]
    recent = [r for r in (soul.get("reactions") or []) if r.get("tag") not in _QUIET_TAGS][-3:]
    if recent:
        lines.append(
            "Escolhas recentes do herói que você viu: "
            + "; ".join(_prose(str(r.get("tag"))) for r in recent)
            + "."
        )
    if soul.get("departure_pending"):
        lines.append(f"{name} já decidiu partir; a fala é de despedida.")
    elif soul.get("warned_turn") is not None:
        lines.append(f"{name} já avisou que está descontente; isso pesa na conversa.")
    quest_stage = soul.get("personal_quest")
    if quest_stage == "revealed":
        lines.append("Você tem um assunto pessoal já contado ao herói.")
    elif quest_stage == "none" and cs.reveal_ready(soul):
        lines.append(
            "Você tem um assunto pessoal que ainda não contou; só conte num momento calmo."
        )
    rline = _romance_line(soul)
    if rline:
        lines.append(rline)
    ack = [f"r:{cid}:{r['id']}" for r in _pending(soul, turn) if r.get("tag") not in _QUIET_TAGS][
        :3
    ]
    intent = ctags.detect_romance_intent(ctags._last_human_text(state))
    if intent:
        ack.append(f"intent:{cid}:romance")
        row_traits = cs._traits(row)
        adult = _int(row.get("age") or 18) >= 18
        if cs.romance_gate_open(soul, row_traits, adult=adult):
            lines.append(
                "O herói demonstra interesse romântico. Você pode corresponder com delicadeza; "
                "a cena, se houver, termina em corte antes de contato físico explícito."
            )
        else:
            lines.append(
                "O herói demonstra interesse romântico, mas isso não cabe agora: recuse com "
                "delicadeza, sem ofender e sem penalizá-lo."
            )
    extra = ""
    if cs.romance_enabled() and soul.get("romance") not in (None, "none"):
        extra = "\n" + _ROMANCE_RULE
    return _wrap(_clip("\n".join(lines), BLOCK_CAP_EACH - len(extra)), extra), ack


def companion_prompt_block(
    state: dict, purpose: Literal["story", "npc"], *, target: str = ""
) -> tuple[str, list[str]]:
    """``(bloco, ids para companion_voice_ack)``. Vazio sem companheiro presente / flag != on."""
    if cs.mode() != "on":
        return "", []
    if purpose == "npc":
        return _npc_block(state, target)
    return _story_block(state)
