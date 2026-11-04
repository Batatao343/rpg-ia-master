"""SPEC-387 R33 / Sol P1-1 / R2-P1-1: texto do modo `off` sem LLM, traduzido do registro técnico do motor."""

from __future__ import annotations

import re
from collections.abc import Iterable

from services import round_log as rl

_ATK_LINE_RE = re.compile(r"^(.+?) → (.+?): (acerto|erro|critico|supercritico)\b")
_WOUND_LINE_RE = re.compile(r"Ferimento (\w+) em (\w+)")
_VIT_ZERO_RE = re.compile(r"Vitalidade [1-9]\d* -> 0\b")
_ATK_VERB = {
    "acerto": "acerta",
    "erro": "erra",
    "critico": "acerta em cheio",
    "supercritico": "acerta de forma devastadora",
}


_USA_LINE_RE = re.compile(r"^Usa (.+?)(?: \(| —|$)")
_NOISE_RE = re.compile(r"→|->|×|\btotal \d|Entropia|Carga do Abismo|\(excedente|^dano \d")


def _clean_numeric(line: str) -> str:
    """Linha humana com número (cura, dano contínuo): fica o número, sai o parêntese técnico."""
    line = re.sub(r" \(Vit \d+\)", "", line)
    return re.sub(r"recupera (\d+) Vitalidade", r"recupera \1 de Vitalidade", line)


def context(cards_used: Iterable[dict] | None, names: dict[str, str] | None) -> dict:
    """Autoria das Cartas: `out["cards_used"]` (em ordem, com `actor_id`) + nome de cada ator."""
    return {"cards_used": list(cards_used or []), "names": dict(names or {})}


def context_from(out: dict, actors_by_id: dict) -> dict:
    """Monta o contexto a partir da saída do `run_round` e dos atores do conflito."""
    names = {
        str(k): str(a.get("name") or "") for k, a in actors_by_id.items() if isinstance(a, dict)
    }
    return context(out.get("cards_used"), names)


def _used_name(entry: dict) -> str:
    card = entry.get("card") or rl._card(entry.get("card_id")) or {}
    return str(card.get("name") or "")


def _translate_logs(logs: Iterable[str], hero_name: str, ctx: dict | None = None) -> list[str]:
    """SPEC-387 (Sol P1-1, R2-P1-1): o registro técnico do motor em frases na voz "você", SEM descartar
    fatos (Carta usada e por quem, golpe, ferimento, Vitalidade, cura, dano contínuo, fuga). Descarta só
    aritmética de dado e ids; nunca o nome do herói."""
    hero = (hero_name or "").strip()
    queue = list((ctx or {}).get("cards_used") or [])
    names = (ctx or {}).get("names") or {}
    out: list[str] = []
    target = ""  # quem sofreu o último golpe (para o Ferimento/Vitalidade da linha seguinte)

    def who(name: str, subject: bool) -> str:
        if hero and name == hero:
            return "Você" if subject else "você"
        return name

    for raw in logs:
        line = str(raw or "").strip()
        if not line:
            continue
        u = _USA_LINE_RE.match(line)
        if u:  # o autor vem de `cards_used` (em ordem), NUNCA do nome da Carta
            card = u.group(1)
            hit = next((i for i, e in enumerate(queue) if _used_name(e) == card), None)
            actor = names.get(str(queue.pop(hit).get("actor_id"))) if hit is not None else ""
            out.append(f"{who(actor, True)} usa {card}." if actor else f"{card} é usada.")
            continue
        m = _ATK_LINE_RE.match(line)
        if m:
            target = m.group(2)
            out.append(f"{who(m.group(1), True)} {_ATK_VERB[m.group(3)]} {who(target, False)}.")
            continue
        w = _WOUND_LINE_RE.search(line)
        v = _VIT_ZERO_RE.search(line)
        if (w or v) and target:
            subj = who(target, True)
            if v:
                out.append(f"{subj} fica sem Vitalidade.")
            if w:
                cat, reg = rl._cat_pt(w.group(1)), rl._region_phrase(w.group(2))
                out.append(f"{subj} sofre um ferimento {cat} {reg}.")
            continue
        if _NOISE_RE.search(line) and not line.startswith("Você"):
            continue
        human = rl._voce(_clean_numeric(line), hero)
        if rl._is_arith(human) and not human.startswith("Você"):
            continue
        if not rl._RAW_ID_RE.search(human) and not rl.names_hero(human, hero):
            out.append(human)
    return out


def off_fallback_text(
    logs: Iterable[str],
    hero_name: str,
    flavor: str,
    victory: bool,
    ctx: dict | None = None,
) -> str:
    """SPEC-387 R33: texto do modo `off` sem LLM — só linhas humanas do motor, na voz do jogador
    ("você"), sem id, sem bullets nem "⚔️"; um parágrafo como `deterministic_outcome_text`."""
    lines: list[str] = []
    for human in _translate_logs(logs, hero_name, ctx):
        if human not in lines:
            lines.append(human)
    head = [flavor.strip()] if flavor and flavor.strip() else []
    tail = "Vitória! O campo silencia." if victory else "O que você faz?"
    return " ".join([*head, *lines]) + ("\n\n" if lines or head else "") + tail


def for_round(
    logs: Iterable[str], player: dict, flavor: str | None, victory: bool, ctx: dict | None
) -> str:
    """Montagem dos argumentos para o `_narrate` do combate (mantém o agente enxuto)."""
    return off_fallback_text(logs, str(player.get("name") or ""), flavor or "", victory, ctx)
