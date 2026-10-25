"""SPEC-314 Etapa 2 — o que o LLM pode PROPOR (R9-R12)."""

from __future__ import annotations

import pytest

import agents.npc as npc
from services import faction_membership as fm
from tests.spec310_helpers import sergeant
from tests.test_spec310_npc_prompt import _state


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    monkeypatch.setenv("RPG_WORLD_ENGINE", "on")
    monkeypatch.setenv("RPG_NPC_WORLD", "on")
    monkeypatch.setenv("RPG_NPC_KNOWLEDGE", "off")
    monkeypatch.delenv("RPG_NPC_SELF", raising=False)


class _Fixed:
    def __init__(self, **fields):
        self.res = npc.NPCResponse(
            dialogue="Hum.", action_description="encara", memory_update="", **fields
        )

    def with_structured_output(self, *_a, **_k):
        return self

    def invoke(self, *_a, **_k):
        return self.res


def _run(monkeypatch, state, **fields):
    monkeypatch.setattr(npc, "get_llm", lambda *a, **k: _Fixed(**fields))
    monkeypatch.setattr(npc, "RAG_AVAILABLE", False)
    return npc.npc_actor_node(state)


def _rev(fid, level):
    return npc.FactionReveal(faction_id=fid, reveal_level=level)


def _intel(out):
    return out.get("faction_intel") or {}


def test_reveal_id_invisivel_descartado(monkeypatch):
    out = _run(monkeypatch, _state(), faction_reveals=[_rev("cultistas_destilacao", "existencia")])
    assert "cultistas_destilacao" not in _intel(out)  # secreta ignota: nem estava no bloco


def test_reveal_sem_plano_vira_existencia(monkeypatch):
    row = sergeant(relationship=8)  # amistoso: teto 'objetivo'
    st = _state(row)
    out = _run(monkeypatch, st, faction_reveals=[_rev("cultistas_destilacao", "objetivo")])
    assert "cultistas_destilacao" not in _intel(out)
    st["faction_intel"] = {
        "cultistas_destilacao": {"known": True}
    }  # visível, mas amistoso e não rival
    out = _run(monkeypatch, st, faction_reveals=[_rev("cultistas_destilacao", "objetivo")])
    assert _intel(out)["cultistas_destilacao"]["known"] is True
    assert not _intel(out)["cultistas_destilacao"].get("knows_goal")
    # pública com plano mostrado (amistoso): 'objetivo' passa
    out = _run(monkeypatch, st, faction_reveals=[_rev("clas_combate", "objetivo")])
    assert _intel(out)["clas_combate"]["knows_goal"] is True


def test_alias_sem_leal_descarta_reveal(monkeypatch):
    row = sergeant(id="npc_pardal", faction_id="mao_sombria", relationship=8)
    out = _run(monkeypatch, _state(row), faction_reveals=[_rev("sua_irmandade", "existencia")])
    assert "mao_sombria" not in _intel(out)
    out = _run(monkeypatch, _state(row), faction_reveals=[_rev("mao_sombria", "existencia")])
    assert "mao_sombria" not in _intel(out)  # id real também não estava no prompt


def test_recrutador_secreto_join_via_alias(monkeypatch):
    seen = []

    def fake(state, action, fid):
        seen.append((action, fid))
        return {}, [], ""

    monkeypatch.setattr(fm, "apply_intent", fake)
    row = sergeant(id="npc_pardal", faction_id="mao_sombria")
    ma = npc.MembershipAction(action="join", faction_id="sua_irmandade")
    _run(monkeypatch, _state(row), membership_action=ma)
    assert seen == [("join", "mao_sombria")]
    seen.clear()  # id de fação secreta fora do bloco: nem chega ao motor
    ma = npc.MembershipAction(action="join", faction_id="cultistas_destilacao")
    _run(monkeypatch, _state(row), membership_action=ma)
    assert seen == []


def test_schema_descricoes():
    for model, field in (
        (npc.FactionReveal, "faction_id"),
        (npc.MembershipAction, "faction_id"),
        (npc.NPCResponse, "membership_action"),
    ):
        desc = model.model_fields[field].description
        assert "sua_irmandade" in desc and "<FACÇÕES_DO_MUNDO>" in desc
