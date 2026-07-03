"""
world_simulator (Fase 2): eventos off-screen narrados em descanso/viagem.
Offline/determinístico (MockLLM via conftest). Cobre nota, clamp de perigo, guard e contexto.
"""
import gamedata
import agents.world_simulator as ws
from llm_setup import FallbackLLM


def _world(loc_id="nova_arcadia"):
    return {"current_location_id": loc_id, "current_location": "Nova Arcádia",
            "world_clock": {"day": 1, "period": "Manhã"}}


def test_simulate_world_returns_eco_note():
    state = {"game_id": "ws_test"}
    world, note = ws.simulate_world(state, _world(), gamedata.seed_factions(), {}, periods=2)
    assert note.startswith("[ECOS DO MUNDO]")
    assert isinstance(world, dict)


def test_simulate_world_danger_shift_zero_no_change():
    # mock devolve danger_shift=0 → não cria override
    state = {"game_id": "ws_test"}
    world, _ = ws.simulate_world(state, _world("pradaria_ruinas"), gamedata.seed_factions(), {}, periods=1)
    assert not world.get("danger_overrides")


def test_simulate_world_fallback_guard(monkeypatch):
    # FallbackLLM devolve AIMessage (não WorldPulse) → no-op, sem crash
    monkeypatch.setattr(ws, "get_llm", lambda *a, **k: FallbackLLM("indisponível"))
    world_in = _world()
    world, note = ws.simulate_world({"game_id": "x"}, world_in, gamedata.seed_factions(), {}, periods=1)
    assert note == "" and isinstance(world, dict)


def test_apply_danger_shift_clamps():
    w = ws._apply_danger_shift(_world("pradaria_ruinas"), "pradaria_ruinas", 1)  # base 2 → 3
    assert w["danger_overrides"]["pradaria_ruinas"] == 3
    w2 = ws._apply_danger_shift(_world("nova_arcadia"), "nova_arcadia", -1)  # base 1 → piso 1
    assert w2["danger_overrides"]["nova_arcadia"] == 1
    # teto 4: parte de um override 4
    w3 = ws._apply_danger_shift({"current_location_id": "x", "danger_overrides": {"x": 4}}, "x", 1)
    assert w3["danger_overrides"]["x"] == 4


def test_known_factions_ctx_respects_intel():
    facs = gamedata.seed_factions()
    assert "Nenhuma facção conhecida" in ws._known_factions_ctx(facs, {})
    ctx = ws._known_factions_ctx(facs, {"legiao_ferro": {"known": True}})
    assert "A Legião de Ferro" in ctx
    # fação não-conhecida não aparece
    assert "Bandos Nômades" not in ctx
