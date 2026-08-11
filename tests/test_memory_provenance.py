"""Contratos da spec hardening-memoria-proveniencia."""
from __future__ import annotations

from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from agents import archivist
from agents.archivist import MemoryUpdate
from playtest.invariants import check_memory_provenance
from playtest.runner import CampaignResult, TurnRecord, _fill_state_metrics
from playtest.telemetry import build_summary, turn_to_record
from services.context_builder import build_context_pack
from services.memory_provenance import (
    MemoryFactRecord,
    commit_memory_facts,
    make_memory_fact,
    normalize_memory_facts,
    validate_memory_fact,
)
import persistence
import rag


def _event(event_id: str = "evt-1", *, event_type: str = "npc_killed") -> dict:
    return {
        "event_id": event_id,
        "type": event_type,
        "target_id": "npc_bandido",
        "turn": 4,
        "payload": {},
    }


def test_schema_fecha_enums_e_memoria_legada_perde_autoridade() -> None:
    with pytest.raises(ValidationError):
        MemoryFactRecord.model_validate({
            "text": "algo",
            "provenance": "certeza_do_narrador",
            "confidence": "absoluta",
        })

    [legacy] = normalize_memory_facts(["A ponte caiu."])
    assert legacy["provenance"] == "legacy_unverified"
    assert legacy["confidence"] == "speculative"
    assert legacy["source_id"] is None


def test_roundtrip_save_preserva_ledger_e_migra_string_legada_lazy() -> None:
    raw = persistence._state_to_save_data({
        "game_id": "save-memory",
        "player": {},
        "memory_facts": ["Um save antigo lembrava da ponte."],
        "pending_memory_facts": [make_memory_fact(
            "Um relato aguarda retry.", provenance="npc_claim",
            source_id="npc:iris", source_turn=8,
        )],
    }, "save-memory")
    loaded = persistence._raw_to_state(raw)
    assert loaded["memory_facts"][0]["provenance"] == "legacy_unverified"
    assert loaded["memory_facts"][0]["confidence"] == "speculative"
    assert loaded["pending_memory_facts"][0]["source_id"] == "npc:iris"


def test_documentos_faiss_usam_metadata_e_legado_fica_nao_verificado() -> None:
    confirmed = make_memory_fact(
        "A ponte caiu.", provenance="canonical_event",
        source_id="evt-ponte", source_turn=3,
    )
    from services.memory_provenance import memory_metadata
    rendered = rag._format_memory_documents([
        SimpleNamespace(page_content="A ponte caiu.", metadata=memory_metadata(confirmed)),
        SimpleNamespace(page_content="A memória antiga existe.", metadata={}),
    ])
    assert "[CONFIRMADO | canonical_event | fonte evt-ponte | turno 3]" in rendered
    assert "[NÃO VERIFICADO | legacy_unverified] A memória antiga existe." in rendered


def test_llm_nao_pode_promover_inferencia_e_evento_aceito_pode_confirmar() -> None:
    inference = make_memory_fact(
        "Valerius talvez tenha feito um pacto.",
        provenance="inference",
        confidence="confirmed",  # entrada hostil: deve ser ignorada
        source_id="archivist:4",
        source_turn=4,
    )
    assert inference["confidence"] == "speculative"

    state = {"event_log": [_event()]}
    canonical = make_memory_fact(
        "O bandido morreu.",
        provenance="canonical_event",
        source_id="evt-1",
        source_turn=4,
    )
    accepted, reason = validate_memory_fact(canonical, state)
    assert reason is None
    assert accepted["confidence"] == "confirmed"


def test_segredo_exige_secret_revealed_aceito_para_o_mesmo_id() -> None:
    fact = make_memory_fact(
        "Valerius fez um pacto com Daruun.",
        provenance="canonical_event",
        source_id="evt-public",
        source_turn=6,
    )
    rejected, reason = validate_memory_fact(
        fact,
        {"event_log": [_event("evt-public")]},
    )
    assert rejected is None
    assert reason == "unrevealed_secret:pacto_valerius"

    reveal = _event("evt-reveal", event_type="secret_revealed")
    reveal["target_id"] = "pacto_valerius"
    accepted, reason = validate_memory_fact(
        {**fact, "source_id": "evt-reveal"},
        {"event_log": [reveal]},
    )
    assert reason is None
    assert accepted["confidence"] == "confirmed"


def test_commit_idempotente_promove_mesmo_texto_uma_vez() -> None:
    rumor = make_memory_fact(
        "A ponte caiu.", provenance="npc_claim", source_id="npc:iris", source_turn=2,
    )
    confirmed = make_memory_fact(
        "A ponte caiu.", provenance="canonical_event", source_id="evt-ponte", source_turn=3,
    )
    ledger, promotions = commit_memory_facts([rumor], [confirmed, confirmed])
    assert len(ledger) == 1
    assert ledger[0]["confidence"] == "confirmed"
    assert promotions == 1
    again, promotions = commit_memory_facts(ledger, [confirmed])
    assert again == ledger
    assert promotions == 0


def test_archivist_falha_atomica_deixa_fato_pendente_e_retry_nao_duplica(
    monkeypatch,
) -> None:
    class _Structured:
        def invoke(self, _messages):
            return MemoryUpdate(
                new_summary="A praça está tensa.",
                important_facts=["Valerius talvez esconda um pacto."],
                chronicle_entry="",
            )

    class _LLM:
        def with_structured_output(self, _schema):
            return _Structured()

    monkeypatch.setattr(archivist, "get_llm", lambda **_kw: _LLM())
    writes: list[list[str]] = []
    outcomes = iter([False, True])

    def persist(_game_id, facts, **_kwargs):
        writes.append(list(facts))
        return next(outcomes)

    monkeypatch.setattr(archivist, "add_memory_to_session", persist)
    state = {
        "game_id": "memory-test",
        "world": {"turn_count": 10},
        "archive_due": True,
        "messages": [],
        "narrative_summary": "Antes.",
    }
    failed = archivist.archive_node(state)
    assert failed["archive_due"] is True
    assert len(failed["pending_memory_facts"]) == 1
    assert failed.get("memory_facts", []) == []

    retried = archivist.archive_node({**state, **failed})
    assert retried["pending_memory_facts"] == []
    assert len(retried["memory_facts"]) == 1
    assert retried["memory_facts"][0]["confidence"] == "speculative"
    assert writes == [
        ["Valerius talvez esconda um pacto."],
        ["Valerius talvez esconda um pacto."],
    ]


def test_contexto_rotula_ledger_e_memoria_vetorial_legada(monkeypatch) -> None:
    from services import context_builder

    monkeypatch.setattr(context_builder, "query_rag", lambda *_a, **_k: "")
    monkeypatch.setattr(
        context_builder, "query_session_memory", lambda *_a, **_k: "Memória antiga.",
    )
    pack = build_context_pack(
        {
            "world": {},
            "npcs": {},
            "narrative_summary": "O herói desconfia do castelo.",
            "memory_facts": [make_memory_fact(
                "A ponte caiu.", provenance="canonical_event",
                source_id="evt-ponte", source_turn=3,
            )],
        },
        "ponte", "story", game_id="game-1",
    )
    assert "[CONFIRMADO | canonical_event | fonte evt-ponte | turno 3]" in pack.memory_block
    assert "[NÃO VERIFICADO | legacy_unverified] Memória antiga." in pack.memory_block
    assert "[RESUMO NARRATIVO | speculative]" in pack.memory_block


def test_invariante_e_jsonl_expoem_memoria_sem_fonte() -> None:
    state = {
        "world": {"turn_count": 7},
        "player": {},
        "memory_facts": [{
            "memory_id": "bad",
            "text": "Virou cânone sem prova.",
            "provenance": "canonical_event",
            "confidence": "confirmed",
            "source_id": None,
            "source_turn": 7,
            "canonical_entity_ids": [],
        }],
        "memory_rejections": [{"reason": "unrevealed_secret:x"}],
        "memory_promotions": [{"memory_id": "promoted"}],
    }
    violations = check_memory_provenance(state, None, 7)
    assert [v.check_id for v in violations] == ["memory.confirmed_without_source"]

    rec = TurnRecord(turn=7, action="olhar", route="storyteller", latency_ms=1)
    _fill_state_metrics(rec, state)
    row = turn_to_record(rec)
    assert row["memory_by_provenance"] == {"canonical_event": 1}
    assert row["memory_rejections"] == 1
    assert row["memory_promotions"] == 1


def test_summary_conta_proveniencia_dos_writes_de_startup() -> None:
    result = CampaignResult(
        profile="npc_only",
        seed=1,
        turns_completed=0,
        errors=[],
        history=[],
        final_state={"player": {}, "world": {}, "event_log": []},
        save_path="",
        startup_rag_events=[{
            "operation": "add_session_memory",
            "success": True,
            "provenance_counts": {"inference": 4},
        }],
    )
    summary = build_summary(result, [])
    assert summary["memory"]["writes_by_provenance"] == {"inference": 4}
