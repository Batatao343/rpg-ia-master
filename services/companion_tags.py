"""SPEC-300 — detecção de tags de escolha (puro, sem LLM).

Fontes aceitas (R5): eventos NOVOS do ``event_log`` (ids ausentes do baseline), desfecho de
combate encerrado, diferenças de baseline (``abyss_charge``/ouro) e um conjunto fechado de
regex sobre a última ação do jogador. Nunca lê ``faction_impacts`` nem texto narrado.
"""

from __future__ import annotations

import json
import re
import unicodedata
from functools import lru_cache
from pathlib import Path
from typing import Any, TypedDict

_DATA = Path(__file__).resolve().parent.parent / "data"


class ChoiceTag(TypedDict):
    id: str
    faction_id: str  # "" se não se aplica
    sign: int  # +1 / -1 (FACTION_DIRECT)
    source_ref: str  # event_id | "combat:<encounter_id>" | "regex" | "baseline"


@lru_cache(maxsize=1)
def catalog() -> dict[str, dict]:
    raw = json.loads((_DATA / "companion_choice_tags.json").read_text(encoding="utf-8"))
    return {t["id"]: t for t in raw["tags"]}


def _fold(text: Any) -> str:
    raw = unicodedata.normalize("NFKD", str(text or ""))
    return "".join(c for c in raw if not unicodedata.combining(c)).lower()


def _int(value: Any, default: int = 0) -> int:
    if isinstance(value, bool):
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


# --------------------------------------------------------------------------- #
# Regex fechadas (magnitude 1; negação testada)
# --------------------------------------------------------------------------- #
_NEGATION = re.compile(r"\b(nao|nunca|jamais|sem|ninguem)\b")
_THREAT = re.compile(
    r"\b(ameac\w*|intimid\w*|aterroriz\w*|"
    r"vou (?:te |lhe )?(?:matar|machucar|quebrar|cortar)|"
    r"(?:puxo|saco|encosto|aponto)\b[^.!?]{0,20}\b(?:faca|adaga|espada|lamina)\b)"
)
_DONATION = re.compile(
    r"\b(?:doo|doar|doacao|esmola|"
    r"(?:dou|entrego|ofereco|deixo|dar)\s+(?:\d+\s+)?(?:de\s+)?(?:moedas?|ouro|dinheiro)\s+"
    r"(?:a|ao|aos|para|pra)\b)"
)
_ROMANCE = re.compile(
    r"\b(?:flert\w*|cortej\w*|beij\w*|abrac\w*\s+(?:com\s+)?carinho|"
    r"(?:gosto|amo)\s+(?:muito\s+)?de\s+voce|"
    r"(?:quero|gostaria de)\s+(?:ficar|estar)\s+(?:mais\s+)?(?:perto|junto)|"
    r"(?:te|lhe)\s+(?:amo|quero\s+bem)|romanc\w*|meu\s+coracao|apaixon\w*)\b"
)


def _matches_unnegated(rx: re.Pattern, folded: str) -> bool:
    for m in rx.finditer(folded):
        before = folded[max(0, m.start() - 24) : m.start()]
        if not _NEGATION.search(before):
            return True
    return False


def detect_action_tags(text: str) -> list[str]:
    """Tags por regex da ação do jogador (``doou_ouro`` ainda exige a queda de ouro)."""
    folded = _fold(text)
    out: list[str] = []
    if _matches_unnegated(_THREAT, folded):
        out.append("ameacou")
    if _matches_unnegated(_DONATION, folded):
        out.append("doou_ouro")
    return out


def detect_romance_intent(text: str) -> bool:
    return _matches_unnegated(_ROMANCE, _fold(text))


# --------------------------------------------------------------------------- #
# Estado -> tags
# --------------------------------------------------------------------------- #
def _last_human_text(state: dict) -> str:
    for message in reversed(state.get("messages") or []):
        if getattr(message, "type", "") == "human":
            return str(getattr(message, "content", "") or "")
    return ""


def new_events(state: dict) -> list[dict]:
    seen = set((state.get("turn_baseline") or {}).get("event_ids") or [])
    return [
        e
        for e in (state.get("event_log") or [])
        if isinstance(e, dict) and e.get("event_id") and e["event_id"] not in seen
    ]


def combat_result_id(state: dict) -> str:
    """Id estável do desfecho de combate ENCERRADO ("" se não há)."""
    combat = state.get("combat") or {}
    if combat.get("phase") != "ended":
        return ""
    result = combat.get("result") or {}
    return str(result.get("result_event_id") or result.get("encounter_id") or "ended")


def _combat_outcome(state: dict) -> str:
    combat = state.get("combat") or {}
    result = combat.get("result") or {}
    return str(combat.get("outcome") or result.get("outcome") or "")


def _spared_enemy(state: dict) -> bool:
    """SPEC-325: o desfecho do encontro deixou algum inimigo incapacitado (nao-letal)."""
    result = (state.get("combat") or {}).get("result") or {}
    return any(
        isinstance(p, dict) and p.get("final_status") == "incapacitado"
        for p in result.get("participants") or []
    )


def _in_combat_this_turn(state: dict) -> bool:
    combat = state.get("combat") or {}
    return bool(combat) and combat.get("phase") in {"entering", "active", "resolving", "ended"}


def _npc_by_id(state: dict, entity_id: str) -> dict:
    for row in (state.get("npcs") or {}).values():
        if isinstance(row, dict) and row.get("id") == entity_id:
            return row
    return {}


def detect_choice_tags(state: dict, *, seen_combat_id: str = "") -> list[ChoiceTag]:
    """Tags do turno. ``seen_combat_id`` evita recontar o mesmo combate encerrado."""
    cat = catalog()
    tags: list[ChoiceTag] = []

    def add(tag_id: str, *, faction_id: str = "", sign: int = 0, ref: str = "") -> None:
        if tag_id in cat:
            tags.append({"id": tag_id, "faction_id": faction_id, "sign": sign, "source_ref": ref})

    baseline = state.get("turn_baseline") or {}
    events = new_events(state)
    fought = _in_combat_this_turn(state)
    for ev in events:
        etype = str(ev.get("type") or "")
        eid = str(ev.get("event_id") or "")
        payload = ev.get("payload") or {}
        if etype == "npc_killed" and ev.get("actor_id") == "player":
            victim = _npc_by_id(state, str(ev.get("target_id") or ""))
            rel = victim.get("relationship")
            if not fought and rel is not None and _int(rel, 0) >= 5:
                add("matou_inocente", ref=eid)
            else:
                add("matou_nomeado", ref=eid)
        elif etype == "quest_completed":
            if not payload.get("personal_of"):
                add("quest_concluida", ref=eid)
        elif etype == "quest_failed":
            if not payload.get("personal_of") and payload.get("reason") != "companion_gone":
                add("quest_falhou", ref=eid)
        elif etype == "faction_deed":
            direction = str(payload.get("direction") or "")
            fid = str(ev.get("target_id") or "")
            if direction == "ajudou":
                add("ajudou_faccao", faction_id=fid, sign=1, ref=eid)
            elif direction == "prejudicou":
                add("prejudicou_faccao", faction_id=fid, sign=-1, ref=eid)
        elif etype == "secret_revealed":
            add("revelou_segredo", ref=eid)
        elif etype == "crime_witnessed":  # SPEC-299 (se existir)
            add("crime_testemunhado", ref=eid)
        elif etype == "fine_paid":  # SPEC-299 (se existir)
            add("pagou_multa", ref=eid)
        elif etype == "companion_abandoned":  # SPEC-325 R12: os OUTROS companheiros reagem
            add("abandonou_companheiro", ref=eid)

    cid = combat_result_id(state)
    if cid and cid != seen_combat_id:
        outcome = _combat_outcome(state)
        if outcome == "surrendered_enemy":
            add("aceitou_rendicao", ref=f"combat:{cid}")
        elif outcome == "fled":
            add("fugiu_do_combate", ref=f"combat:{cid}")
        elif outcome == "victory" and _spared_enemy(state):
            add("poupou_inimigo", ref=f"combat:{cid}")  # SPEC-325 R9

    player = state.get("player") or {}
    if _int(player.get("abyss_charge")) > _int(baseline.get("abyss_charge")):
        add("usou_abismo", ref="baseline")

    for tag_id in detect_action_tags(_last_human_text(state)):
        if tag_id == "doou_ouro":
            gold_down = _int(player.get("gold")) < _int(
                baseline.get("gold"), _int(player.get("gold"))
            )
            if not gold_down or _int(baseline.get("gold_spent")) > 0:
                continue
        add(tag_id, ref="regex")
    return tags
