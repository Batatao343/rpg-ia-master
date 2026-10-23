"""SPEC-297 Etapa 8 - reuso no jogo B (R22-R26, R2, R34)."""

import pytest

import agents.npc as npc_mod
import agents.storyteller as st
import persistence
from services import shared_pool as sp
from services.shared_pool_models import PoolNamespace, PoolStatus, fold_name
from tests.spec297_support import entry, make_store, npc_doc, seed

LOC = "na_anel_lama"  # regiao nova_arcadia


@pytest.fixture
def on(monkeypatch):
    monkeypatch.setenv("RPG_SHARED_POOL", "on")
    monkeypatch.setenv("RPG_POOL_REUSE_RATE", "1")
    sp.reset_default_store()
    yield
    sp.reset_default_store()


def state(game="game-b", turn=5, npcs=None, used=None, loc=LOC):
    return {
        "game_id": game,
        "world": {"turn_count": turn, "current_location_id": loc},
        "npcs": npcs or {},
        "pool_used": used or [],
    }


def seeded(tmp_path, n=3, region="nova_arcadia", game="game-a"):
    store = make_store(tmp_path)
    for i in range(n):
        store.insert(
            entry(
                name=f"Pessoa Pool{i}",
                status=PoolStatus.PROMOTED,
                game=game,
                region=region,
                entry_id=f"pool_npc_{i}",
                sd=seed(desire_id="des_cura"),
            )
        )
    return store


def test_cast_block_seeded_and_rate(tmp_path, monkeypatch, on):
    store = seeded(tmp_path)
    a = sp.cast_block(state(), store=store)
    b = sp.cast_block(state(), store=store)
    assert a == b and a[0].startswith("<ELENCO_POSSIVEL>") and 1 <= len(a[1]) <= 2
    monkeypatch.setenv("RPG_POOL_REUSE_RATE", "0.5")
    offered = sum(1 for t in range(1000) if sp.cast_entries(state(turn=t), store=store))
    assert abs(offered / 1000 - 0.5) <= 0.05


def test_cast_only_same_region(tmp_path, on):
    store = seeded(tmp_path, region="brekmar")
    assert sp.cast_block(state(), store=store) == ("", [])
    assert sp.cast_block(state(loc="brekmar"), store=store)[1]


def test_cast_excludes_pool_used_and_known(tmp_path, on):
    store = seeded(tmp_path, n=3)
    st_ = state(
        used=["pool_npc_0"],
        npcs={"Pessoa Pool1": {"name": "Pessoa Pool1"}},
    )
    for turn in range(30):
        st_["world"]["turn_count"] = turn
        ids = sp.cast_block(st_, store=store)[1]
        assert set(ids) <= {"pool_npc_2"}


def test_cast_never_offers_own_games_npcs(tmp_path, on):
    store = seeded(tmp_path, game="game-b")
    assert sp.cast_block(state(game="game-b"), store=store) == ("", [])


def test_shadow_never_offers_cast(tmp_path, monkeypatch, on):
    store = seeded(tmp_path)
    monkeypatch.setenv("RPG_SHARED_POOL", "shadow")
    assert sp.cast_block(state(), store=store) == ("", [])


def test_materialize_no_llm_call(monkeypatch, tmp_path, on):
    store = seeded(tmp_path, n=1)
    pooled = store.get("pool_npc_0")

    def boom(*a, **k):
        raise AssertionError("LLM/geração não pode ser chamada na materialização")

    monkeypatch.setattr(st, "generate_new_npc", boom)
    used: list = []
    out = st._with_new_npc(
        {},
        pooled.name,
        "Anel de Lama",
        "cena",
        game_id="game-b",
        home_id=LOC,
        turn=5,
        cast=[pooled],
        pool_used_out=used,
    )
    npc = out[pooled.name]
    assert used == ["pool_npc_0"] and npc["pool_entry_id"] == "pool_npc_0"
    assert npc["in_scene"] is True and npc["hidden_traits"] is not None
    assert npc["max_vitalidade"] > 0


def test_materialize_allowlist_only(tmp_path, on):
    dirty = npc_doc(
        "Pessoa Suja",
        relationship=99,
        memory=["segredo do jogo A"],
        status="morto",
        dead=True,
        died_turn=4,
        hidden_traits=["x"],
        revealed_traits=["y"],
        interaction_count=9,
        knowledge={"a": 1},
        in_scene=True,
        last_seen_turn=3,
        cargo="rei",
    )
    e = entry(name="Pessoa Suja", status=PoolStatus.PROMOTED, doc=dirty, entry_id="pool_npc_d")
    out = sp.materialize_npc(e, game_id="game-b", home_location_id=LOC)
    assert out.get("status", "ativo") == "ativo"  # ficha v4 do motor, não o "morto" do jogo A
    for banned in (
        "memory",
        "dead",
        "died_turn",
        "hidden_traits",
        "revealed_traits",
        "interaction_count",
        "knowledge",
        "in_scene",
        "last_seen_turn",
        "cargo",
    ):
        assert banned not in out, banned
    assert out["relationship"] == out["initial_relationship"] == 5


def test_dead_in_game_a_alive_in_game_b(tmp_path, on):
    store = seeded(tmp_path, n=1)
    pooled = store.get("pool_npc_0")
    # jogo A matou o NPC no próprio save; a base não muda (R26)
    game_a_npc = {
        **sp.materialize_npc(pooled, game_id="game-a"),
        "dead": True,
        "status": "morto",
        "relationship": -50,
    }
    assert game_a_npc["dead"] is True
    again = store.get("pool_npc_0")
    assert again == pooled
    b = sp.materialize_npc(again, game_id="game-b")
    assert not b.get("dead") and b.get("status") != "morto"
    assert b["relationship"] == b["initial_relationship"]


def test_player_cannot_summon_pool_npc_by_name(monkeypatch, tmp_path, on):
    store = seeded(tmp_path, n=1)
    pooled = store.get("pool_npc_0")
    sp._default_store = store
    db = npc_mod.load_npc_db("game-b")
    assert pooled.name not in {v.get("name") for v in db.values()}
    assert (
        sp.get_by_name_fold(PoolNamespace.NPC, pooled.name, game_id="game-b", store=store)
        is not None
    )
    # sem estar no elenco oferecido, _with_new_npc NÃO copia da base: gera (mock) um novo
    calls = []
    monkeypatch.setattr(
        st,
        "generate_new_npc",
        lambda name, **k: calls.append(name) or {"name": name, "role": "x", "persona": "p"},
    )
    st._with_new_npc(
        {}, pooled.name, "Anel", "cena", game_id="game-b", home_id=LOC, turn=1, cast=[]
    )
    assert calls == [pooled.name]


def test_flag_flip_on_to_off_mid_campaign(tmp_path, monkeypatch, on):
    store = seeded(tmp_path)
    st_ = state(used=["pool_npc_0"])
    assert sp.cast_block(st_, store=store)[1]
    monkeypatch.setenv("RPG_SHARED_POOL", "off")
    assert sp.cast_block(st_, store=store) == ("", [])
    assert not sp.enabled()
    # materializado antes do flip continua no save: nada a apagar
    assert st_["pool_used"] == ["pool_npc_0"]


def test_old_save_without_pool_used_loads():
    raw = persistence._raw_to_state({"game_id": "g-old", "player": {}, "world": {}})
    assert raw.get("pool_used", []) == []
    raw2 = persistence._raw_to_state({"game_id": "g", "pool_used": ["pool_npc_1"]})
    assert raw2["pool_used"] == ["pool_npc_1"]


def test_fold_name_helper():
    assert fold_name("  Ção  Bá ") == "cao ba"
