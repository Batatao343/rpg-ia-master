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


def render_player_message(narrative: str, outcome: dict) -> str:
    gains = (int(outcome.get("gold_delta", 0) or 0) > 0
             or int(outcome.get("xp_delta", 0) or 0) > 0
             or bool(outcome.get("items_gained")) or bool(outcome.get("quests_completed")))
    text = str(narrative or "").strip()
    # Reserved receipt blocks are untrusted input, even when emitted by a model.
    # Replace each marker's line; retain unrelated prose on following lines.
    text = re.sub(r"\[RESULTADO\][^\r\n]*", "", text).strip()
    if gains:
        text = _NEGATIVE_REWARD.sub("", text).strip()
    if outcome.get("items_gained"):
        text = _NEGATIVE_ITEM.sub("", text).strip()
    receipt: list[str] = []
    if int(outcome.get("gold_delta", 0) or 0) > 0:
        receipt.append(f"+{outcome['gold_delta']} ouro")
    if int(outcome.get("xp_delta", 0) or 0) > 0:
        receipt.append(f"+{outcome['xp_delta']} XP")
    receipt.extend(f"+{qty} {item_id}" for item_id, qty
                   in sorted((outcome.get("items_gained") or {}).items()))
    if outcome.get("quests_completed"):
        receipt.append(f"{len(outcome['quests_completed'])} missão(ões) concluída(s)")
    if receipt:
        text = f"{text}\n\n[RESULTADO] " + " · ".join(receipt)
    return text


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
    outcome["player_message"] = render_player_message(_last_ai_text(state), outcome)
    return outcome


def player_facing_message(state: dict) -> str:
    action = state.get("last_action_outcome") or {}
    if not action.get("allowed", True) and action.get("message"):
        return str(action["message"])
    outcome = state.get("last_turn_outcome") or {}
    if outcome.get("player_message"):
        return str(outcome["player_message"])
    return _last_ai_text(state)
