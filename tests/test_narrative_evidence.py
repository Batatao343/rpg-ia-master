import copy

import pytest
from langchain_core.messages import AIMessage, HumanMessage


@pytest.fixture
def state():
    return {'game_id': 'test', 'player': {'name': 'Ari', 'inventory': []},
            'world': {'current_location': 'Nova Arcádia', 'current_location_id': 'nova_arcadia',
                      'turn_count': 3}, 'event_log': [], 'npcs': {}}


@pytest.mark.parametrize('channel', ['message', 'summary', 'chronicle', 'memory', 'context'])
def test_shared_contract_removes_false_death_and_arrival_preserving_atmosphere(state, channel):
    from services.narrative_evidence import build_evidence, validate_narrative
    before = copy.deepcopy(state)
    result = validate_narrative('Ari morreu. Você chegou a Brekmar. A chuva cobre as ruas.',
                                build_evidence(state), channel=channel)
    assert result.text == 'A chuva cobre as ruas.'
    assert {r['reason'] for r in result.rejections} == {'player_death', 'current_location'}
    assert state == before


@pytest.mark.parametrize('text', [
    'Ari não morreu.', 'Talvez Ari morreu.', 'Se Ari morreu, ninguém sabe.',
    'O guarda diz que Ari morreu.', 'Ontem você chegou a Brekmar.',
    'Você pretende viajar para Brekmar.', 'Ari deseja uma adaga.',
    'Você chegou a Nova Arcádia.', 'O fogo morreu na lareira.',
])
def test_non_assertions_and_valid_controls_survive(state, text):
    from services.narrative_evidence import build_evidence, validate_narrative
    result = validate_narrative(text, build_evidence(state), channel='message')
    assert result.text == text
    assert result.rejections == []


def test_archivist_checks_summary_chronicle_and_facts(monkeypatch, state):
    import agents.archivist as archive
    from services.memory_provenance import make_memory_fact, validate_memory_fact
    class Model:
        def with_structured_output(self, schema):
            return self
        def invoke(self, messages):
            return archive.MemoryUpdate(new_summary='Ari morreu. A chuva persiste.',
                important_facts=['Ari morreu.'], chronicle_entry='Ari morreu. O vento canta.')
    monkeypatch.setattr(archive, 'get_llm', lambda **kwargs: Model())
    monkeypatch.setattr(archive, 'add_memory_to_session', lambda *args, **kwargs: True)
    state.update(archive_due=True, messages=[HumanMessage('Olho a rua.'), AIMessage('Chove.')])
    out = archive.archive_node(state)
    assert 'morreu' not in out['narrative_summary']
    assert 'morreu' not in str(out.get('chronicle', []))
    assert validate_memory_fact(make_memory_fact('Você chegou a Brekmar.', provenance='inference'), state)[0] is None


def test_pending_event_is_not_proof_of_death(state):
    from services.narrative_evidence import build_evidence, validate_narrative
    state['pending_events'] = [{'type': 'player_died'}]
    assert validate_narrative('Ari morreu.', build_evidence(state), channel='message').text == ''
    state['event_log'] = [{'event_id': 'death', 'type': 'player_died', 'target_id': 'player'}]
    assert validate_narrative('Ari morreu.', build_evidence(state), channel='message').text == 'Ari morreu.'


def test_reflexive_pronoun_is_not_a_conditional_escape(state):
    from services.narrative_evidence import build_evidence, validate_narrative
    checked = validate_narrative('Você se encontra em Brekmar.', build_evidence(state), channel='message')
    assert checked.text == ''
    assert checked.rejections[0]['reason'] == 'current_location'
