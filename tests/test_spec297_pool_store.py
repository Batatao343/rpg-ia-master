"""SPEC-297 Etapa 1 - contrato e store legacy (R9-R12, R33)."""

from datetime import timedelta

import pytest

from infrastructure.shared_pool_store import PoolImmutableError
from services import shared_pool as sp
from services.shared_pool_models import PoolNamespace, PoolStatus
from tests.spec297_support import NOW, OWNER_A, OWNER_B, entry, make_store, npc_doc, seed


def _submit(store, name="Aldric Vento", game="game-a", owner=OWNER_A, **kw):
    return sp.submit(
        PoolNamespace.NPC,
        npc_doc(name),
        game_id=game,
        region_id="nova_arcadia",
        name_origin=kw.pop("name_origin", "narrator"),
        seed=kw.pop("seed", seed()),
        store=store,
        now=NOW,
        owner_id=owner,
        **kw,
    )


def _cands(store, **kw):
    args = dict(
        region_id="nova_arcadia", exclude_ids=set(), exclude_names=set(), limit=5, store=store
    )
    args.update(kw)
    return sp.candidates(PoolNamespace.NPC, **args)


def test_submit_held_visible_only_in_origin_game(tmp_path, monkeypatch):
    monkeypatch.setenv("RPG_SHARED_POOL", "on")
    store = make_store(tmp_path)
    e = _submit(store, game="game-a", owner=OWNER_A)
    assert e.status == PoolStatus.HELD
    assert sp.visible_entry(e, game_id="game-a")
    # outro jogo do MESMO dono tampouco enxerga o hold
    assert not sp.visible_entry(e, game_id="game-a2")
    assert not sp.visible_entry(e, game_id="game-b")
    assert _cands(store) == []


def test_promoted_visible_to_others_only_with_flag_on(monkeypatch):
    p = entry(status=PoolStatus.PROMOTED)
    monkeypatch.setenv("RPG_SHARED_POOL", "shadow")
    assert not sp.visible_entry(p, game_id="game-z")
    monkeypatch.setenv("RPG_SHARED_POOL", "on")
    assert sp.visible_entry(p, game_id="game-z")


def test_entry_id_unique_for_same_name_in_two_games(tmp_path):
    store = make_store(tmp_path)
    a = _submit(store, game="game-a")
    b = _submit(store, game="game-b", owner=OWNER_B)
    assert a.entry_id != b.entry_id
    assert a.entry_id.startswith("pool_npc_")


def test_owner_daily_cap_marks_local_only(tmp_path, monkeypatch):
    monkeypatch.setenv("RPG_POOL_SUBMIT_PER_OWNER_DAY", "2")
    store = make_store(tmp_path)
    statuses = [_submit(store, name=f"Npc Numero {i}").status for i in range(4)]
    assert statuses == [
        PoolStatus.HELD,
        PoolStatus.HELD,
        PoolStatus.LOCAL_ONLY,
        PoolStatus.LOCAL_ONLY,
    ]


def test_player_named_and_seedless_are_local_only(tmp_path):
    store = make_store(tmp_path)
    assert _submit(store, name_origin="player").status == PoolStatus.LOCAL_ONLY
    assert _submit(store, seed=None, name="Sem Semente").status == PoolStatus.LOCAL_ONLY


def test_submit_requires_game_id(tmp_path):
    with pytest.raises(ValueError):
        sp.submit(
            PoolNamespace.NPC,
            npc_doc(),
            game_id="",
            region_id="nova_arcadia",
            name_origin="narrator",
            store=make_store(tmp_path),
        )


def test_submit_stores_shingle_hashes_not_text(tmp_path):
    store = make_store(tmp_path)
    text = "quero falar com o ferreiro velho da rua do cobre agora mesmo"
    e = _submit(store, player_inputs=[text])
    assert e.input_shingles
    assert "ferreiro velho" not in store.path.read_text(encoding="utf-8")


def test_hold_hours_sets_promote_after(tmp_path, monkeypatch):
    monkeypatch.setenv("RPG_POOL_HOLD_HOURS", "6")
    assert _submit(make_store(tmp_path)).promote_after == NOW + timedelta(hours=6)


def test_json_store_roundtrip_and_atomic_write(tmp_path):
    store = make_store(tmp_path)
    e = entry()
    store.insert(e)
    assert store.get(e.entry_id) == e
    assert not list(tmp_path.glob(".*.tmp"))
    with pytest.raises(ValueError):
        store.insert(e)
    assert make_store(tmp_path).get(e.entry_id).name == e.name


def test_promoted_content_is_immutable_but_status_changes(tmp_path):
    store = make_store(tmp_path)
    e = entry(status=PoolStatus.PROMOTED)
    store.insert(e)
    with pytest.raises(PoolImmutableError):
        store.update(e.entry_id, {"document": {"name": "outro"}})
    assert store.update(e.entry_id, {"status": "vetoed"}).status == PoolStatus.VETOED


def test_candidates_filters_region_and_limit(tmp_path, monkeypatch):
    monkeypatch.setenv("RPG_SHARED_POOL", "on")
    store = make_store(tmp_path)
    for i in range(6):
        store.insert(
            entry(name=f"Alguem Numero{i}", status=PoolStatus.PROMOTED, entry_id=f"pool_npc_{i}")
        )
    store.insert(
        entry(
            name="Outra Regiao", status=PoolStatus.PROMOTED, region="brekmar", entry_id="pool_npc_x"
        )
    )
    store.insert(entry(name="Ainda Hold", status=PoolStatus.HELD, entry_id="pool_npc_h"))
    got = _cands(store, exclude_ids={"pool_npc_0"}, exclude_names={"alguem numero1"}, limit=3)
    assert len(got) == 3
    assert all(e.region_id == "nova_arcadia" and e.status == PoolStatus.PROMOTED for e in got)
    assert {"pool_npc_0", "pool_npc_1"}.isdisjoint({e.entry_id for e in got})


def test_candidates_empty_unless_on(tmp_path, monkeypatch):
    store = make_store(tmp_path)
    store.insert(entry(status=PoolStatus.PROMOTED))
    for mode in ("off", "shadow"):
        monkeypatch.setenv("RPG_SHARED_POOL", mode)
        assert _cands(store) == []
