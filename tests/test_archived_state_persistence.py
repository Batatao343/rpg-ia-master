"""An archived character cannot become playable by crossing a save boundary."""
from uuid import uuid4


def test_archived_flag_and_reason_survive_save_reload(tmp_path, monkeypatch):
    import persistence
    from state import GameState
    assert {'archived', 'archived_reason'} <= GameState.__annotations__.keys()
    monkeypatch.setenv('RPG_RUNTIME_PROFILE', 'legacy')
    monkeypatch.setattr(persistence, 'SAVES_DIR', str(tmp_path))
    state = {'game_id': str(uuid4()), 'messages': [], 'player': {}, 'world': {},
             'archived': True, 'archived_reason': 'Migração incompatível'}
    assert persistence.save_game_state(state)
    loaded = persistence.load_game_state(persistence.save_path(state['game_id']))
    assert loaded['archived'] is True
    assert loaded['archived_reason'] == state['archived_reason']


def test_archived_game_does_not_enter_graph_nodes(monkeypatch):
    import main
    called = []
    monkeypatch.setattr(main, 'action_guard_node', lambda state: called.append('unexpected') or {})
    graph = main.build_game_graph()
    result = graph.invoke({'game_id': str(uuid4()), 'archived': True,
                           'archived_reason': 'Migração', 'player': {}, 'world': {}})
    assert called == []
    assert result['archived'] is True
