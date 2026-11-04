"""SPEC-372 R12 — com `RPG_FAUNA_TRAMAS` off (ou sem requisitos) nada muda."""

from __future__ import annotations

from services import fauna
from services import plot_threads as pt


def test_registrada_off_no_registro():
    import yaml

    with open("config/flags.yaml", encoding="utf-8") as fh:
        reg = yaml.safe_load(fh)
    flags = reg.get("flags", reg)
    assert flags["RPG_FAUNA_TRAMAS"]["default"] == "off"


def test_tramas_mode_exige_fauna_e_tramas(monkeypatch):
    pt.clear_cache()
    monkeypatch.setenv("RPG_FAUNA_TRAMAS", "on")
    monkeypatch.setenv("RPG_FAUNA", "on")
    monkeypatch.delenv("RPG_PLOT_THREADS", raising=False)
    assert fauna.tramas_mode() == "off"
    monkeypatch.setenv("RPG_PLOT_THREADS", "on")
    assert fauna.tramas_mode() == "on"
    monkeypatch.setenv("RPG_FAUNA", "off")
    assert fauna.tramas_mode() == "off"
    monkeypatch.setenv("RPG_FAUNA", "on")
    monkeypatch.setenv("RPG_FAUNA_TRAMAS", "off")
    assert fauna.tramas_mode() == "off"


def test_campanha_na_lama_mesma_contagem_de_invoke_on_off(monkeypatch):
    """R13: 12 turnos MockLLM no Anel de Lama; com `RPG_FAUNA_TRAMAS=on` o turno nunca chama
    a LLM mais vezes que com `off` (mesmo estado e mesma seed), e a invariante nao acusa nada."""
    import copy
    import random

    from langchain_core.messages import HumanMessage

    from main import app
    from playtest.invariants import check_fauna
    from playtest.runner import _build_initial_state
    from tests.test_spec360_flags_off import _count_invokes

    for k in ("RPG_WORLD_ENGINE", "RPG_FAUNA", "RPG_FAUNA_SINAIS", "RPG_PLOT_THREADS"):
        monkeypatch.setenv(k, "on")
    pt.clear_cache()
    calls = _count_invokes(monkeypatch)
    state = _build_initial_state("explorador", 3, start_level=3)
    state["world"].update(
        {
            "current_location_id": "na_anel_lama",
            "current_location": "Anel de Lama",
            "danger_overrides": {"na_anel_lama": 4},
        }
    )
    acts = ["olho a viela", "descanso aqui", "olho em volta", "sigo o rastro", "descanso"]
    violations = []
    for t in range(12):
        busy = bool((state.get("combat") or {}).get("active"))
        text = "fujo do combate" if busy else acts[t % len(acts)]
        state["messages"] = list(state.get("messages") or []) + [HumanMessage(content=text)]
        monkeypatch.setenv("RPG_FAUNA_TRAMAS", "off")
        calls[0] = 0
        random.seed(2000 + t)
        app.invoke(copy.deepcopy(state), {"recursion_limit": 60})
        off_calls = calls[0]
        monkeypatch.setenv("RPG_FAUNA_TRAMAS", "on")
        calls[0] = 0
        random.seed(2000 + t)
        state = app.invoke(state, {"recursion_limit": 60})
        assert calls[0] <= off_calls, (t, text, calls[0], off_calls)
        violations += check_fauna(state, None, t)
    assert not violations
