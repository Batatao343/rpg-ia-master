"""SPEC-205 R7-R10: consulta PURA de alvos válidos e motivo de indisponibilidade.

Sem LLM, sem I/O, sem mutação de estado. Reaproveita as mesmas regras que o
motor revalida no uso (`cards.can_use_card`, `conflict_turn._invalid_target_reason`
via `_targetable`/`occlusion_attack_modifier`) — o frontend nunca recalcula regra.

Ids de alvo: `"player"`, `enemy.id` (= `participant_id` do manifesto SPEC-203) e
`id`/nome de aliado (party formal ou transitório de cena).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

from services import cards
from services import conflict_scene as cs
from services.conflict_turn import _SUPPORT_EFFECTS, _targetable

PLAYER_ID = "player"

# Enum fechado (R8). `out_of_zone` é reservado: a cena atual não impõe restrição
# de alcance a Cartas, então hoje nunca é emitido (ver spec, R8).
INVALID_REASONS = (
    "not_prepared",
    "spent_frequency",
    "no_entropy",
    "cooldown",
    "no_valid_target",
    "target_dead",
    "target_hidden",
    "out_of_zone",
    "not_your_turn",
    "combat_inactive",
    "fora_de_combate",  # SPEC-353 R37: utilitária não age no conflito
)

MANEUVERS = ("engajar", "desengajar", "guardar", "esconder", "procurar")
# Manobras que miram um participante hostil.
_TARGETED_MANEUVERS = {"engajar", "procurar"}


@dataclass
class TargetingResult:
    valid_targets: list[str] = field(default_factory=list)
    invalid_reason: str | None = None

    def as_dict(self) -> dict:
        return {"valid_targets": list(self.valid_targets), "invalid_reason": self.invalid_reason}


def _enemies(state: dict) -> list[dict]:
    return [e for e in (state.get("enemies") or []) if isinstance(e, dict)]


def _enemy_id(enemy: dict) -> str:
    return str(enemy.get("id") or enemy.get("name") or "")


def friendly_ids(state: dict) -> list[str]:
    """Herói + aliados presentes (party ativa e aliados transitórios de cena)."""
    import party as party_mod

    ids = [PLAYER_ID]
    for ally in party_mod.backfill_party(state.get("party") or []):
        if isinstance(ally, dict) and ally.get("active") and _targetable(ally):
            ids.append(str(ally.get("id") or ally.get("name")))
    meta = state.get("combat") or {}
    enemy_refs = [str(v) for e in _enemies(state) for v in (e.get("id"), e.get("name")) if v]
    # Mesma regra do motor (agents/combat.py): lista vazia também recalcula.
    transient = meta.get("scene_allies") or party_mod.scene_allies(state, excluded=enemy_refs)
    for ally in transient or []:
        if isinstance(ally, dict) and _targetable(ally):
            aid = str(ally.get("id") or ally.get("name"))
            if aid not in ids:
                ids.append(aid)
    return ids


def _combat_gate(state: dict) -> str | None:
    if not (state.get("combat") or {}).get("active"):
        return "combat_inactive"
    if state.get("death_pending") or state.get("game_over"):
        return "not_your_turn"
    return None


def _enemy_targets(state: dict) -> TargetingResult:
    """Inimigos vivos e miráveis (ocultação) a partir do herói."""
    enemies = _enemies(state)
    alive = [e for e in enemies if _targetable(e)]
    if not alive:
        return TargetingResult([], "target_dead")
    scene = (state.get("combat") or {}).get("scene") or {}
    visible: list[str] = []
    for enemy in alive:
        eid = _enemy_id(enemy)
        if scene.get("positions", {}).get(PLAYER_ID):
            if not cs.occlusion_attack_modifier(scene, PLAYER_ID, eid)["can_target"]:
                continue
        visible.append(eid)
    if not visible:
        return TargetingResult([], "target_hidden")
    return TargetingResult(visible, None)


def valid_targets_for_card(state: dict, card_id: str) -> TargetingResult:
    """Alvos válidos e motivo de indisponibilidade de uma Carta do jogador."""
    gate = _combat_gate(state)
    if gate:
        return TargetingResult([], gate)
    player = state.get("player") or {}
    card = cards.get_card(card_id) or {}
    if card.get("tipo") == "utilitaria":  # SPEC-353 R37: sem efeito no conflito
        return TargetingResult([], "fora_de_combate")
    prepared = set(player.get("prepared_cards") or [])
    virtude_ids = {vc.get("card_id") for vc in (player.get("virtue_cards") or [])}
    if card_id not in prepared and card_id not in virtude_ids:
        return TargetingResult([], "not_prepared")
    if card.get("tipo") != "ativa":
        # Reações/passivas não são jogadas da mão: sem alvo, sem bloqueio.
        return TargetingResult([], None)
    counter = cards.FREQ_COUNTER.get(str(card.get("frequencia", "livre")))
    if counter and int(((player.get("card_usage") or {}).get(card_id) or {}).get(counter, 0)) >= 1:
        return TargetingResult([], "spent_frequency")
    if not cards.can_use_card(player, card_id):
        return TargetingResult([], "no_entropy")
    import combat_mechanics as cm

    if cm.has_control(player, "silence"):
        # Bloqueio temporário (silêncio): o motor recusaria a Carta.
        return TargetingResult([], "cooldown")
    kind = str((card.get("efeito") or {}).get("kind") or "")
    if kind in _SUPPORT_EFFECTS:
        return TargetingResult(friendly_ids(state), None)
    result = _enemy_targets(state)
    if not result.valid_targets and result.invalid_reason is None:
        result.invalid_reason = "no_valid_target"
    return result


def basic_action_targeting(state: dict, kind: str, maneuver: str | None = None) -> TargetingResult:
    """Ataque básico, passar, fugir e manobras táticas."""
    gate = _combat_gate(state)
    if gate:
        return TargetingResult([], gate)
    if kind == "attack" or (kind == "maneuver" and maneuver in _TARGETED_MANEUVERS):
        return _enemy_targets(state)
    return TargetingResult([], None)


def basic_actions(state: dict) -> list[dict]:
    """`combat.basic_actions[]` (R7): ataque, manobras, passar e fugir."""
    out: list[dict] = []
    for kind, maneuver in (
        [("attack", None)] + [("maneuver", m) for m in MANEUVERS] + [("pass", None), ("flee", None)]
    ):
        row: dict = {"kind": kind}
        if maneuver:
            row["maneuver"] = maneuver
        row.update(basic_action_targeting(state, kind, maneuver).as_dict())
        row["cost"] = 0
        out.append(row)
    return out


def card_targeting(state: dict, card_id: str) -> dict:
    return valid_targets_for_card(state, card_id).as_dict()


def check_declared_target(
    state: dict,
    *,
    card_id: str | None,
    action_kind: str | None,
    maneuver: str | None,
    target_id: str | None,
) -> str | None:
    """R9: motivo de rejeição de borda para um `target_id` explícito, ou None.

    Só rejeita por razão relativa ao ALVO (alvo fora da lista ou sem alvo
    válido); economia (Entropia/frequência) segue com o motor, que já não cobra
    nada se o alvo é inválido (SPEC-232)."""
    if not target_id or not (state.get("combat") or {}).get("active"):
        return None
    if card_id:
        result = valid_targets_for_card(state, card_id)
    elif action_kind == "attack" or (action_kind == "maneuver" and maneuver in _TARGETED_MANEUVERS):
        result = basic_action_targeting(state, action_kind, maneuver)
    else:
        return None
    if target_id in result.valid_targets:
        return None
    if result.invalid_reason in (None, "no_valid_target", "target_dead", "target_hidden"):
        if result.valid_targets or result.invalid_reason:
            return result.invalid_reason or "no_valid_target"
        return "no_valid_target"
    return None  # economia/estado: o motor decide sem cobrar
