"""SPEC-390: 3 arestas de texto do 8º smoke (Voto em "você", Provocação no herói, título da missão)."""

from __future__ import annotations

import random

import pytest

from services import round_log as rl
from services import turn_outcome as to
from tests.fixtures import spec368_seed as sd

HERO = "Smoke368"


@pytest.fixture(scope="module")
def saves(tmp_path_factory):
    return str(tmp_path_factory.mktemp("spec390_saves"))


def test_voce_replaces_hero_name_in_voto_line():
    line = f"Goblin, provocado por {HERO}, muda de alvo."
    assert rl._voce(line, HERO) == "Goblin, provocado por você, muda de alvo."
    assert rl._is_human_line(rl._voce(line, HERO))


def test_voce_keeps_other_actor_name():
    line = "Goblin, provocado por Ketil, muda de alvo."
    assert rl._voce(line, HERO) == line


def _taunt(victim: str, source: str) -> list[str]:
    names = {"v": victim, "s": source}
    out = {"condicoes_novas": [{"control": "taunt", "victim_id": "v", "source_id": "s"}]}
    return rl._taunt_lines(out, names)


def test_taunt_on_hero_uses_voce_voice():
    assert _taunt("Você", "Soldado") == ["Você está provocado por Soldado."]


def test_taunt_on_enemy_keeps_text():
    assert _taunt("Goblin", "Você") == [
        "Goblin está provocado: a próxima intenção dele mira você (com chance)."
    ]


def test_public_outcome_uses_quest_title_and_falls_back_to_id():
    base = {"receipt_id": "r1", "quests_completed": ["q368"]}
    titled = to.public_outcome({**base, "quest_titles": {"q368": "Caça"}})
    assert titled["quests_completed"] == [{"id": "q368", "title": "Caça"}]
    old = to.public_outcome(base)  # save antigo sem quest_titles
    assert old["quests_completed"] == [{"id": "q368", "title": "q368"}]


def test_finalize_outcome_keeps_receipt_id_and_adds_titles():
    state = {
        "game_id": "g",
        "turn_baseline": {"completed_quests": []},
        "quests": [{"id": "q1", "title": "Caça", "status": "completed"}],
        "player": {},
        "world": {},
    }
    out = to.finalize_outcome(state)
    assert out["quest_titles"] == {"q1": "Caça"}
    state["quests"][0]["title"] = "Outro"
    assert to.finalize_outcome(state)["receipt_id"] == out["receipt_id"]


def test_voto_api_never_shows_hero_name(saves):
    from fastapi.testclient import TestClient

    import api

    seen = False
    for seed in range(6):
        gid = sd.seed_save(13, variant="voto", saves_dir=saves)
        with sd._legacy(saves):
            random.seed(seed)
            c = TestClient(api.app)
            r = c.post("/game/action", json=sd.smoke_body(13, "voto", gid))
            assert r.status_code == 200, r.text[:300]
            hist = c.get("/game/history", params={"game_id": gid}).text
        for text in (r.text, hist):
            assert f"provocado por {HERO}" not in text
        seen = seen or "provocado por você, muda de alvo" in r.text
    assert seen


def test_entrega_receipt_shows_title(saves):
    from langchain_core.messages import HumanMessage

    from agents.npc import npc_actor_node
    from services.event_processor import process_pending_events

    gid = sd.seed_save(14, variant="entrega", saves_dir=saves)
    with sd._legacy(saves):
        st = sd._load(gid)
    st["turn_baseline"] = to.capture_baseline(st)
    st["messages"] = [*st.get("messages", []), HumanMessage(content="Entrego a prova da caça")]
    st["active_npc_name"] = "Contratante"
    done = process_pending_events({**st, **npc_actor_node(st)})
    pub = to.public_outcome(to.finalize_outcome({**st, **done}))
    assert pub["quests_completed"] == [{"id": "q368", "title": "Caça"}]
