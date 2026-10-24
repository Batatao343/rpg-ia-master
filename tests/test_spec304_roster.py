"""SPEC-304 Etapa 1: estado, modo, elenco (R1, R2, R26-R29)."""

from __future__ import annotations

import ast
import json
import pathlib

import pytest

from services import npc_world
from services import world_engine as we
from tests.spec304_helpers import (
    BRUNNA_ID,
    hook,
    known_npc,
    setup_env,
    step,
    waiting_state,
)


@pytest.fixture(autouse=True)
def _on(monkeypatch):
    setup_env(monkeypatch, "on")


def _with_npcs(st: dict, extra: dict) -> dict:
    st["npcs"] = {**st["npcs"], **extra}
    return st


def test_roster_priority_order():
    st = waiting_state()
    _with_npcs(
        st,
        {
            "Querida": known_npc("npc_q", "Querida", rel=9),
            "Conhecido": known_npc("npc_c", "Conhecido", rel=5, last_seen_turn=4),
        },
    )
    r = npc_world.roster(st)
    leader = "npc_comandante_thrace"
    assert r[0] == BRUNNA_ID  # party primeiro
    assert r.index("npc_q") < r.index(leader) < r.index("npc_c")  # querido < lider < conhecido
    first_key = next(k for k in r if k.startswith("npc_mv_") and k != BRUNNA_ID)
    assert r.index("npc_c") < r.index(first_key)  # npcs-chave por ultimo


def test_roster_cap_60():
    st = waiting_state()
    many = {f"N{i}": known_npc(f"npc_g{i:03d}", f"N{i}", rel=5) for i in range(120)}
    _with_npcs(st, many)
    assert len(npc_world.roster(st)) == 60


def test_roster_excludes_dead():
    st = waiting_state()
    _with_npcs(
        st,
        {
            "Morto": known_npc("npc_dead", "Morto", rel=9, status="morto"),
            "Vivo": known_npc("npc_live", "Vivo", rel=9),
        },
    )
    r = npc_world.roster(st)
    assert "npc_dead" not in r and "npc_live" in r
    st["world_projection"] = {"entities": {"npc_comandante_thrace": {"alive": False}}}
    assert "npc_comandante_thrace" not in npc_world.roster(st)


def test_roster_stable_same_inputs():
    st = waiting_state()
    assert npc_world.roster(st) == npc_world.roster(st)


def test_out_of_roster_frozen_untouched():
    st = waiting_state()
    hook(st, 2)
    victim = next(k for k in st["npc_sim"]["roster"] if k.startswith("npc_mv_") and k != BRUNNA_ID)
    before = json.dumps(st["npc_sim"]["npcs"][victim]["pos"], sort_keys=True)
    # 80 conhecidos novos empurram os npcs-chave para fora do teto
    _with_npcs(st, {f"N{i}": known_npc(f"npc_g{i:03d}", f"N{i}") for i in range(80)})
    hook(st, 3)
    entry = st["npc_sim"]["npcs"][victim]
    assert victim not in st["npc_sim"]["roster"] and entry["frozen"] is True
    assert json.dumps(entry["pos"], sort_keys=True) == before  # congelado: nada muda
    assert all(r in st["npc_sim"]["npcs"] for r in st["npc_sim"]["roster"])
    assert "npc_g000" in st["npc_sim"]["roster"] and len(st["npc_sim"]["roster"]) == 60


def test_mode_off_noop_byte_identical(monkeypatch):
    setup_env(monkeypatch, "off")
    st = waiting_state()
    res = step(st, 1, 6)
    assert res.state_patch == {}
    assert not st.get("npc_sim") and not st.get("npc_beliefs")
    # identico a rodar SEM o hook registrado
    st2 = waiting_state()
    saved = list(we._HOOKS)
    try:
        we._HOOKS[:] = [h for h in we._HOOKS if h[0] != "npc_world"]
        res2 = step(st2, 1, 6)
    finally:
        we._HOOKS[:] = saved
    assert json.dumps(res.pending_events, sort_keys=True) == json.dumps(
        res2.pending_events, sort_keys=True
    )
    assert json.dumps(res.digest, sort_keys=True) == json.dumps(res2.digest, sort_keys=True)


def test_engine_off_forces_npc_world_off(monkeypatch):
    monkeypatch.setenv("RPG_WORLD_ENGINE", "off")
    monkeypatch.setenv("RPG_NPC_WORLD", "on")
    assert npc_world.mode() == "off"
    monkeypatch.setenv("RPG_WORLD_ENGINE", "shadow")
    assert npc_world.mode() == "off"


def test_legacy_save_initializes_all_home_no_retro():
    st = waiting_state(day=40)
    assert not st.get("npc_sim") and not st.get("npc_beliefs")
    hook(st, 41)
    sim = st["npc_sim"]
    assert sim["enabled_from_day"] == 41
    assert all(p["opened_day"] >= 41 for p in sim["perils"])
    # NPC ja morto continua morto para o jogador (crenca nasce do visivel)
    st["npcs"]["Morto"] = known_npc("npc_dead", "Morto", status="morto")
    from services.npc_layers import visible_npc_view

    view = {v["name"]: v for v in visible_npc_view(st["npcs"], st)}
    assert view["Morto"]["status"] == "morto"


def test_save_load_roundtrip_npc_sim_and_beliefs(tmp_path, monkeypatch):
    import persistence

    monkeypatch.setenv("RPG_RUNTIME_PROFILE", "legacy")
    monkeypatch.setattr(persistence, "SAVES_DIR", str(tmp_path))
    st = waiting_state()
    for d in range(2, 30):
        step(st, d - 1, d)
    st["npc_beliefs"] = {"npc_x": {"status_known": "morto", "as_of_day": 3}}
    state = {
        "game_id": "11111111-2222-4333-8444-555555555304",
        "messages": [],
        "player": {},
        "world": {},
        "npc_sim": st["npc_sim"],
        "npc_beliefs": st["npc_beliefs"],
    }
    assert persistence.save_game_state(state)
    loaded = persistence.load_game_state(
        persistence.save_path("11111111-2222-4333-8444-555555555304")
    )
    assert loaded["npc_sim"] == st["npc_sim"] and loaded["npc_beliefs"] == st["npc_beliefs"]
    # save antigo (sem as chaves) carrega {}
    legacy = persistence._raw_to_state({"game_id": "old", "player": {}, "world": {}})
    assert (
        legacy["npc_sim"] == {} and legacy["npc_beliefs"] == {} and legacy["npc_sim_shadow"] == {}
    )


def test_npc_sim_size_bound():
    st = waiting_state()
    for d in range(2, 121):
        step(st, d - 1, d)
    assert len(npc_world.roster(st)) <= 60
    assert len(json.dumps(st["npc_sim"])) < 50_000  # 60 entradas + perigos + anel
    assert len(st["npc_sim"]["perils"]) <= 30 + 3
    assert len(st["npc_sim"]["tick_log"]) <= 30


def test_keys_in_gamestate_typeddict():
    from state import GameState

    assert {"npc_sim", "npc_sim_shadow", "npc_beliefs"} <= GameState.__annotations__.keys()


def test_no_global_random_in_npc_modules():
    root = pathlib.Path(__file__).resolve().parents[1] / "services"
    for name in ("npc_world.py", "npc_perils.py"):
        tree = ast.parse((root / name).read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                assert all(a.name != "random" for a in node.names), name
            if isinstance(node, ast.ImportFrom):
                assert node.module != "random", name
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and isinstance(node.func.value, ast.Name)
            ):
                assert node.func.value.id != "random", name
