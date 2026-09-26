"""Art identity and per-arc spend limits must survive every state boundary."""
from uuid import uuid4


def test_art_reservations_and_budgets_survive_save_reload(tmp_path, monkeypatch):
    import persistence
    from state import GameState
    assert 'art_generation_ledger' in GameState.__annotations__
    assert 'art_arc_budgets' in GameState.__annotations__
    monkeypatch.setenv('RPG_RUNTIME_PROFILE', 'legacy')
    monkeypatch.setattr(persistence, 'SAVES_DIR', str(tmp_path))
    state = {'game_id': str(uuid4()), 'messages': [], 'player': {}, 'world': {},
             'art_generation_ledger': [{'generation_id': 'portrait', 'trigger_kind': 'player_portrait'}],
             'art_arc_budgets': {'arc': {'npc_generations_used': 2, 'epic_generation_used': True}}}
    assert persistence.save_game_state(state)
    loaded = persistence.load_game_state(persistence.save_path(state['game_id']))
    assert loaded['art_generation_ledger'] == state['art_generation_ledger']
    assert loaded['art_arc_budgets'] == state['art_arc_budgets']
