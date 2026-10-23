"""SPEC-296 Etapa 2 — consumidores do <AMBIENTE> e notícias percebidas (offline)."""

import os
import random

from langchain_core.messages import AIMessage, HumanMessage

import agents.combat as combat
import agents.npc as npc
import agents.storyteller as stt
from tests.test_combat_lifecycle import _enemy, _player


class _Spy:
    """LLM que só captura o prompt e falha (cai nos fallbacks determinísticos)."""

    def __init__(self):
        self.prompts: list[str] = []

    def with_structured_output(self, *_a, **_k):
        return self

    def invoke(self, msgs, *_a, **_k):
        self.prompts.append("\n".join(str(getattr(m, "content", m)) for m in msgs))
        return AIMessage(content="ok")


def _story_state(world_extra=None, text="Observo ao redor"):
    world = {
        "current_location": "Skallgard",
        "current_location_id": "skallgard",
        "turn_count": 5,
        "time_of_day": "Manhã",
        "danger_level": 2,
        "weather_state": "nevasca",
        "world_clock": {"day": 2, "period": "Manhã"},
        "quest_plan": [],
    }
    world.update(world_extra or {})
    return {
        "game_id": "pytest296",
        "narrative_summary": "",
        "archivist_last_run": 0,
        "messages": [HumanMessage(content=text)],
        "npcs": {},
        "factions": [],
        "faction_intel": {},
        "campaign_plan": {},
        "player": {
            "name": "T",
            "class_name": "Guerreiro",
            "level": 1,
            "vitalidade": 10,
            "max_vitalidade": 10,
        },
        "world": world,
    }


def test_storyteller_prompt_has_ambient_block(monkeypatch):
    spy = _Spy()
    monkeypatch.setattr(stt, "get_llm", lambda *a, **k: spy)
    stt.storyteller_node(_story_state())
    prompt = spy.prompts[0]
    assert "<AMBIENTE>" in prompt and "Saídas:" in prompt
    assert "Nevasca" in prompt
    assert "Fenômeno global" not in prompt
    assert "<AMBIENTE_DE_LUZ>" not in prompt and "<CLIMA_GLOBAL>" not in prompt


def test_storyteller_appends_news_on_pulse(monkeypatch):
    spy = _Spy()
    monkeypatch.setattr(stt, "get_llm", lambda *a, **k: spy)
    monkeypatch.setattr(
        stt,
        "simulate_world",
        lambda state, world, f, i, p: (world, "[ECOS DO MUNDO] Sinos ao longe."),
    )
    out = stt.storyteller_node(_story_state(text="Descanso até recuperar as forças"))
    news = out["world"]["news"]
    assert news and news[-1]["text"] == "Sinos ao longe."
    assert news[-1]["source"] == "pulse" and news[-1]["location_id"] == "skallgard"


def test_storyteller_prompt_has_heard_block(monkeypatch):
    spy = _Spy()
    monkeypatch.setattr(stt, "get_llm", lambda *a, **k: spy)
    news = [
        {
            "day": 1,
            "period": "Manhã",
            "location_id": "x",
            "location_name": "Brekmar",
            "text": "Um cometa cruzou o céu.",
            "source": "pulse",
            "turn": 1,
        }
    ]
    stt.storyteller_node(_story_state({"news": news}))
    prompt = spy.prompts[0]
    assert "<OUVIU_DIZER>" in prompt and "Um cometa cruzou o céu." in prompt
    assert "não invente detalhes" in prompt


def test_npc_prompt_has_ambient_without_exits(monkeypatch):
    seen = {}

    class _NPCLLM(_Spy):
        def invoke(self, msgs, *a, **k):
            seen["p"] = str(msgs[0].content)
            return self._model(
                dialogue="oi",
                action_description="",
                memory_update="",
                relationship_change=0,
                faction_reveals=[],
            )

        _model = npc.NPCResponse if hasattr(npc, "NPCResponse") else None

    monkeypatch.setattr(npc, "get_llm", lambda *a, **k: _NPCLLM())
    st = _story_state()
    st.update(
        active_npc_name="Guarda",
        npcs={
            "Guarda": {
                "name": "Guarda",
                "role": "guarda",
                "persona": "rude",
                "location": "skallgard",
                "memory": [],
                "relationship": 5,
            }
        },
        messages=[HumanMessage(content="quem manda aqui?")],
    )
    try:
        npc.npc_actor_node(st)
    except Exception:  # noqa: BLE001 - só o prompt interessa
        pass
    assert "<AMBIENTE>" in seen["p"]
    assert "Saídas:" not in seen["p"]


def test_combat_world_ctx_has_ambient(monkeypatch):
    spy = _Spy()
    monkeypatch.setattr(combat, "get_llm", lambda *a, **k: spy)
    random.seed(1)
    state = {
        "game_id": "amb-combat",
        "messages": [HumanMessage(content="ataco o goblin")],
        "player": _player(),
        "enemies": [_enemy(hp=200)],
        "combat": {"active": True},
        "world": {
            "current_location": "Skallgard",
            "current_location_id": "skallgard",
            "turn_count": 3,
            "danger_level": 2,
            "weather_state": "nevasca",
            "world_clock": {"day": 1, "period": "Manhã"},
        },
        "party": [],
    }
    combat.combat_node(state)
    joined = "\n".join(spy.prompts)
    assert "<AMBIENTE>" in joined
    assert "Saídas:" not in joined


def test_legacy_save_without_news_loads():
    import persistence
    from services.ambient import append_news, heard_block

    state = _story_state()
    assert "news" not in state["world"]
    state["game_id"] = "legacy-news"
    assert persistence.save_game_state(state)
    loaded = persistence.load_game_state(os.path.join(persistence.SAVES_DIR, "legacy-news.json"))
    assert loaded is not None
    assert not loaded["world"].get("news")  # save antigo: ausente/vazio, sem quebrar
    assert heard_block(loaded["world"]) == ""
    state["world"] = append_news(
        state["world"], text="Rumor", location_id="skallgard", location_name="Skallgard", turn=1
    )
    assert persistence.save_game_state(state)
    again = persistence.load_game_state(os.path.join(persistence.SAVES_DIR, "legacy-news.json"))
    assert again["world"]["news"][0]["text"] == "Rumor"


def test_world_block_exposes_news():
    import api
    from services.ambient import append_news

    w = {"current_location": "X", "world_clock": {"day": 1, "period": "Manhã"}}
    assert api._world_block(w)["news"] == []
    for i in range(15):
        w = append_news(w, text=f"r{i}", location_id="a", location_name="A", turn=i)
    block = api._world_block(w)
    assert len(block["news"]) == 12 and block["news"][-1]["text"] == "r14"
