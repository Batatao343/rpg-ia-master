"""SPEC-393 R3: a prosa do desfecho de morte não contradiz os Ferimentos reais do herói.

Vocabulário fechado (partes do corpo e gravidades do registro). Determinístico: devolve o
motivo da rejeição ou None. O chamador cai no texto determinístico de desfecho."""

from __future__ import annotations

import re

from services.economy import _fold

_REGION = re.compile(r"\b(cabeca|torso|braco|perna)s?(?: (esquerd|direit)[oa])?\b")
_GRAVITY = re.compile(r"\b(leve|grave|critic)(?:o|a|s|os|as|mente|amente)?\b")
_WOUND_WORD = re.compile(r"\b(ferimento|ferimentos|ferid[oa]s?|ferir|feriu)\b")
_OTHER_OWNER = re.compile(
    r"\b(?:braco|perna|torso|cabeca)s?(?: (?:esquerd|direit)[oa])? d[oae]s? (?!corpo\b)\w"
)
_THIRD_PARTY = re.compile(
    r"^(?:o|a|os|as|um|uma) (?!(?:braco|perna|torso|cabeca)s?\b)\w+(?: \w+)?,? ferid"
)
_NEGATION = re.compile(
    r"\b(?:sem|nenhum|nenhuma|nao)\b(?: \w+){0,2}? (?:ferimentos?|ferid\w*|leves?|graves?|criticos?)\b"
)
_SPLIT = re.compile(r"[.!?\n]+")


def wounds_from_player(player: dict) -> list[dict]:
    """Ferimentos do herói como [{regiao, categoria}] (categoria sem acento)."""
    out: list[dict] = []
    for cat, items in (player.get("ferimentos") or {}).items():
        for w in items or []:
            region = str((w or {}).get("regiao") or "")
            out.append({"regiao": region, "categoria": _fold(str(cat))})  # noqa: PERF401
    return out


def _wound_key(w: dict) -> tuple[str, str, str]:
    region = _fold(str(w.get("regiao") or ""))
    base, _, side = region.partition("_")
    return base, side[:-1] if side else "", _fold(str(w.get("categoria") or ""))


def _sentence_reason(sent: str, keys: list[tuple[str, str, str]]) -> str | None:
    """`sent` já em fold (minúsculas, sem acento)."""
    regions = [(m.group(1), m.group(2) or "") for m in _REGION.finditer(sent)]
    if not regions or not _WOUND_WORD.search(sent) or _NEGATION.search(sent):
        return None
    if _OTHER_OWNER.search(sent) or _THIRD_PARTY.match(sent.strip()):
        return None
    recorded = [
        k for k in keys if any(k[0] == b and (not s or not k[1] or k[1] == s) for b, s in regions)
    ]
    for raw_gravity in {m.group(1) for m in _GRAVITY.finditer(sent)}:
        gravity = "critico" if raw_gravity == "critic" else raw_gravity
        if not any(k[2] == gravity for k in recorded):
            return f"gravidade:{gravity}"
    return None if recorded else "parte_fora_do_registro:" + regions[0][0]


def check(prose: str, wounds: list[dict]) -> str | None:
    """Motivo da contradição com o registro de Ferimentos, ou None se a prosa é fiel."""
    keys = [_wound_key(w) for w in wounds]
    for raw in _SPLIT.split(prose or ""):
        if not raw.strip():
            continue
        reason = _sentence_reason(_fold(raw), keys)
        if reason:
            return reason
    return None


def codes(label: str, prose: str, player: dict) -> list[str]:
    """Códigos de rejeição para `_narrate_outcome` (vazio fora da morte ou com prosa fiel)."""
    if label != "death":
        return []
    reason = check(prose, wounds_from_player(player))
    if not reason:
        return []
    from observability.telemetry import log_fallback

    log_fallback("combat.death_prose", "wound_contradiction", detail=reason)
    return [f"wounds:{reason}"]
