"""SPEC-185 owner-scoped, bounded read projection contract."""
from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from infrastructure.account_read_model import PostgresAccountReader
from infrastructure.contracts import Principal
from services.presentation_history import record_history


class Result:
    def __init__(self, rows):
        self.rows = rows

    def fetchall(self):
        return self.rows

    def fetchone(self):
        return self.rows[0] if self.rows else None


class Connection:
    def __init__(self, owner, rows):
        self.owner = owner
        self.rows = rows
        self.calls = []

    def execute(self, sql, params):
        self.calls.append((sql, params))
        assert self.owner in params, "every financial query needs the verified owner"
        return Result(self.rows)


class Pool:
    def __init__(self, connection):
        self.db = connection

    def connection(self):
        class Context:
            def __enter__(inner):
                return self.db

            def __exit__(inner, *_args):
                return False

        return Context()


def principal():
    owner = uuid4()
    return Principal(owner, "test", str(owner))


def test_history_attribution_is_one_batch_for_50_messages_and_checks_each_epoch():
    user = principal()
    game = uuid4()
    db = Connection(user.user_id, [
        {"presentation_entry_id": "old", "timeline_epoch": 0, "cost_milli": 42,
         "llm_cost_usd": "0.000000042", "events": 1, "exact": True},
        {"presentation_entry_id": "new", "timeline_epoch": 1, "cost_milli": None,
         "llm_cost_usd": "0.000000017", "events": 1, "exact": False},
        {"presentation_entry_id": "wrong", "timeline_epoch": 0, "cost_milli": 99,
         "llm_cost_usd": "0.000000099", "events": 1, "exact": True},
    ])
    reader = PostgresAccountReader(Pool(db))
    entries = [{"id": f"legacy-{i}", "epoch": 0, "role": "player"} for i in range(47)] + [
        {"id": "old", "epoch": 0, "role": "narrator"},
        {"id": "new", "epoch": 1, "role": "narrator"},
        {"id": "wrong", "epoch": 1, "role": "narrator"},
    ]
    costs = reader.history_costs(user, game, entries)
    assert costs["old"] == {"cost_milli": "42", "technical_cost_usd": "0.000000042",
                            "technical_cost_basis": "usage_ledger", "technical_cost_exact": True}
    assert costs["new"]["cost_milli"] is None
    assert costs["new"]["technical_cost_usd"] == "0.000000017"
    assert costs["new"]["technical_cost_exact"] is False
    assert "wrong" not in costs
    assert len(db.calls) == 1
    sql, params = db.calls[0]
    assert "t.owner_id=%s and t.game_id=%s" in sql
    assert "u.owner_id=%s" in sql and "r.owner_id=%s" in sql
    assert params == (user.user_id, game, ["old", "new", "wrong"],
                      user.user_id, user.user_id)


def test_record_history_returns_only_new_narrator_key_and_restore_gets_new_key():
    state = {"game_id": str(uuid4()), "world": {"turn_count": 4},
             "continuity": {"timeline_epoch": 0}, "messages": []}
    old = record_history(state, "A")
    assert old and record_history(state, "A") is None
    state["continuity"]["timeline_epoch"] = 1
    assert record_history(state, "B") != old


def test_account_reads_are_owner_scoped_and_keyset_bounded():
    user = principal()
    at = datetime(2026, 10, 9, tzinfo=timezone.utc)
    row = {"event_id": uuid4(), "created_at": at, "game_id": uuid4(),
           "category": "game", "operation_kind": "turn"}
    db = Connection(user.user_id, [row] * 21)
    reader = PostgresAccountReader(Pool(db))
    page = reader.usage(user, limit=20)
    assert len(page["items"]) == 20 and page["next_cursor"]
    assert "provider" not in page["items"][0] and "input_units" not in page["items"][0]
    sql, params = db.calls[0]
    assert "u.owner_id=%s" in sql and "limit %s" in sql and params[-1] == 21
    assert "created_at,u.event_id" in sql


def test_purchase_history_uses_signed_kind_and_stable_keyset():
    user = principal()
    at = datetime(2026, 10, 9, tzinfo=timezone.utc)
    rows = [{"entry_id": uuid4(), "entry_type": "refund", "amount_milli": 250,
             "created_at": at} for _ in range(3)]
    db = Connection(user.user_id, rows)
    page = PostgresAccountReader(Pool(db)).purchases(user, limit=2)
    assert len(page["items"]) == 2 and page["next_cursor"]
    assert page["items"][0]["kind"] == "refund"
    sql, params = db.calls[0]
    assert "entry_type in ('purchase','refund','reversal')" in sql
    assert "(created_at,entry_id)" in sql and params[-1] == 3


def test_series_has_server_filled_zero_bins_and_only_settlement_sql():
    user = principal()
    db = Connection(user.user_id, [])
    series = PostgresAccountReader(Pool(db)).series(user, "24h",
        now=datetime(2026, 10, 9, 12, tzinfo=timezone.utc))
    assert len(series["points"]) == 24
    assert series["totals"] == {"game": "0", "image": "0", "voice": "0"}
    assert all(point["game"] == point["image"] == point["voice"] == "0"
               for point in series["points"])
    assert "e.entry_type='settle'" in db.calls[0][0]
    assert "at time zone 'UTC'" in db.calls[0][0]
    assert "r.reference_type='speech_to_text'" in db.calls[0][0]


def test_series_totals_are_calculated_on_server():
    user = principal()
    start = datetime(2026, 10, 3, tzinfo=timezone.utc)
    db = Connection(user.user_id, [
        {"bucket": start, "category": "game", "amount_milli": 1250},
        {"bucket": start, "category": "image", "amount_milli": 500},
    ])
    series = PostgresAccountReader(Pool(db)).series(user, "7d",
        now=datetime(2026, 10, 9, 12, tzinfo=timezone.utc))
    assert series["totals"] == {"game": "1250", "image": "500", "voice": "0"}
    assert series["points"][0]["total"] == "1750"
