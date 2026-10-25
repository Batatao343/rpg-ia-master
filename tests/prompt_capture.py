"""Captura os system prompts de router/narrador/NPC com LLMs espiões (SPEC-317 R9)."""

from __future__ import annotations

from langchain_core.messages import AIMessage, HumanMessage

import agents.npc as npc
import agents.router as router_mod
import agents.storyteller as stt
from tests.test_ambient_consumers import _story_state


class _Spy:
    def __init__(self, sink: dict, key: str):
        self.sink, self.key = sink, key

    def with_structured_output(self, *_a, **_k):
        return self

    def invoke(self, msgs, *_a, **_k):
        self.sink.setdefault(self.key, str(msgs[0].content))
        return AIMessage(content="ok")


def capture(monkeypatch) -> dict[str, str]:
    sink: dict[str, str] = {}
    monkeypatch.setattr(stt, "get_llm", lambda *a, **k: _Spy(sink, "story"))
    monkeypatch.setattr(npc, "get_llm", lambda *a, **k: _Spy(sink, "npc"))
    monkeypatch.setattr(router_mod, "get_llm", lambda *a, **k: _Spy(sink, "router"))
    stt.storyteller_node(_story_state())
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
    rs = _story_state(text="Sigo pela estrada")
    router_mod.dm_router_node(rs)
    return sink
