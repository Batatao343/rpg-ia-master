"""Shared conservative guard for explicit claims, not a semantic truth oracle.

Only committed state/events provide evidence. Unknown atmospheric prose stays
creative; explicit critical contradictions are removed sentence by sentence.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
import re

from services.memory_provenance import (
    _fold, false_player_death_claim, canonical_location_contradiction,
    inventory_possession_contradiction, npc_identity_contradiction, find_strict_unrevealed,
)


@dataclass(frozen=True)
class EvidenceSnapshot:
    game_id: str
    timeline_epoch: int
    turn: int
    location_id: str
    player_alive: bool
    entity_ids: list[str]
    inventory: dict[str, int]
    accepted_event_ids: list[str]
    state: dict = field(repr=False)


@dataclass(frozen=True)
class NarrativeCheck:
    text: str
    rejections: list[dict[str, str]]
    evidence_ids: list[str]


def build_evidence(state: dict) -> EvidenceSnapshot:
    from services.turn_outcome import capture_baseline
    # No pending proposals, prompts or model output can manufacture evidence.
    keys = ('game_id', 'world', 'player', 'npcs', 'event_log', 'continuity',
            'world_projection', 'revealed_secrets', 'game_over', 'turn_baseline',
            'rejected_item_claims')
    canonical = deepcopy({key: state[key] for key in keys if key in state})
    world = canonical.get('world') or {}
    baseline = capture_baseline(canonical)
    return EvidenceSnapshot(str(state.get('game_id', '')),
        int((state.get('continuity') or {}).get('timeline_epoch', 0) or 0),
        int(world.get('turn_count', 0) or 0), str(world.get('current_location_id') or ''),
        false_player_death_claim('Você morreu.', canonical),
        list((state.get('npcs') or {}).keys()), baseline['inventory'],
        baseline['event_ids'], canonical)


_QUALIFIED = re.compile(
    r'\b(?:talvez|caso|outrora|ontem|antigamente|rumor|boato|'
    r'diz que|disse que|afirma que|alega que|conta que|segundo)\b|(?:^|[,;:]\s*)se\b')


def _reason(sentence: str, evidence: EvidenceSnapshot) -> str | None:
    state = evidence.state
    # A quotation cannot launder an unrevealed secret.
    if find_strict_unrevealed(sentence, state):
        return 'unrevealed_secret'
    folded = _fold(sentence)
    if _QUALIFIED.search(folded) or sentence.lstrip().startswith(('"', '“', '—')):
        return None
    if false_player_death_claim(sentence, state):
        return 'player_death'
    if canonical_location_contradiction(sentence):
        return 'location_region'
    if inventory_possession_contradiction(sentence, state):
        return 'inventory_possession'
    if npc_identity_contradiction(sentence, state):
        return 'npc_identity'
    player_name = re.escape(_fold((state.get('player') or {}).get('name', '')))
    subject = rf'(?:voce|o heroi|a heroina|{player_name})' if player_name else r'(?:voce|o heroi|a heroina)'
    import gamedata
    world = state.get('world') or {}
    current = _fold(world.get('current_location', ''))
    for location in gamedata.WORLD_MAP.get('locations', []):
        name = _fold(location.get('name', ''))
        if not name or name == current or location.get('id') == evidence.location_id:
            continue
        if re.search(rf'\b{subject}\s+(?:chegou|esta|se encontra)\s+(?:a|em|no|na|ao)\s+{re.escape(name)}\b', folded):
            return 'current_location'
    # Numeric rewards are authoritative only when matched by the turn baseline.
    reward = re.search(rf'\b{subject}\s+(?:ganhou|recebeu|obteve)\s+(\d+)\s+(ouro|xp)\b', folded)
    if reward and state.get('turn_baseline'):
        key = 'gold' if reward[2] == 'ouro' else 'xp'
        delta = int((state.get('player') or {}).get(key, 0)) - int(state['turn_baseline'].get(key, 0))
        if delta != int(reward[1]):
            return 'reward_delta'
    return None


def validate_narrative(text: str, evidence: EvidenceSnapshot, *, channel: str) -> NarrativeCheck:
    accepted, rejected = [], []
    for sentence in re.split(r'(?<=[.!?])\s+|\n+', str(text or '')):
        if not sentence.strip():
            continue
        reason = _reason(sentence, evidence)
        if reason:
            rejected.append({'channel': channel, 'reason': reason,
                             'turn': str(evidence.turn)})  # never log private text
        else:
            accepted.append(sentence)
    # Preserve original formatting if unchanged (combat log, dialogue, poetry).
    cleaned = str(text or '') if not rejected else ' '.join(accepted).strip()
    return NarrativeCheck(cleaned, rejected[-32:], [])


def guard_current_messages(state: dict) -> tuple[list, list[dict]]:
    evidence = build_evidence(state)
    messages = list(state.get('messages') or [])
    audit: list[dict] = []
    start = max((i for i, msg in enumerate(messages) if getattr(msg, 'type', '') == 'human'), default=-1)
    for index in range(start + 1, len(messages)):
        msg = messages[index]
        if getattr(msg, 'type', '') != 'ai' or not isinstance(msg.content, str):
            continue
        checked = validate_narrative(msg.content, evidence, channel='message')
        if checked.rejections:
            messages[index] = msg.model_copy(update={'content': checked.text or 'Você observa a cena e pondera seu próximo passo.'})
            audit.extend(checked.rejections)
    return messages, audit[-32:]
