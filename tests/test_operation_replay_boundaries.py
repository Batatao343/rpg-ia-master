from contextlib import contextmanager
from uuid import uuid4

import pytest

from infrastructure.contracts import Conflict, Principal


class Pool:
    def __init__(self, row):
        self.row = row

    @contextmanager
    def connection(self):
        yield self

    def execute(self, *args):
        return self

    def fetchone(self):
        return self.row


@pytest.mark.parametrize('field', ['game_id', 'kind', 'request_hash'])
def test_receipt_rejects_reused_id_with_different_request(field):
    from infrastructure.postgres_turns import PostgresTurnCoordinator
    gid, op, owner = uuid4(), uuid4(), uuid4()
    row = {'status': 'completed', 'receipt': {'response': {'ok': True}},
           'game_id': gid, 'kind': 'turn', 'request_sha256': 'a' * 64}
    coordinator = PostgresTurnCoordinator(Pool(row))
    args = {'game_id': gid, 'kind': 'turn', 'request_hash': 'a' * 64}
    args[field] = uuid4() if field == 'game_id' else 'different'
    with pytest.raises(Conflict):
        coordinator.receipt(Principal(owner, 'test', str(owner)), op, **args)


def test_valid_receipt_does_not_depend_on_current_game_version():
    from infrastructure.postgres_turns import PostgresTurnCoordinator
    gid, op, owner = uuid4(), uuid4(), uuid4()
    row = {'status': 'completed', 'receipt': {'response': {'ok': True}},
           'game_id': gid, 'kind': 'turn', 'request_sha256': 'a' * 64}
    coordinator = PostgresTurnCoordinator(Pool(row))
    assert coordinator.receipt(Principal(owner, 'test', str(owner)), op,
        game_id=gid, kind='turn', request_hash='a' * 64) == row['receipt']


def test_claim_context_releases_even_http_errors():
    from services.turn_execution import operation_scope
    from fastapi import HTTPException
    failed = []
    class Coordinator:
        def fail(self, claim, code):
            failed.append(code)
    with pytest.raises(HTTPException):
        with operation_scope(Coordinator(), object()):
            raise HTTPException(409, 'death_pending')
    assert failed == ['HTTPException']
