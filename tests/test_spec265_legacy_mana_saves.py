"""SPEC-265 (revisão Sol) — saves antigos com mana/stamina do jogador seguem carregando.

As chaves legadas podem existir em saves v3 (arquivados) e v4+; o motor as ignora,
a view da API não as expõe e o descanso não as recompõe nem quebra.
"""
from __future__ import annotations

from langchain_core.messages import AIMessage

import api
import persistence
import world_utils

_LEGACY = {"mana": 3, "max_mana": 10, "stamina": 2, "max_stamina": 20}
_KEYS = set(_LEGACY)


def _response_keys(state: dict) -> set:
    state = dict(state)
    state.setdefault("game_id", "g")
    state.setdefault("messages", [AIMessage(content="Tudo quieto.")])
    state.setdefault("world", {"current_location": "Arena"})
    return set(api.format_response(state).player_stats)


def test_save_v3_com_mana_stamina_arquiva_e_view_nao_expoe() -> None:
    raw = {"schema_version": 3, "player": {"hp": 20, "max_hp": 20, **_LEGACY}}
    migrated = persistence.migrate_state(raw)
    assert migrated["archived"] is True
    assert migrated["schema_version"] == persistence.SCHEMA_VERSION
    assert not _KEYS & _response_keys(migrated)


def test_save_v4_com_mana_stamina_round_trip_e_descanso() -> None:
    raw = {
        "schema_version": 4,
        "game_id": "g",
        "player": {"virtudes": {"corpo": 2}, "vitalidade": 4, "max_vitalidade": 10,
                   "hp": 4, "max_hp": 10, "entropy": 1, "max_entropy": 6, **_LEGACY},
        "party": [],
        "messages": [],
        "world": {"current_location": "Arena"},
    }
    state = persistence._raw_to_state(raw)
    assert not state.get("archived")
    assert not _KEYS & _response_keys(state)

    player, _world = world_utils.apply_rest(
        dict(state["player"]), world_utils.ensure_world({"current_location_id": "nova_arcadia"}))
    assert player["entropy"] == 6
    # chaves legadas ficam inertes: nem recompostas nem removidas pelo descanso
    assert {k: player[k] for k in _KEYS} == _LEGACY
