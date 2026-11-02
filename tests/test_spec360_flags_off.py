"""SPEC-360 R25-R27: flags `off` byte-identicas, zero chamada LLM nova e latencia.

O golden (`tests/fixtures/spec360_flags_off_golden.json`) foi gravado na Etapa 0, ANTES de
qualquer codigo de produto da SPEC-360 (`SPEC360_REGEN=1` regrava; so o coordenador).
"""

from __future__ import annotations

import hashlib
import json
import os
import time
from pathlib import Path

import pytest

GOLDEN = Path(__file__).parent / "fixtures" / "spec360_flags_off_golden.json"
TURNS = 30


def _sha(obj) -> str:
    return hashlib.sha256(
        json.dumps(obj, ensure_ascii=False, sort_keys=True, default=str).encode("utf-8")
    ).hexdigest()[:16]


def _fingerprint(result) -> dict:
    turns = [
        [
            r.action,
            r.route,
            r.location_id,
            int(r.player_vitality),
            int(r.gold),
            int(r.player_level),
            bool(r.combat_started),
            bool(r.combat_ended),
            len(r.llm_events),
        ]
        for r in result.history
    ]
    st = result.final_state or {}
    msgs = [str(getattr(m, "content", m)) for m in st.get("messages") or []]
    world = dict(st.get("world") or {})
    return {
        "turns": turns,
        "messages": _sha(msgs),
        "world_clock": world.get("world_clock"),
        "location": world.get("current_location_id"),
        "bestiary_knowledge": _sha(st.get("bestiary_knowledge") or {}),
        "errors": len(result.errors),
    }


def _run(profile: str = "explorador", turns: int = TURNS):
    from playtest.runner import run_campaign

    return run_campaign(profile, turns=turns, seed=0, invariants=False)


def _flags(monkeypatch, fauna: str, sinais: str) -> None:
    monkeypatch.setenv("RPG_FAUNA", fauna)
    monkeypatch.setenv("RPG_FAUNA_SINAIS", sinais)


def test_golden_flags_off_byte_identico(monkeypatch):
    """R25: com as duas flags `off`, 30 turnos do `explorador` igualam o golden da Etapa 0."""
    _flags(monkeypatch, "off", "off")
    fp = _fingerprint(_run())
    if os.getenv("SPEC360_REGEN") == "1":
        GOLDEN.parent.mkdir(parents=True, exist_ok=True)
        GOLDEN.write_text(
            json.dumps(fp, ensure_ascii=False, indent=1, sort_keys=True) + "\n", encoding="utf-8"
        )
        pytest.skip("golden regravado")
    golden = json.loads(GOLDEN.read_text(encoding="utf-8"))
    assert fp == golden


def _count_invokes(monkeypatch) -> list[int]:
    import mock_llm

    calls = [0]
    orig, orig_s = mock_llm.MockLLM.invoke, mock_llm._StructuredMock.invoke

    def _inv(self, messages):
        calls[0] += 1
        return orig(self, messages)

    def _inv_s(self, messages):
        calls[0] += 1
        return orig_s(self, messages)

    monkeypatch.setattr(mock_llm.MockLLM, "invoke", _inv)
    monkeypatch.setattr(mock_llm._StructuredMock, "invoke", _inv_s)
    return calls


def test_zero_chamada_llm_nova(monkeypatch):
    """R26: 30 turnos do `explorador`, flags `on` vs `off`, mesma seed: mesma contagem de invoke."""
    calls = _count_invokes(monkeypatch)
    _flags(monkeypatch, "off", "off")
    _run()
    off = calls[0]
    calls[0] = 0
    _flags(monkeypatch, "on", "on")
    result = _run()
    assert calls[0] == off
    assert not result.errors


def test_latencia_por_chamada(monkeypatch):
    """R27: eco_multiplier + scene_block + day_hook < 20 ms por chamada (media); bloco <= 60
    tokens (len/4)."""
    import gamedata
    import world_utils as wu
    from services import fauna, world_engine

    _flags(monkeypatch, "on", "on")
    monkeypatch.setenv("RPG_WORLD_ENGINE", "on")
    ctx = fauna.EcoCtx("na_anel_lama", "nova_arcadia", "Noite", "outono", {}, 10)
    entries = list(fauna.load().values())
    t0 = time.perf_counter()
    for e in entries * 5:
        fauna.eco_multiplier(e, ctx)
    eco_ms = 1000 * (time.perf_counter() - t0) / (len(entries) * 5)
    sim: dict = {}
    t0 = time.perf_counter()
    for d in range(1, 21):
        world = {"current_location_id": "na_anel_lama", "world_clock": {"day": d}}
        fauna.day_hook(
            world_engine.DayContext("g", d, sim, {}, world, [], world_engine.day_rng("g", d, "x"))
        )
    hook_ms = 1000 * (time.perf_counter() - t0) / 20
    state = {"world": {"current_location_id": "na_anel_lama", "world_clock": {"day": 20}}}
    t0 = time.perf_counter()
    blocks = []
    for _ in range(20):
        block, upd = fauna.scene_block({**state, "world_sim": sim})
        if upd:
            sim = upd["world_sim"]
        if block:
            blocks.append(block)
    scene_ms = 1000 * (time.perf_counter() - t0) / 20
    t0 = time.perf_counter()
    loc = gamedata.get_location("na_anel_lama")
    for t in range(20):
        wu.encounter_distribution(loc, 3, t, world=state["world"], world_sim=sim)
    dist_ms = 1000 * (time.perf_counter() - t0) / 20
    assert eco_ms < 20 and hook_ms < 20 and scene_ms < 20 and dist_ms < 50
    assert all(len(b) / 4 <= 60 for b in blocks)


_LAMA_ACTS = ["olho a viela", "descanso aqui", "olho em volta", "sigo o rastro", "descanso"]


def test_campanha_na_lama_exercita_fauna_sem_chamada_extra(monkeypatch):
    """P1-2 (Sol), R26/R29 com a fauna atuando: campanha MockLLM pelo grafo no Anel de Lama
    (perigo forçado 4, motor de mundo `on`). A cada turno, o MESMO estado roda também com as
    flags `off`: o turno `on` nunca chama a LLM mais vezes que o `off` (na caça, só a abertura
    do combate que ela abre). Houve sinal, conversão
    ou caça e encontro de fauna; o invariante `fauna_presenca_valida` não acusa nada."""
    import copy
    import random

    from langchain_core.messages import HumanMessage

    from main import app
    from playtest.invariants import check_fauna
    from playtest.runner import _build_initial_state
    from services import fauna

    monkeypatch.setenv("RPG_WORLD_ENGINE", "on")
    calls = _count_invokes(monkeypatch)
    state = _build_initial_state("explorador", 3, start_level=3)
    state["world"].update(
        {
            "current_location_id": "na_anel_lama",
            "current_location": "Anel de Lama",
            "danger_overrides": {"na_anel_lama": 4},
        }
    )
    extra, violations, hunts, off_starts = [], [], [], []
    for t in range(30):
        busy = bool((state.get("combat") or {}).get("active"))
        text = "fujo do combate" if busy else _LAMA_ACTS[t % len(_LAMA_ACTS)]
        state["messages"] = list(state.get("messages") or []) + [HumanMessage(content=text)]
        _flags(monkeypatch, "off", "off")
        calls[0] = 0
        random.seed(1000 + t)  # o mesmo acaso nos dois ramos do turno
        off_out = app.invoke(copy.deepcopy(state), {"recursion_limit": 60})
        off_calls = calls[0]
        if not busy and (off_out.get("combat") or {}).get("active"):
            off_starts.append(off_calls)  # custo de um início de combate qualquer (`off`)
        _flags(monkeypatch, "on", "on")
        calls[0] = 0
        random.seed(1000 + t)
        state = app.invoke(state, {"recursion_limit": 60})
        # A caça (R20) troca um turno de história por um início de combate: as chamadas são as
        # de QUALQUER encontro (preparo, declaração e narração do combate) mais a do roteador,
        # que classifica o texto livre. Nenhuma é da fauna.
        hunt = text == "sigo o rastro" and bool((state.get("combat") or {}).get("active"))
        if hunt:
            hunts.append(calls[0])
        elif calls[0] > off_calls:
            extra.append((t, text, calls[0], off_calls))
        violations += check_fauna(state, None, t)
    summary = fauna.summary(state.get("world_sim"))
    rows = (state.get("world_sim") or {}).get("fauna", {}).get("presencas") or []
    assert summary["sinal"] >= 1
    assert summary["caca"] >= 1 or any(p["origem"] == "conversao" for p in rows)
    assert summary["encontro"] >= 1
    assert not violations
    assert not extra, extra
    assert off_starts  # houve encontro comum para comparar
    if hunts:
        assert max(hunts) <= max(off_starts) + 1, (hunts, off_starts)
