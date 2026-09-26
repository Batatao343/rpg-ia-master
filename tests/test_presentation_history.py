from langchain_core.messages import AIMessage, HumanMessage
import pytest

from services.presentation_history import record_history, history_page, message_kind


def test_paginated_history_deduplicates_and_rejects_cursor_after_restore():
    state = {'game_id': 'test', 'world': {'turn_count': 1},
             'messages': [HumanMessage('Olho'), AIMessage('Chove')], 'next': 'storyteller'}
    record_history(state, 'Chove')
    record_history(state, 'Chove')
    page = history_page(state, limit=1)
    assert page['entries'][0]['role'] == 'player'
    assert history_page(state, cursor=page['next_cursor'])['entries'][0]['text'] == 'Chove'
    assert len(state['presentation_history']) == 2
    state['continuity'] = {'timeline_epoch': 1}
    with pytest.raises(ValueError):
        history_page(state, cursor=page['next_cursor'])


def test_legacy_history_explicitly_marks_incompleteness():
    page = history_page({'messages': [HumanMessage('Olho'), AIMessage('Chove')]})
    assert page['partial_history'] is True
    assert len(page['entries']) == 2


def test_kind_is_not_inferred_from_quotes_or_item_mentions():
    assert message_kind({'next': 'storyteller', 'messages': [AIMessage('"Um item!" 💰')]}) == 'STORY'
    assert message_kind({'next': 'npc_actor', 'messages': [AIMessage('Olá')]}) == 'NPC'
