"""Stable player-facing messages, separate from the short LLM transcript."""
from __future__ import annotations

from hashlib import sha256


def message_kind(state: dict) -> str:
    route = str(state.get('last_routed_intent') or state.get('next') or '').lower()
    return {'combat_agent': 'COMBAT', 'combat': 'COMBAT', 'npc_actor': 'NPC',
            'npc': 'NPC', 'loot': 'LOOT', 'loot_agent': 'LOOT'}.get(route, 'STORY')


def record_history(state: dict, text: str, *, include_input: bool = True) -> None:
    history = list(state.get('presentation_history') or [])
    epoch = int((state.get('continuity') or {}).get('timeline_epoch', 0))
    turn = int((state.get('world') or {}).get('turn_count', 0))
    rows = []
    if include_input:
        human = next((m for m in reversed(state.get('messages') or [])
                      if getattr(m, 'type', '') == 'human'), None)
        if human:
            rows.append(('player', str(human.content)))
    rows.append(('narrator', text))
    for role, content in rows:
        key = sha256(f"{state['game_id']}:{epoch}:{turn}:{role}".encode()).hexdigest()[:24]
        if not any(row['id'] == key for row in history):
            history.append({'id': key, 'turn': turn, 'epoch': epoch, 'role': role,
                            'text': content, 'type': message_kind(state) if role == 'narrator' else 'STORY'})
    state['presentation_history'] = history


def history_page(state: dict, *, cursor: str | None = None, limit: int = 50) -> dict:
    epoch = int((state.get('continuity') or {}).get('timeline_epoch', 0))
    offset = 0
    if cursor:
        cursor_epoch, offset_text = cursor.split(':')
        offset = int(offset_text)
        if int(cursor_epoch) != epoch or offset < 0:
            raise ValueError('history_cursor_stale')
    entries = list(state.get('presentation_history') or [])
    partial = not bool(entries)
    if partial:
        for i, msg in enumerate(state.get('messages') or []):
            role = {'human': 'player', 'ai': 'narrator'}.get(getattr(msg, 'type', ''))
            if role:
                entries.append({'id': f'legacy:{epoch}:{i}', 'turn': 0, 'epoch': epoch,
                                'role': role, 'text': str(msg.content), 'type': 'STORY'})
    end = offset + max(1, min(100, limit))
    return {'entries': entries[offset:end], 'next_cursor': f'{epoch}:{end}' if end < len(entries) else None,
            'epoch': epoch, 'partial_history': partial}
