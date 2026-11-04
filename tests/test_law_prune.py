"""SPEC-377 item 1 — poda diaria de `wanted` decaido (hook `law` do motor de mundo)."""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from langchain_core.messages import HumanMessage

from services import law, law_day_hook, world_engine
from tests.spec299_helpers import base_state, commit, with_clock


@pytest.fixture(autouse=True)
def _on(monkeypatch):
    monkeypatch.setenv("RPG_LAW", "on")
    monkeypatch.setenv("RPG_WORLD_ENGINE", "on")
    monkeypatch.setattr(law, "_unit", lambda *a: 0.0)
    monkeypatch.setattr(law, "patrol_present", lambda *a, **k: False)


def _w(jid="codigo_de_ferro", *, heat=0, bounty=0, capital=False, last=0, known=None, shown=()):
    return {
        "jurisdiction_id": jid,
        "heat": heat,
        "bounty": bounty,
        "capital": capital,
        "last_crime_clock": last,
        "known_at": known if known is not None else {"nova_arcadia": 5},
        "signals_shown": list(shown),
        "hunters_last_clock": -1,
    }


def _ctx(state, day):
    return SimpleNamespace(state=state, day=day)


def _residual_state(clock=200):
    """Pos-suborno: heat decaiu a 0, bounty zerado, mas known_at/sinais ficaram."""
    state = with_clock(base_state("nova_arcadia"), clock)
    state["law_state"] = {
        "wanted": {
            "codigo_de_ferro": _w(known={"nova_arcadia": 5}, shown=("perguntaram_por_voce",))
        }
    }
    return state


def _crime_entregue(state):
    """Um furto em Nova Arcadia, entregue por patrulha (vira `wanted` no `turn_updates`)."""
    state = {**state, "npcs": {}}
    state, _rec, _why = commit(state, "furto")
    return {**state, **law.turn_updates(state)}


def test_residual_pos_suborno_sem_poda_vaza_para_o_crime_novo(monkeypatch):
    """Caracteriza o bug (W3): sem poda a noticia antiga vale e o sinal ja esta mostrado."""
    monkeypatch.setattr(law, "patrol_present", lambda *a, **k: True)
    w = _crime_entregue(_residual_state())["law_state"]["wanted"]["codigo_de_ferro"]
    assert w["known_at"]["nova_arcadia"] == 5  # min(): a noticia "ja chegou"
    assert "perguntaram_por_voce" in w["signals_shown"]


def test_pos_poda_crime_novo_comeca_do_zero(monkeypatch):
    """Inversao do teste acima (D1=a): com a poda, known_at e sinais recomecam."""
    monkeypatch.setattr(law, "patrol_present", lambda *a, **k: True)
    state = _residual_state()
    state = {**state, **law.daily_tick(state, state["world"]["world_clock"]["day"])}
    assert state["law_state"]["wanted"] == {}
    w = _crime_entregue(state)["law_state"]["wanted"]["codigo_de_ferro"]
    assert w["known_at"]["nova_arcadia"] != 5
    assert "perguntaram_por_voce" not in w["signals_shown"]


def test_pena_e_multa_ja_zeram_residuo():
    law_state = law.normalize_law({"wanted": {"codigo_de_ferro": _w(heat=50, bounty=30)}})
    law._clear_wanted(law_state, "codigo_de_ferro", keep_heat=0)
    w = law_state["wanted"]["codigo_de_ferro"]
    assert w["known_at"] == {} and w["signals_shown"] == [] and w["hunters_last_clock"] == -1


def test_daily_tick_poda_so_decaidas():
    state = {
        "world": {"world_clock": {"day": 40, "period": "Manhã"}},
        "law_state": {
            "wanted": {
                "codigo_de_ferro": _w(),  # decaida
                "lei_dos_clas": _w("lei_dos_clas", heat=60, capital=True),
                "colmeia": _w("colmeia", bounty=9),
            }
        },
    }
    kept = law.daily_tick(state, 40)["law_state"]["wanted"]
    assert set(kept) == {"lei_dos_clas", "colmeia"}
    assert law.daily_tick({**state, "law_state": {"wanted": kept}}, 40) == {}


def test_hook_registrado_post():
    rows = [h for h in world_engine._HOOKS if h[0] == "law"]
    assert rows and rows[0][1] == "post" and rows[0][3] is law_day_hook.day_hook


@pytest.mark.parametrize(
    ("engine", "lawmode", "has_state"),
    [("shadow", "on", True), ("off", "on", True), ("on", "off", True), ("on", "on", False)],
)
def test_hook_vazio_em_shadow_off_sem_state(monkeypatch, engine, lawmode, has_state):
    monkeypatch.setenv("RPG_WORLD_ENGINE", engine)
    monkeypatch.setenv("RPG_LAW", lawmode)
    res = law_day_hook.day_hook(_ctx(_residual_state() if has_state else None, 40))
    assert res.state_patch == {}


def test_hook_poda_em_on_e_nada_sem_mudanca():
    res = law_day_hook.day_hook(_ctx(_residual_state(), 40))
    assert res.state_patch["law_state"]["wanted"] == {}
    state = {**_residual_state(), "law_state": res.state_patch["law_state"]}
    assert law_day_hook.day_hook(_ctx(state, 41)).state_patch == {}


def test_leitura_derivada_identica():
    state = {
        "law_state": {
            "wanted": {
                "codigo_de_ferro": _w(),
                "lei_dos_clas": _w("lei_dos_clas", heat=80, last=190),
                "colmeia": _w("colmeia", heat=60, bounty=5, last=100),
            }
        }
    }
    clock = 40 * law._periods_per_day()
    before = {j: law.effective_heat(w, clock) for j, w in law.get_law(state)["wanted"].items()}
    after_law = {**state, **law.daily_tick(state, 40)}["law_state"]
    for j, heat in before.items():
        w = after_law["wanted"].get(j)
        assert law.effective_heat(w, clock) == heat
        assert law.level(w, clock) == law.level(law.get_law(state)["wanted"][j], clock)


def test_save_antigo_carrega_e_e_podado():
    state = {"law_state": {"wanted": {"codigo_de_ferro": {"heat": 3}}}}  # sem campos novos
    assert law_day_hook.day_hook(_ctx(state, 90)).state_patch["law_state"]["wanted"] == {}
    assert law_day_hook.day_hook(_ctx({}, 90)).state_patch == {}


def test_viagem_multidia_poda_uma_vez():
    state = _residual_state(clock=100)
    state["game_id"] = "law-prune-multi"
    before = dict(state["world"]["world_clock"])
    after = {**state["world"], "world_clock": {"day": before["day"] + 3, "period": "Manhã"}}
    tick = world_engine.advance_days(state, state["world"], after, [], {})
    patch = tick.state_patch["law_state"]
    assert patch["wanted"] == {}


def test_poda_e_cacadores_mesmo_turno_preserva_hunters_last_clock():
    """R7: o merge do state_patch podado nao pode apagar a marca de `mark_hunters`."""
    from agents import storyteller

    state = with_clock(base_state("nova_arcadia"), 104)  # ultimo periodo: a viagem vira o dia
    state["game_id"] = "law-prune-r7"
    state["law_state"] = {
        "wanted": {
            "codigo_de_ferro": _w(
                heat=80,
                bounty=280,
                capital=True,
                last=20,
                known={"nova_arcadia": 20, "na_anel_dourado": 22},
                shown=("perguntaram_por_voce",),
            ),
            "lei_dos_clas": _w("lei_dos_clas", known={"skallgard": 1}),  # sera podada
        }
    }
    state["messages"] = [HumanMessage(content="vou para o Pântano da Melancolia")]
    state["world"] = {**state["world"], "last_encounter_turn": -99}
    out = storyteller.storyteller_node(state)
    assert out["combat_encounter_hint"]["reason"] == "bounty_hunters"
    wanted = out["law_state"]["wanted"]
    assert "lei_dos_clas" not in wanted
    assert wanted["codigo_de_ferro"]["hunters_last_clock"] >= 0
