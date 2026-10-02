"""Tiny opt-in product contracts; bounded to DeepSeek and never image generation."""
from __future__ import annotations

import json
import os
from types import SimpleNamespace
from uuid import uuid4

import pytest
from dotenv import load_dotenv
from langchain_core.messages import HumanMessage

load_dotenv(override=True)

pytestmark = pytest.mark.llm_contract


def test_real_storyteller_completes_eligible_beat_with_grounded_reward(
    monkeypatch, tmp_path,
):
    if os.getenv('RPG_AUDIT_REAL') != '1':
        pytest.skip('RPG_AUDIT_REAL=1 required')
    if not os.getenv('DEEPSEEK_API_KEY'):
        pytest.skip('DEEPSEEK_API_KEY absent')
    import llm_setup
    from agents import storyteller
    from services.turn_outcome import capture_baseline, finalize_outcome

    route_file = tmp_path / 'routes.json'
    route_file.write_text(json.dumps({tier.value: [['deepseek', 'deepseek-v4-flash']]
                                      for tier in llm_setup.ModelTier}), encoding='utf-8')
    monkeypatch.delenv('RPG_FORCE_MOCK', raising=False)
    monkeypatch.setenv('RPG_NO_MOCK', '1')
    monkeypatch.setenv('RPG_ROUTES', str(route_file))
    monkeypatch.setattr(llm_setup, 'STRUCTURED_SEMANTIC_MAX_ATTEMPTS', 3)
    llm_setup._CLIENT_CACHE.clear()
    calls = []
    llm_setup.set_llm_telemetry_hook(
        lambda provider, model, tier, latency, fell_back:
        calls.append((provider, model, tier.value, fell_back))
    )
    monkeypatch.setattr(storyteller, 'build_context_pack', lambda *a, **k: SimpleNamespace(
        lore_block='Nova Arcádia é uma cidade de Valoria.', memory_block='',
        world_state_block='O herói está em Nova Arcádia.'))
    monkeypatch.setattr(storyteller, 'simulate_world', lambda s, w, *a: (w, ''))
    monkeypatch.setattr(storyteller, 'check_encounter', lambda *a, **k: None)
    state = {
        'game_id': str(uuid4()), 'messages': [HumanMessage(content=(
            'Concluo agora a tarefa de observar o selo na praça e relato exatamente o que vi.'))],
        'player': {'name': 'Ari', 'class_name': 'Devoto do Abismo', 'level': 1,
                   'xp': 0, 'gold': 10, 'inventory': [], 'vitalidade': 8,
                   'max_vitalidade': 8},
        'world': {'current_location': 'Nova Arcádia', 'current_location_id': 'nova_arcadia',
                  'turn_count': 4, 'danger_level': 0, 'weather': 'claro',
                  'world_clock': {'day': 1, 'period': 'Manhã'}, 'visited': ['nova_arcadia']},
        'campaign_plan': {'beats': [{'description': 'Observar o selo na praça e relatar',
                                     'status': 'pending'}], 'current_step': 0},
        'npcs': {}, 'factions': [], 'faction_intel': {}, 'quests': [],
        'event_log': [], 'world_projection': {}, 'narrative_summary': '',
    }
    state['turn_baseline'] = capture_baseline(state)
    try:
        update = storyteller.storyteller_node(state)
    finally:
        llm_setup.set_llm_telemetry_hook(None)
        llm_setup._CLIENT_CACHE.clear()
    merged = {**state, **update}
    outcome = finalize_outcome(merged)
    assert calls and len(calls) <= 3
    assert all(row[0] == 'deepseek' and not row[3] for row in calls)
    assert update['messages'][-1].content.strip()
    assert update['campaign_plan']['beats'][0]['status'] == 'done'
    assert update['player']['xp'] == 150
    assert outcome['xp_delta'] == 150
