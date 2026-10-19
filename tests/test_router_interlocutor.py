"""SPEC-202 Etapa 2 — fiação da política de interlocutor no router e no ator."""

from __future__ import annotations

import pytest
from langchain_core.messages import HumanMessage

import agents.router as router_mod
from agents.router import RouterDecision, RouteType, dm_router_node
from tests.test_interlocutor import _CountingLLM, _state


def _install(monkeypatch, route=RouteType.STORY, target=None) -> _CountingLLM:
    llm = _CountingLLM(route, target)
    monkeypatch.setattr(router_mod, "get_llm", lambda *a, **k: llm)
    return llm


def test_ordem_precedencia_preservada(monkeypatch):
    # combate ativo: gate de combate vence a meta-pergunta (sem CLASSIFY).
    llm = _install(monkeypatch, RouteType.NPC, "Brunna")
    st = _state("Narrador, a Brunna parece mentir?", combat={"active": True, "round": 1})
    out = dm_router_node(st)
    assert out["next"] == RouteType.COMBAT.value and llm.calls == 0

    # recovery
    import services.actor_lifecycle as lifecycle

    monkeypatch.setattr(lifecycle, "is_recovery_turn", lambda _s: True)
    out = dm_router_node(_state("Brunna, me ajude"))
    assert out["next"] == RouteType.STORY.value and llm.calls == 0
    monkeypatch.setattr(lifecycle, "is_recovery_turn", lambda _s: False)

    # viagem/descanso explícitos
    out = dm_router_node(_state("Viajo para Nova Arcádia com a Brunna"))
    assert out["next"] == RouteType.STORY.value
    assert out["interlocutor_reason"] is None and llm.calls == 0

    # SPEC-217 R14: o Jev roda DEPOIS dos gates Python (pre_classify incluso) e,
    # em primary coberto, pula o CLASSIFY; o payload passa pela mesma política.
    import services.jev_rollout as jev

    calls = []

    class _Primary:
        mode = "primary"

        def primary_routing(self):
            return jev.JevRouting("storyteller", None, None, 0.9)

    monkeypatch.setattr(jev, "begin", lambda s, t: calls.append(t) or _Primary())
    out = dm_router_node(_state("Narrador, a Brunna parece mentir?"))
    assert out["next"] == RouteType.STORY.value and not calls and llm.calls == 0
    out = dm_router_node(_state("Brunna, você viu o barco?"))
    assert out["next"] == RouteType.NPC.value and calls and llm.calls == 0


CASES = [
    ("Pergunto ao narrador o que a Velha Magda sente", RouteType.NPC, "Velha Magda", 0),
    ("Descreva quem está aqui", RouteType.NPC, "Brunna", 0),
    ("O que eu sei sobre a Brunna?", RouteType.NPC, None, 0),
    ("Brunna, você viu o barco?", RouteType.NPC, "Brunna", 1),
    ("Falo com Halveth", RouteType.NPC, "Halveth", 1),
    ("Falo com Gorim", RouteType.NPC, "Gorim", 1),
    ("E você?", RouteType.STORY, None, 1),
    ("Pergunto a ela o que houve", RouteType.NPC, "ela", 1),
    ("Ataco o guarda", RouteType.COMBAT, "Guarda", 1),
    ("Compro uma corda", RouteType.LOOT, None, 1),
]


@pytest.mark.parametrize("text,route,target,expected_calls", CASES)
def test_zero_invoke_extra(monkeypatch, text, route, target, expected_calls):
    llm = _install(monkeypatch, route, target)
    dm_router_node(_state(text))
    assert llm.calls == expected_calls <= 1


def test_prompt_classify_lista_npcs_em_cena(monkeypatch):
    seen = {}

    class _Spy(_CountingLLM):
        def invoke(self, messages):
            seen["sys"] = str(messages[0].content)
            return super().invoke(messages)

    llm = _Spy(RouteType.STORY)
    monkeypatch.setattr(router_mod, "get_llm", lambda *a, **k: llm)
    dm_router_node(_state("Sigo pela rua"))
    assert "Brunna Ponte-Alta" in seen["sys"] and "Velha Magda" in seen["sys"]
    assert "Gorim" not in seen["sys"]  # fora de cena não é listado
    assert "narrador" in seen["sys"].lower()


def test_classify_falho_rotula_fallback(monkeypatch):
    class _Boom:
        def with_structured_output(self, *_a, **_k):
            return self

        def invoke(self, _m):
            raise RuntimeError("down")

    monkeypatch.setattr(router_mod, "get_llm", lambda *a, **k: _Boom())
    out = dm_router_node(_state("Sigo pela rua"))
    assert out["next"] == RouteType.STORY.value
    assert out["interlocutor_reason"] == "classify_fallback"


def test_npc_actor_nao_gera_npc_sem_generic_role(monkeypatch):
    import agents.npc as npc_mod

    generated = []
    monkeypatch.setattr(
        npc_mod,
        "generate_new_npc",
        lambda name, context="": (
            generated.append(name)
            or {"name": "Orsolya", "role": "Taverneira", "persona": "seca", "memory": []}
        ),
    )
    st = {**_state("Falo com o taverneiro"), "npcs": {}}

    out = npc_mod.npc_actor_node({**st, "active_npc_name": "taverneiro"})
    assert out.get("next") == "storyteller" and not generated

    out = npc_mod.npc_actor_node(
        {**st, "active_npc_name": "taverneiro", "interlocutor_reason": "generic_role_spawn"}
    )
    assert generated == ["taverneiro"]
    assert str(out["messages"][0].content).startswith("**Orsolya:**")
    assert out["active_npc_name"] in out["npcs"]


def test_party_command_preservado(monkeypatch):
    import agents.npc as npc_mod

    llm = _install(monkeypatch, RouteType.NPC, "Brunna")
    st = _state("Brunna, junte-se a mim")
    route = dm_router_node(st)
    assert route["active_npc_name"] == "Brunna Ponte-Alta" and llm.calls == 1
    out = npc_mod.npc_actor_node({**st, **route})
    assert "Brunna Ponte-Alta" in str(out["messages"][0].content)
    assert "last_interaction_outcome" in out or "party" in out


def test_suite_existente_router_payload_zerado(monkeypatch):
    _install(monkeypatch, RouteType.STORY)
    out = dm_router_node(
        {
            "messages": [HumanMessage(content="acao")],
            "world": {"current_location": "Ponte"},
            "npcs": {},
            "combat": None,
        }
    )
    assert out["active_npc_name"] is None and out["mediated_subject_id"] is None
    assert out["interlocutor_reason"] == "classify_story"


def test_router_decision_schema_intacto():
    assert set(RouterDecision.model_fields) == {
        "route",
        "loot_context",
        "target",
        "reasoning",
        "confidence",
    }
