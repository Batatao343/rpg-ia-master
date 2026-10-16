"""Canonical end-of-turn outcome and shared player-facing presentation."""
from __future__ import annotations

import hashlib
import re
from collections import Counter

_NEGATIVE_REWARD = re.compile(
    r"[^.!?]*(?:nada novo (?:foi )?obtido|nenhuma "
    r"recompensa[^.!?]{0,50}(?:obtido|obtida|acrescentado|acrescentada))[^.!?]*[.!?]?",
    re.IGNORECASE,
)
_NEGATIVE_ITEM = re.compile(
    r"[^.!?]*nenhum(?:a)? (?:objeto|item)[^.!?]{0,50}(?:obtido|acrescentado)[^.!?]*[.!?]?",
    re.IGNORECASE,
)


def record_gain(baseline: dict | None, kind: str, amount: int,
                origin: str | None = None) -> dict | None:
    """SPEC-226 R10: registra um ganho (amount > 0) ou gasto (amount < 0) individual
    de `kind` ('gold'|'xp') no `turn_baseline` do turno, para o guard narrativo
    aceitar o GANHO BRUTO por fonte. PURO: devolve cópia; sem baseline (nó chamado
    fora do grafo) devolve o próprio valor, sem inventar um baseline parcial."""
    if not baseline or kind not in ("gold", "xp"):
        return baseline
    amount = int(amount or 0)
    if not amount:
        return baseline
    out = dict(baseline)
    if amount > 0:
        out[f"{kind}_gains"] = [*(baseline.get(f"{kind}_gains") or []), amount]
        if origin:  # SPEC-199: origem (combat|beat|quest|loot|exploration)
            out["gain_origins"] = [*(baseline.get("gain_origins") or []), origin]
    else:
        out[f"{kind}_spent"] = int(baseline.get(f"{kind}_spent", 0) or 0) - amount
    return out


def _inventory(actor: dict) -> Counter[str]:
    counts: Counter[str] = Counter()
    for entry in actor.get("inventory") or []:
        if isinstance(entry, dict) and entry.get("id"):
            qty = int(entry.get("qty", 1) or 0)
            if qty > 0:
                counts[str(entry["id"])] += qty
    return counts


def capture_baseline(state: dict) -> dict:
    player = state.get("player") or {}
    return {
        "turn": int((state.get("world") or {}).get("turn_count", 0) or 0),
        "gold": int(player.get("gold", 0) or 0), "xp": int(player.get("xp", 0) or 0),
        "level": int(player.get("level", 1) or 1), "inventory": dict(_inventory(player)),
        "completed_quests": sorted(str(q.get("id") or "") for q in (state.get("quests") or [])
                                   if isinstance(q, dict) and q.get("status") == "completed"),
        "event_ids": sorted(str(e.get("event_id") or "") for e in (state.get("event_log") or [])
                            if isinstance(e, dict) and e.get("event_id")),
    }


def _last_ai_text(state: dict) -> str:
    for message in reversed(state.get("messages") or []):
        if getattr(message, "type", "") != "human" and getattr(message, "content", ""):
            return str(message.content)
    return ""


_RECEIPT = re.compile(r"[ \t]*\[RESULTADO\][^\r\n]*")


def strip_receipt(text: str) -> str:
    """SPEC-199 R7: remove blocos legados `[RESULTADO] ...` (saves pré-SPEC-199)."""
    return _RECEIPT.sub("", str(text or "")).strip()


def render_player_message(narrative: str, outcome: dict) -> str:
    gains = (int(outcome.get("gold_delta", 0) or 0) > 0
             or int(outcome.get("xp_delta", 0) or 0) > 0
             or bool(outcome.get("items_gained")) or bool(outcome.get("quests_completed")))
    text = str(narrative or "").strip()
    # Reserved receipt blocks are untrusted input, even when emitted by a model.
    # Replace each marker's line; retain unrelated prose on following lines.
    text = strip_receipt(text)
    if gains:
        text = _NEGATIVE_REWARD.sub("", text).strip()
    if outcome.get("items_gained"):
        text = _NEGATIVE_ITEM.sub("", text).strip()
    return text


_ORIGIN_SOURCE = {"combat": "combat", "beat": "story", "quest": "quest",
                  "loot": "loot", "exploration": "exploration"}


def _source(outcome: dict, origins: list | None = None) -> str:
    """Derivado das ORIGENS registradas por `record_gain` (nunca do LLM); sem
    origem registrada cai na heurística por deltas."""
    mapped = {_ORIGIN_SOURCE[o] for o in origins or [] if o in _ORIGIN_SOURCE}
    if mapped:
        return mapped.pop() if len(mapped) == 1 else "mixed"
    kinds = []
    if int(outcome.get("xp_delta", 0) or 0) > 0:
        kinds.append("combat" if int(outcome.get("level_delta", 0) or 0) >= 0 else "story")
    if outcome.get("quests_completed"):
        kinds.append("quest")
    if int(outcome.get("gold_delta", 0) or 0) > 0 or outcome.get("items_gained"):
        kinds.append("loot")
    if not kinds:
        return "none"
    return kinds[0] if len(set(kinds)) == 1 else "mixed"


def public_outcome(outcome: dict | None) -> dict:
    """SPEC-199 R4: whitelist pública do recibo do turno (sem event_ids/hashes)."""
    if not outcome or not outcome.get("receipt_id"):
        return {}
    import inventory as inv
    items = outcome.get("items_gained") or {}
    if isinstance(items, dict):
        items = [{"id": k, "qty": v} for k, v in sorted(items.items())]
    named = []
    for it in items:
        if not isinstance(it, dict) or not it.get("id"):
            continue
        named.append({"id": str(it["id"]), "qty": int(it.get("qty", 1) or 1),
                      "name": str(it.get("name") or inv.item_display({"id": it["id"]}))})
    quests = []
    for q in outcome.get("quests_completed") or []:
        if isinstance(q, dict):
            quests.append({"id": str(q.get("id") or ""), "title": str(q.get("title") or q.get("id") or "")})
        else:
            quests.append({"id": str(q), "title": str(q)})
    return {
        "receipt_id": str(outcome["receipt_id"]), "turn": int(outcome.get("turn", 0) or 0),
        "xp_delta": int(outcome.get("xp_delta", 0) or 0),
        "level_delta": int(outcome.get("level_delta", 0) or 0),
        "level_after": int(outcome.get("level_after", 0) or 0),
        "gold_delta": int(outcome.get("gold_delta", 0) or 0),
        "items_gained": named, "quests_completed": quests,
        "source": str(outcome.get("source") or _source(outcome)),
    }


def finalize_outcome(state: dict) -> dict:
    baseline = dict(state.get("turn_baseline") or capture_baseline(state))
    now = capture_baseline(state)
    items = dict(_inventory(state.get("player") or {}) - Counter(baseline.get("inventory") or {}))
    outcome = {
        "turn": now["turn"], "gold_delta": now["gold"] - int(baseline.get("gold", now["gold"])),
        "xp_delta": now["xp"] - int(baseline.get("xp", now["xp"])),
        "level_delta": now["level"] - int(baseline.get("level", now["level"])),
        "items_gained": {k: v for k, v in items.items() if k and v > 0},
        "quests_completed": sorted(set(now["completed_quests"]) - set(baseline.get("completed_quests") or [])),
        "event_ids": sorted(set(now["event_ids"]) - set(baseline.get("event_ids") or [])),
    }
    outcome["receipt_id"] = hashlib.sha256(
        f"{state.get('game_id','')}|{repr(sorted(outcome.items()))}".encode()
    ).hexdigest()[:20]
    outcome["level_after"] = now["level"]
    outcome["source"] = _source(outcome, baseline.get("gain_origins"))
    outcome["player_message"] = render_player_message(_last_ai_text(state), outcome)
    # SPEC-202 R9: quem respondeu (público). Fora do receipt_id, que permanece
    # derivado só das mudanças mecânicas.
    from services.interlocutor import public_speaker, speaker_for_turn
    outcome["speaker"] = public_speaker(speaker_for_turn(state))
    return outcome


def player_facing_message(state: dict) -> str:
    action = state.get("last_action_outcome") or {}
    if not action.get("allowed", True) and action.get("message"):
        return str(action["message"])
    outcome = state.get("last_turn_outcome") or {}
    if outcome.get("player_message"):
        return strip_receipt(str(outcome["player_message"]))
    return _last_ai_text(state)
