"""Mutation contracts through authenticated HTTP and actual local Postgres."""
import os
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urlsplit
from uuid import UUID, uuid4

import httpx
import pytest

from infrastructure.contracts import Principal
from tests.test_postgres_jobs_local import infra  # noqa: F401

pytestmark = pytest.mark.infra_local


@pytest.fixture
def campaign(infra):
    base = os.getenv('RPG_AUDIT_BROWSER_URL')
    if not base:
        pytest.skip('local audit API required')
    assert urlsplit(base).hostname in {'127.0.0.1', 'localhost'}
    store, _, _, _ = infra
    with httpx.Client(base_url=base, timeout=30, trust_env=False) as client:
        signup = client.post('/auth/signup', json={'email': f'mutation-{uuid4().hex}@example.test',
                                                  'password': 'LocalAuditOnly-2026!'})
        assert signup.status_code == 200, signup.text
        client.headers.update({'Origin': base, 'X-CSRF-Token': signup.json()['csrf_token']})
        owner = UUID(client.get('/auth/config').json()['user_id'])
        principal = Principal(owner, 'test', str(owner), local=True)
        options = client.get('/data/options').json()
        created = client.post('/game/new', json={'name': 'Mutation audit',
            'race': options['races'][0], 'class_name': options['classes'][0],
            'region': options['regions'][0], 'action_id': str(uuid4())})
        assert created.status_code == 200, created.text
        game = UUID(created.json()['game_id'])
        try:
            yield client, store, principal, game
        finally:
            store.delete(principal, game)


@pytest.mark.parametrize('kind', ['death', 'equip', 'levelup'])
def test_completed_mutation_replays_before_changed_preconditions(campaign, kind):
    client, store, principal, game = campaign
    stored = store.get(principal, game)
    state = stored.state
    state['death_pending'] = kind == 'death'
    if kind == 'levelup':
        state['player']['pending_choices'] = [{'id': 'audit-virtude', 'level': 2, 'kind': 'virtude'}]
        state['player']['virtudes']['forca'] = 1
    store.save(principal, game, stored.version, state)
    fields = {'death': {'choice': 'accept'}, 'equip': {'unequip_slot': 'weapon'},
              'levelup': {'choice_id': 'audit-virtude', 'virtude': 'forca'}}[kind]
    payload = {'game_id': str(game), 'action_id': str(uuid4()), **fields}
    first = client.post(f'/game/{kind}', json=payload)
    assert first.status_code == 200, first.text
    committed = store.get(principal, game)
    state = committed.state
    state['archived'] = True
    modified = store.save(principal, game, committed.version, state)
    replay = client.post(f'/game/{kind}', json=payload)
    assert replay.status_code == 200, replay.text
    assert replay.json() == first.json()
    assert store.get(principal, game).version == modified.version
    new_request = client.post(f'/game/{kind}', json={**payload, 'action_id': str(uuid4())})
    assert new_request.status_code == 409
    # Rejected precondition must not strand the operation's game lease.
    current = store.get(principal, game)
    current.state['archived'] = False
    current.state['game_over'] = False
    current.state['death_pending'] = False
    store.save(principal, game, current.version, current.state)
    released = client.post('/game/equip', json={'game_id': str(game),
        'action_id': str(uuid4()), 'unequip_slot': 'weapon'})
    assert released.status_code == 200, released.text


def test_two_simultaneous_mutations_commit_only_once(campaign):
    client, store, principal, game = campaign
    before = store.get(principal, game)
    cookies = dict(client.cookies)
    headers = dict(client.headers)
    def mutate(operation):
        with httpx.Client(base_url=str(client.base_url), cookies=cookies,
                          headers=headers, timeout=30, trust_env=False) as contender:
            return contender.post('/game/equip', json={'game_id': str(game),
                'action_id': str(operation), 'unequip_slot': 'weapon'}).status_code
    with ThreadPoolExecutor(max_workers=2) as executor:
        statuses = list(executor.map(mutate, [uuid4(), uuid4()]))
    assert sorted(statuses) == [200, 409]
    assert store.get(principal, game).version == before.version + 1
