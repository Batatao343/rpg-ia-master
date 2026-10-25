"""SPEC-318 R5: gate `lean` do arquivista (e shadow) + fallback plain em FAST."""

from __future__ import annotations

import logging

import pytest
from langchain_core.messages import AIMessage, HumanMessage

from agents import archivist
from llm_setup import ModelTier

TURN = 4  # fora da janela de retry (4 % 3 != 0) e a 4 turnos do último run


def _state(**kw):
    st = {
        "game_id": "g318",
        "messages": [HumanMessage(content="oi"), AIMessage(content="Olá, viajante.")],
        "world": {"turn_count": TURN},
        "narrative_summary": "A conversa segue.",
        "archive_due": True,
        "archivist_last_run": 2,
        "chronicle": [],
        "pending_world_events": [],
    }
    st.update(kw)
    return st


def test_default_policy_is_legacy(monkeypatch):
    monkeypatch.delenv("RPG_ARCHIVE_POLICY", raising=False)
    assert archivist._should_archive(_state(archive_low=TURN), TURN) is True


def test_lean_skips_small_talk(monkeypatch):
    monkeypatch.setenv("RPG_ARCHIVE_POLICY", "lean")
    assert archivist._should_archive(_state(archive_low=TURN), TURN) is False
    # a marca só vale no próprio turno: uma marca velha não pula um evento novo
    assert archivist._should_archive(_state(archive_low=TURN - 1), TURN) is True
    # sem marca de baixo valor = evento relevante, mantém
    assert archivist._should_archive(_state(), TURN) is True


def test_lean_keeps_conflict_summary(monkeypatch):
    monkeypatch.setenv("RPG_ARCHIVE_POLICY", "lean")
    st = _state(archive_low=TURN, conflict_summary={"conflict_id": "c1"})
    assert archivist._should_archive(st, TURN) is True


def test_lean_keeps_canonical_facts(monkeypatch):
    monkeypatch.setenv("RPG_ARCHIVE_POLICY", "lean")
    st = _state(archive_low=TURN, memory_canonical_facts=["O herói viu a ponte cair."])
    assert archivist._should_archive(st, TURN) is True


def test_lean_keeps_every_10_turns(monkeypatch):
    monkeypatch.setenv("RPG_ARCHIVE_POLICY", "lean")
    st = _state(archive_low=12, archivist_last_run=2, world={"turn_count": 12})
    assert archivist._should_archive(st, 12) is True  # 12 - 2 >= 10


def test_lean_does_not_treat_npc_queue_as_trigger(monkeypatch):
    monkeypatch.setenv("RPG_ARCHIVE_POLICY", "lean")
    row = {"operation": "add_npc_memory", "npc_id": "npc_x", "facts": ["f"]}
    st = _state(archive_low=TURN, pending_npc_memory=[row], memory_fact_policy="canonical_only")
    assert archivist._should_archive(st, TURN) is False


def test_lean_skip_still_drains_npc_memory_without_llm(monkeypatch):
    monkeypatch.setenv("RPG_ARCHIVE_POLICY", "lean")
    writes = []
    monkeypatch.setattr(
        archivist, "add_npc_memory", lambda g, n, f, **_k: writes.append((n, list(f))) or True
    )
    monkeypatch.setattr(
        archivist,
        "get_llm",
        lambda **_k: (_ for _ in ()).throw(AssertionError("o SMART não devia rodar")),
    )
    row = {"operation": "add_npc_memory", "npc_id": "npc_x", "facts": ["Turno 4: algo."]}
    out = archivist.archive_node(
        _state(archive_low=TURN, pending_npc_memory=[row], memory_fact_policy="canonical_only")
    )
    assert writes == [("npc_x", ["Turno 4: algo."])]
    assert out["pending_npc_memory"] == []
    assert out["archive_due"] is False and out["memory_fact_policy"] is None


def test_shadow_logs_would_skip(monkeypatch, caplog):
    monkeypatch.setenv("RPG_ARCHIVE_POLICY", "legacy")
    monkeypatch.setenv("RPG_ARCHIVE_POLICY_SHADOW", "1")
    with caplog.at_level(logging.INFO):
        assert archivist._should_archive(_state(archive_low=TURN), TURN) is True  # nada muda
        assert archivist._should_archive(_state(), TURN) is True
    shadow = [r.getMessage() for r in caplog.records if "lean_shadow" in r.getMessage()]
    assert len(shadow) == 2
    assert '"would_skip": true' in shadow[0].lower() and '"would_skip": false' in shadow[1].lower()


def test_shadow_off_logs_nothing(monkeypatch, caplog):
    monkeypatch.delenv("RPG_ARCHIVE_POLICY_SHADOW", raising=False)
    with caplog.at_level(logging.INFO):
        archivist._should_archive(_state(archive_low=TURN), TURN)
    assert not [r for r in caplog.records if "lean_shadow" in r.getMessage()]


@pytest.mark.parametrize("policy", ["legacy", "lean"])
def test_emitters_mark_low_only_when_policy_reads_it(monkeypatch, policy):
    from services import latency_flags

    monkeypatch.setenv("RPG_ARCHIVE_POLICY", policy)
    assert latency_flags.archive_low_wanted() is (policy == "lean")


def test_plain_fallback_uses_fast(monkeypatch):
    tiers = []

    class _Bad:
        def with_structured_output(self, _m):
            return self

        def invoke(self, _msgs):
            return AIMessage(content="texto solto, não é MemoryUpdate")

    class _Plain:
        is_fallback = False

        def invoke(self, _msgs):
            return AIMessage(content="O herói segue pela estrada.")

    def fake_get_llm(*, temperature=0.3, tier=ModelTier.SMART):
        tiers.append(tier)
        return _Bad() if tier == ModelTier.SMART else _Plain()

    monkeypatch.setattr(archivist, "get_llm", fake_get_llm)
    out = archivist.archive_node(_state())
    assert ModelTier.FAST in tiers and tiers[0] == ModelTier.SMART
    assert "estrada" in out.get("narrative_summary", "")
