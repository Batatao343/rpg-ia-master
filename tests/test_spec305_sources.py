"""SPEC-305 Etapa 2: candidatas, prazo e viabilidade (ids reais do mapa)."""

from __future__ import annotations

import ast
import pathlib

import pytest

from services import world_quests as wq
from tests.spec305_helpers import add_crisis, base_state

ROOT = pathlib.Path(__file__).resolve().parents[1]


def _by_kind(state: dict, day: int = 17) -> dict:
    return {s.kind: s for s in wq.candidates(state, day)}


def test_each_kind_has_candidate_from_state():
    state = base_state()
    add_crisis(state, "guerra", "brekmar", cid="c-guerra", faction_id="legiao_ferro")
    add_crisis(state, "fome", "nova_arcadia", cid="c-fome", loc="nova_arcadia")
    add_crisis(state, "praga", "pantano_melancolia", cid="c-praga", loc="pantano_melancolia")
    add_crisis(state, "abismo", "aethelgard", cid="c-abismo", loc="aethelgard")
    add_crisis(
        state,
        "ascensao",
        "skallgard",
        cid="c-asc",
        start=None,
        warned=15,
        faction_id="clas_combate",
    )
    state["world_projection"] = {
        "location_states": {
            "brekmar_porto": {"state": "ocupado", "since_day": 12, "faction_id": "x"}
        },
        "blocked_routes": [
            {"a": "nova_arcadia", "b": "brekmar", "blocked_by_event": "ev-rt-12345"}
        ],
    }
    got = _by_kind(state)
    assert {
        "romper_cerco",
        "socorrer_escassez",
        "conter_praga",
        "selar_corrupcao",
        "frear_ascensao",
        "libertar_ocupado",
        "reabrir_rota",
    } <= set(got)
    assert got["reabrir_rota"].other_location_id == "brekmar"


def test_deadline_equals_escalation_day():
    state = base_state()
    add_crisis(state, "praga", "brekmar", start=17, escalation=23)
    seed = _by_kind(state)["conter_praga"]
    assert seed.deadline_day == 23 and not seed.provisional


def test_announced_crisis_provisional_deadline_uses_warning_plus_windows():
    state = base_state()
    add_crisis(state, "praga", "brekmar", start=None, warned=14)
    seed = _by_kind(state)["conter_praga"]
    # warned + MIN_WARNING_DAYS (2) + ESCALATION_DAYS (6)
    assert seed.deadline_day == 22 and seed.provisional


@pytest.mark.parametrize("opened_at,escalation", [(16, 22), (17, 23), (19, 25)])
def test_announced_crisis_provisional_deadline_never_shortens(opened_at, escalation):
    """R2: quando a crise abre, o prazo vira o `escalation_day` — nunca menor que o atual."""
    state = base_state(day=opened_at)
    rec = add_crisis(state, "praga", "brekmar", start=None, warned=14, cid="c-p")
    quests, created = wq.offer_from_perceived(
        state, [], opened_at
    )  # sem percepcao: nada, so prepara estado
    assert created == []
    quest = {
        "id": "q",
        "world_kind": "conter_praga",
        "world_source_id": "c-p",
        "status": "active",
        "location_id": "brekmar",
        "deadline_day": 22,
        "deadline_provisional": True,
        "title": "t",
        "progress_log": [],
    }
    rec.update(start_day=opened_at, escalation_day=escalation, location_id="brekmar", severity=1)
    state["quests"] = [quest]
    out, _events = wq.sync_deadlines(state, opened_at)
    assert out[0]["deadline_day"] >= 22
    assert out[0]["deadline_day"] == max(22, escalation)
    assert "deadline_provisional" not in out[0]


def test_route_with_siege_is_not_reabrir_rota():
    state = base_state()
    add_crisis(
        state, "guerra", "brekmar", cid="c-s", route=["nova_arcadia", "brekmar"], faction_id="x"
    )
    state["world_projection"] = {
        "blocked_routes": [{"a": "nova_arcadia", "b": "brekmar", "blocked_by_event": "ev-12345678"}]
    }
    assert "reabrir_rota" not in _by_kind(state)
    assert "romper_cerco" in _by_kind(state)


def test_feasibility_filters_unreachable():
    state = base_state(loc="nova_arcadia")
    # nova_arcadia -> brekmar custa 2 periodos (1 dia): precisa de folga de 1 dia
    assert wq.is_feasible(state, "brekmar", 19, 17)
    assert not wq.is_feasible(state, "brekmar", 18, 17)
    assert not wq.is_feasible(state, "local_inexistente", 40, 17)


def test_feasibility_blocks_offer():
    state = base_state(loc="nova_arcadia")
    add_crisis(state, "praga", "brekmar", start=17, escalation=18)
    item = {
        "item_id": "i1",
        "day": 17,
        "kind": "crise",
        "region_id": "brekmar",
        "location_id": "nova_arcadia",
        "template_id": "praga.crise.inicio",
        "params": {"local": "brekmar"},
        "subject_id": "ev-1",
    }
    _quests, created = wq.offer_from_perceived(state, [item], 17)
    assert created == []  # inviavel: nao da tempo


def test_independent_of_player_stats():
    """R4: mesmo estado com nivel 1 e 20 -> mesmas candidatas e prazos."""
    a, b = base_state(), base_state()
    for st, lvl in ((a, 1), (b, 20)):
        add_crisis(st, "praga", "brekmar")
        st["player"] = {"level": lvl, "gold": lvl * 100, "inventory": [{"id": "x"}] * lvl}
    assert wq.candidates(a, 17) == wq.candidates(b, 17)


def test_no_global_random_in_world_quests():
    tree = ast.parse((ROOT / "services" / "world_quests.py").read_text(encoding="utf-8"))
    names = {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)}
    imports = {
        a.name
        for n in ast.walk(tree)
        if isinstance(n, (ast.Import, ast.ImportFrom))
        for a in n.names
    }
    assert "random" not in names and "random" not in imports


def test_deterministic_ids_and_idempotent_offer():
    state = base_state()
    add_crisis(state, "praga", "brekmar")
    item = {
        "item_id": "i1",
        "day": 17,
        "kind": "crise",
        "region_id": "brekmar",
        "location_id": "brekmar",
        "template_id": "praga.crise.inicio",
        "params": {"local": "brekmar"},
        "subject_id": "ev-1",
    }
    q1, c1 = wq.offer_from_perceived(state, [item], 17)
    assert len(c1) == 1
    again = wq.offer_from_perceived({**state, "quests": q1}, [item], 17)
    assert again[1] == [] and len(again[0]) == 1
    # replay: mesmo id
    _q2, c2 = wq.offer_from_perceived(state, [item], 17)
    assert c1[0]["id"] == c2[0]["id"] == wq.quest_id("g-302", "conter_praga", "crise-1")


def test_resgate_on_with_spec304_but_no_perils():
    """SPEC-304 pousou: o tipo `resgate` esta ligado (`active_perils`), mas sem perigo aberto
    (nenhum NPC simulado em risco) nao nasce semente."""
    assert wq._peril_api() is not None
    assert "resgate" not in _by_kind(base_state())


def test_recuperar_objeto_from_unique_item_held_by_faction():
    state = base_state()
    state["world_projection"] = {
        "unique_items": {
            "art_adaga_vidro_dragao": {"holder": "legiao_ferro", "event_id": "ev-obj-123456"}
        }
    }
    seed = _by_kind(state).get("recuperar_objeto")
    assert seed is not None and seed.item_id == "art_adaga_vidro_dragao"
    # comerciante / jogador / mundo NAO geram a quest
    state["world_projection"]["unique_items"]["art_adaga_vidro_dragao"]["holder"] = "player"
    assert "recuperar_objeto" not in _by_kind(state)
