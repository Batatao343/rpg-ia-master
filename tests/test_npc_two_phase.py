"""SPEC-318 R1/R2: ficha de NPC em duas fases e memória de NPC fora do nó."""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from langchain_core.messages import AIMessage, HumanMessage

import agents.enrich as enrich
from agents import archivist, storyteller
from agents import npc as npc_mod
from tests.test_grounding_boundaries import _story_state, _StoryLLM

NAME = "Brás Tamanduá"
NARRATION = f"O mercador {NAME} ergue a mão e sorri para você entre as barracas."


def _stub_context(monkeypatch):
    monkeypatch.setattr(
        storyteller,
        "build_context_pack",
        lambda *_a, **_k: SimpleNamespace(
            lore_block="", memory_block="", world_state_block="<ESTADO_ATUAL_DO_MUNDO />"
        ),
    )


def _full_sheet(name=NAME):
    return {
        "id": f"npc_{name.lower().replace(' ', '_')}",
        "name": name,
        "role": "Ferreiro",  # tenta contradizer o papel já mostrado
        "persona": "Falante e interesseiro.",
        "initial_relationship": 5,
        "attributes": {"str": 11, "dex": 10, "con": 12, "int": 10, "wis": 9, "cha": 14},
    }


def _narrate(monkeypatch, *, introduced=(NAME,)):
    _stub_context(monkeypatch)
    fake = _StoryLLM(narrative=NARRATION, introduced_npcs=list(introduced))
    monkeypatch.setattr(storyteller, "get_llm", lambda **_k: fake)
    state = _story_state("Olho as barracas do mercado.")
    return state, storyteller.storyteller_node(state)


def test_storyteller_update_has_stub_and_no_fast_npc_call(monkeypatch):
    calls = []
    monkeypatch.setattr(
        storyteller, "generate_new_npc", lambda *a, **k: calls.append(a) or _full_sheet()
    )
    _state, out = _narrate(monkeypatch)
    assert calls == []  # nenhuma chamada de ficha dentro do nó narrador
    stub = out["npcs"][NAME]
    assert stub["sheet_status"] == "stub"
    assert stub["in_scene"] is True
    assert stub["role"] == "Mercador"  # inferido do TEXTO já narrado
    assert stub["hidden_traits"]  # traits seeded já presentes
    assert stub["id"] == "npc_brás_tamanduá"


def test_stub_only_carries_what_the_narration_showed(monkeypatch):
    monkeypatch.setattr(storyteller, "generate_new_npc", lambda *a, **k: _full_sheet())
    _state, out = _narrate(monkeypatch)
    stub = out["npcs"][NAME]
    # regra de ouro: nada de fato novo — persona neutra, sem memória, sem traço revelado
    assert "Pouco se sabe" in stub["persona"]
    assert stub["memory"] == [] and stub["revealed_traits"] == []


def test_two_phase_off_keeps_inline_generation(monkeypatch):
    monkeypatch.setenv("RPG_NPC_TWO_PHASE", "off")
    calls = []
    monkeypatch.setattr(
        storyteller, "generate_new_npc", lambda *a, **k: calls.append(a) or _full_sheet()
    )
    _state, out = _narrate(monkeypatch)
    assert len(calls) == 1 and "sheet_status" not in out["npcs"][NAME]


def test_enrich_completes_sheet_same_turn(monkeypatch):
    monkeypatch.setattr(storyteller, "generate_new_npc", lambda *a, **k: _full_sheet())
    state, out = _narrate(monkeypatch)
    after = {**state, **out}
    before_traits = list(after["npcs"][NAME]["hidden_traits"])
    done = enrich.enrich_node(after)
    sheet = done["npcs"][NAME]
    assert sheet["sheet_status"] == "full"
    assert sheet["persona"] == "Falante e interesseiro."
    assert sheet["role"] == "Mercador"  # o papel já mostrado não muda
    assert sheet["hidden_traits"] == before_traits
    assert sheet["in_scene"] is True and sheet["created_turn"] == 4
    assert "messages" not in done


def test_enrich_prompt_carries_the_stub_as_fixed_context(monkeypatch):
    seen = {}
    monkeypatch.setattr(
        storyteller,
        "generate_new_npc",
        lambda name, context="", **_k: seen.update(context=context) or _full_sheet(),
    )
    state, out = _narrate(monkeypatch)
    seen.clear()
    enrich.enrich_node({**state, **out})
    assert "papel Mercador" in seen["context"] and NAME in seen["context"]
    assert NARRATION in seen["context"]  # só a narração JÁ exibida entra


def test_stub_retry_max_three(monkeypatch):
    fail = {**_full_sheet(), "id": "fallback"}
    monkeypatch.setattr(storyteller, "generate_new_npc", lambda *a, **k: fail)
    state, out = _narrate(monkeypatch)
    cur = {**state, **out}
    for attempt in (1, 2, 3):
        upd = enrich.enrich_node(cur)
        cur = {**cur, **upd}
        assert cur["npcs"][NAME]["sheet_status"] == "stub"
        assert cur["npcs"][NAME]["sheet_attempts"] == attempt
    assert enrich.pending_stubs(cur) == []  # 4o turno: não tenta mais
    assert enrich.enrich_node(cur).get("npcs") is None


def test_stub_completed_on_a_later_turn(monkeypatch):
    fail = {**_full_sheet(), "id": "fallback"}
    ok = {"v": fail}
    monkeypatch.setattr(storyteller, "generate_new_npc", lambda *a, **k: ok["v"])
    state, out = _narrate(monkeypatch)
    cur = {**state, **out}
    cur = {**cur, **enrich.enrich_node(cur)}
    assert cur["npcs"][NAME]["sheet_status"] == "stub"
    ok["v"] = _full_sheet()
    cur["world"] = {**cur["world"], "turn_count": 9}
    cur = {**cur, **enrich.enrich_node(cur)}
    assert cur["npcs"][NAME]["sheet_status"] == "full"
    assert "sheet_attempts" not in cur["npcs"][NAME]


def test_stub_survives_save_round_trip(monkeypatch, tmp_path):
    import persistence

    monkeypatch.setattr(persistence, "SAVES_DIR", str(tmp_path))
    monkeypatch.setattr(storyteller, "generate_new_npc", lambda *a, **k: _full_sheet())
    state, out = _narrate(monkeypatch)
    merged = {**state, **out}
    assert persistence.save_game_state(merged)
    loaded = persistence.load_game_state()
    assert loaded["npcs"][NAME]["sheet_status"] == "stub"
    done = enrich.enrich_node(loaded)
    assert done["npcs"][NAME]["sheet_status"] == "full"


def test_old_saves_without_sheet_status_are_full():
    # saves antigos não têm `sheet_status`: nunca são tratados como pendentes
    assert enrich.pending_stubs({"npcs": {"Velho": {"name": "Velho", "role": "Guarda"}}}) == []


class _DialogueLLM:
    def with_structured_output(self, _schema):
        return self

    def invoke(self, _messages):
        return npc_mod.NPCResponse(
            dialogue="Preços justos, viajante.", action_description="sorri", memory_update=""
        )


def _talk_state(npcs):
    return {
        "game_id": "g-318",
        "active_npc_name": NAME,
        "npcs": npcs,
        "messages": [HumanMessage(content="Quanto custa a poção?")],
        "world": {
            "turn_count": 5,
            "current_location": "Nova Arcádia",
            "current_location_id": "nova_arcadia",
        },
        "party": [],
        "factions": [],
        "faction_intel": {},
        "quests": [],
    }


def test_npc_actor_talks_to_stub(monkeypatch):
    monkeypatch.setattr(storyteller, "generate_new_npc", lambda *a, **k: _full_sheet())
    _state, out = _narrate(monkeypatch)
    monkeypatch.setattr(npc_mod, "get_llm", lambda *_a, **_k: _DialogueLLM())
    monkeypatch.setattr(
        npc_mod,
        "build_context_pack",
        lambda *_a, **_k: SimpleNamespace(memory_block="", lore_block="", world_state_block=""),
    )
    res = npc_mod.npc_actor_node(_talk_state(out["npcs"]))
    text = res["messages"][0].content
    assert "Ninguém responde" not in text and "Preços justos" in text


def test_npc_memory_pending_not_embedded_in_node(monkeypatch):
    def boom(*_a, **_k):
        raise AssertionError("embedding dentro do nó")

    monkeypatch.setattr(npc_mod, "add_npc_memory", boom)
    monkeypatch.setattr(npc_mod, "get_llm", lambda *_a, **_k: _DialogueLLM())
    monkeypatch.setattr(
        npc_mod,
        "build_context_pack",
        lambda *_a, **_k: SimpleNamespace(memory_block="", lore_block="", world_state_block=""),
    )
    npcs = {
        NAME: {
            "id": "npc_bras",
            "name": NAME,
            "role": "Mercador",
            "persona": "x",
            "location": "Nova Arcádia",
            "relationship": 5,
            "memory": [],
            "in_scene": True,
        }
    }
    res = npc_mod.npc_actor_node(_talk_state(npcs))
    assert len(res["pending_npc_memory"]) == 1
    assert res["pending_npc_memory"][0]["npc_id"] == "npc_bras"
    assert res["rag_persistence_error"] is None  # pendente por desenho, não é falha
    assert res["memory_facts"] == [] or all(
        f.get("source_id") != "npc:npc_bras" for f in res["memory_facts"]
    )


def _drain_state(rows):
    return {
        "game_id": "g-318",
        "messages": [AIMessage(content="O NPC respondeu.")],
        "world": {"turn_count": 4},  # fora da janela de retry (4 % 3 != 0)
        "narrative_summary": "A conversa segue.",
        "archive_due": True,
        "archivist_last_run": 0,
        "chronicle": [],
        "pending_world_events": [],
        "memory_fact_policy": "canonical_only",
        "pending_npc_memory": rows,
    }


class _MemLLM:
    def with_structured_output(self, schema):
        self.schema = schema
        return self

    def invoke(self, _messages):
        return self.schema(summary="A conversa segue.", facts=[])


def test_archivist_drains_pending_npc_memory(monkeypatch):
    writes = []
    monkeypatch.setattr(
        archivist,
        "add_npc_memory",
        lambda gid, npc, facts, **_k: writes.append((npc, facts)) or True,
    )
    monkeypatch.setattr(archivist, "get_llm", lambda **_k: _MemLLM())
    row = {"operation": "add_npc_memory", "npc_id": "npc_bras", "facts": ["Turno 3: algo."]}
    out = archivist.archive_node(_drain_state([row]))
    assert writes == [("npc_bras", ["Turno 3: algo."])]  # fresco grava no mesmo turno
    assert out["pending_npc_memory"] == []


def test_failed_memory_waits_for_retry_window_and_is_idempotent(monkeypatch):
    writes = []

    def flaky(gid, npc, facts, **_k):
        writes.append(npc)
        return False

    monkeypatch.setattr(archivist, "add_npc_memory", flaky)
    monkeypatch.setattr(archivist, "get_llm", lambda **_k: _MemLLM())
    row = {"operation": "add_npc_memory", "npc_id": "npc_bras", "facts": ["Turno 3: algo."]}
    st = _drain_state([row])
    first = archivist.archive_node(st)
    assert len(writes) == 1 and first["pending_npc_memory"][0]["attempts"] == 1
    second = archivist.archive_node({**st, **first})  # mesmo turno 4, fora da janela
    assert len(writes) == 1  # não insiste fora da janela
    assert (
        second.get("pending_npc_memory", first["pending_npc_memory"]) == first["pending_npc_memory"]
    )
    # na janela (turno 6) tenta de novo; sucesso limpa sem duplicar
    monkeypatch.setattr(archivist, "add_npc_memory", lambda *_a, **_k: True)
    done = archivist.archive_node({**st, **first, **second, "world": {"turn_count": 6}})
    assert done["pending_npc_memory"] == []


@pytest.mark.parametrize("value", ["", "maybe"])
def test_invalid_flag_value_falls_back_to_default(monkeypatch, value):
    from services import latency_flags

    monkeypatch.setenv("RPG_NPC_TWO_PHASE", value)
    assert latency_flags.two_phase_on() is True


def _chat(monkeypatch):
    monkeypatch.setattr(npc_mod, "get_llm", lambda *_a, **_k: _DialogueLLM())
    monkeypatch.setattr(
        npc_mod,
        "build_context_pack",
        lambda *_a, **_k: SimpleNamespace(memory_block="", lore_block="", world_state_block=""),
    )
    npcs = {
        NAME: {
            "id": "npc_bras",
            "name": NAME,
            "role": "Mercador",
            "persona": "x",
            "location": "Nova Arcádia",
            "relationship": 5,
            "memory": [],
            "in_scene": True,
        }
    }
    return npc_mod.npc_actor_node(_talk_state(npcs))


def test_small_talk_is_marked_low_value_only_under_lean(monkeypatch):
    monkeypatch.setenv("RPG_ARCHIVE_POLICY", "lean")
    assert _chat(monkeypatch)["archive_low"] == 5
    monkeypatch.setenv("RPG_ARCHIVE_POLICY", "legacy")
    monkeypatch.delenv("RPG_ARCHIVE_POLICY_SHADOW", raising=False)
    assert "archive_low" not in _chat(monkeypatch)  # estado idêntico ao legado


def test_sheet_stub_streak_invariant_is_a_warning():
    from playtest import invariants as inv

    npcs = {"A": {"sheet_status": "stub", "sheet_attempts": 3}, "B": {"sheet_status": "stub"}}
    found = inv.check_sheet_stub_streak({"npcs": npcs}, None, 7)
    assert [(v.check_id, v.severity) for v in found] == [("npc.sheet_stub_streak", "warning")]
